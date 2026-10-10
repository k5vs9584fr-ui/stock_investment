from __future__ import annotations

from taiwan_stock_agent.domain.entry_exit import entry_exit_plan
from taiwan_stock_agent.domain.explosive_lifecycle import classify_explosive_lifecycle
from taiwan_stock_agent.domain.live_capital import (
    build_live_rotation_table,
    live_capital_plan,
    rotation_position_plan,
)
from taiwan_stock_agent.domain.opening_gate import promote_opening_candidates
from taiwan_stock_agent.domain.portfolio_exposure import portfolio_exposure_guard, rotation_exposure_capacity
from taiwan_stock_agent.domain.dynamic_exposure import dynamic_exposure_policy
from taiwan_stock_agent.domain.defensive_reduction import build_defensive_reduction_plan
from taiwan_stock_agent.domain.execution_plan import build_execution_plan


def _symbol(row: dict) -> str:
    return str(row.get("symbol") or row.get("ticker") or "")


def _name(row: dict) -> str:
    return str(row.get("name") or _symbol(row))


def _candidate_view(row: dict) -> dict:
    plan = row.get("entry_exit_plan") or entry_exit_plan(row)
    lifecycle = classify_explosive_lifecycle(row)
    return {
        "symbol": _symbol(row),
        "name": _name(row),
        "rank": row.get("opening_live_rank"),
        "opening_score": row.get("opening_confirmation_score"),
        "hybrid_score": row.get("hybrid_action_score"),
        "practical_score": row.get("practical_score"),
        "explosive_phase": lifecycle.get("phase"),
        "explosive_label": lifecycle.get("label"),
        "explosive_priority": lifecycle.get("priority"),
        "explosive_lifecycle_score": lifecycle.get("score"),
        "explosive_action": lifecycle.get("action"),
        "entry_mode": plan.get("entry_mode"),
        "entry_trigger": plan.get("entry_trigger"),
        "hard_stop": (plan.get("exit_rules") or {}).get("hard_stop"),
        "opening_flags": row.get("opening_confirmation_reasons") or [],
        "gate_reasons": row.get("opening_gate_reasons") or [],
    }



def _select_executable_rotations(rotation_actions: list[dict]) -> list[dict]:
    """Greedily select non-conflicting actionable rotations.

    Keep the full comparison table for diagnostics, but executable actions must
    not reuse the same holding or challenger more than once.
    """
    selected: list[dict] = []
    used_holdings: set[str] = set()
    used_challengers: set[str] = set()

    for row in rotation_actions:
        action = str(row.get("action") or "")
        if action not in {"ROTATE", "WATCH_ROTATION"}:
            continue

        held = str(row.get("held_symbol") or "")
        challenger = str(row.get("challenger_symbol") or "")
        if not held or not challenger:
            continue
        if held in used_holdings or challenger in used_challengers:
            continue

        selected.append(row)
        used_holdings.add(held)
        used_challengers.add(challenger)

    return selected

def build_intraday_decision_report(
    ranked_rows: list[dict],
    holdings: list[dict],
    *,
    phase_minutes: int = 15,
    target_n: int = 3,
    max_per_sector: int = 2,
    oos_guard: dict | None = None,
    holding_weights: dict[str, float] | None = None,
    cost_pct: float | None = None,
    max_total_exposure: float = 0.90,
    max_sector_exposure: float = 0.50,
    market_context: dict | None = None,
) -> dict:
    """Build one compact, reusable intraday decision payload.

    The report deliberately separates fresh-entry candidates, current holdings,
    rotation opportunities, position sizing and no-chase names so any interface
    can render the same trading decision without recomputing business logic.
    """
    holding_weights = holding_weights or {}
    dynamic_policy = dynamic_exposure_policy(
        market_context,
        base_max_total=max_total_exposure,
        base_max_sector=max_sector_exposure,
    )
    effective_max_total_exposure = float(dynamic_policy.get("max_total_exposure") or max_total_exposure)
    effective_max_sector_exposure = float(dynamic_policy.get("max_sector_exposure") or max_sector_exposure)

    live_top, rejected = promote_opening_candidates(
        ranked_rows,
        target_n=target_n,
        phase_minutes=phase_minutes,
        max_per_sector=max_per_sector,
    )

    enriched_top: list[dict] = []
    for row in live_top:
        r = dict(row)
        r["entry_exit_plan"] = r.get("entry_exit_plan") or entry_exit_plan(r)
        enriched_top.append(r)

    capital = live_capital_plan(enriched_top, oos_guard=oos_guard)
    target_weights = {
        str(x.get("symbol") or ""): float(x.get("final_weight") or 0.0)
        for x in capital.get("positions") or []
    }

    by_symbol = {_symbol(r): r for r in ranked_rows}
    symbol_sectors = {
        _symbol(r): str(r.get("industry_code") or r.get("industry") or "UNKNOWN")
        for r in ranked_rows
    }
    exposure = portfolio_exposure_guard(
        holding_weights=holding_weights,
        symbol_sectors=symbol_sectors,
        max_total_exposure=effective_max_total_exposure,
        max_sector_exposure=effective_max_sector_exposure,
    )
    matched_holdings: list[dict] = []
    holding_views: list[dict] = []
    for h in holdings:
        symbol = _symbol(h)
        current = by_symbol.get(symbol)
        if current:
            merged = {**current, **h}
            matched_holdings.append(merged)
            holding_views.append({
                "symbol": symbol,
                "name": _name(merged),
                "matched": True,
                "cost": h.get("cost"),
                "shares": h.get("shares"),
                "hybrid_score": merged.get("hybrid_action_score"),
                "practical_score": merged.get("practical_score"),
            })
        else:
            holding_views.append({
                "symbol": symbol,
                "name": _name(h),
                "matched": False,
                "cost": h.get("cost"),
                "shares": h.get("shares"),
            })

    defensive_reduction = build_defensive_reduction_plan(
        matched_holdings,
        holding_weights=holding_weights,
        symbol_sectors=symbol_sectors,
        max_total_exposure=effective_max_total_exposure,
        max_sector_exposure=effective_max_sector_exposure,
    )

    rotations = build_live_rotation_table(
        matched_holdings,
        enriched_top,
        phase_minutes=phase_minutes,
        cost_pct=cost_pct,
    )

    rotation_actions: list[dict] = []
    for dec in rotations:
        held_symbol = str(dec.get("held_symbol") or "")
        challenger_symbol = str(dec.get("challenger_symbol") or "")
        held = next((x for x in matched_holdings if _symbol(x) == held_symbol), {})
        challenger = next((x for x in enriched_top if _symbol(x) == challenger_symbol), {})
        current_weight = float(holding_weights.get(held_symbol, 0.0))
        challenger_existing_weight = float(holding_weights.get(challenger_symbol, 0.0))
        challenger_target_weight = float(target_weights.get(challenger_symbol, 0.40))
        sizing = rotation_position_plan(
            held,
            challenger,
            dec,
            current_weight=current_weight,
            existing_challenger_weight=challenger_existing_weight,
            target_challenger_weight=challenger_target_weight,
        )
        exposure_capacity = rotation_exposure_capacity(
            held_symbol=held_symbol,
            challenger_symbol=challenger_symbol,
            sell_weight=float(sizing.get("sell_weight") or 0.0),
            holding_weights=holding_weights,
            symbol_sectors=symbol_sectors,
            max_total_exposure=effective_max_total_exposure,
            max_sector_exposure=effective_max_sector_exposure,
        )
        allowed_buy = min(
            float(sizing.get("buy_weight") or 0.0),
            float(exposure_capacity.get("max_buy_capacity") or 0.0),
        )
        if allowed_buy + 1e-9 < float(sizing.get("buy_weight") or 0.0):
            released = float(sizing.get("sell_weight") or 0.0)
            sizing["buy_weight"] = round(allowed_buy, 4)
            sizing["cash_from_rotation"] = round(max(0.0, released - allowed_buy), 4)
            sizing["exposure_limited"] = True
        else:
            sizing["exposure_limited"] = False
        sizing["portfolio_exposure_capacity"] = exposure_capacity

        rotation_actions.append({
            "held_symbol": held_symbol,
            "held_name": dec.get("held_name"),
            "challenger_symbol": challenger_symbol,
            "challenger_name": dec.get("challenger_name"),
            "action": dec.get("final_action"),
            "live_rotation_edge": dec.get("live_rotation_edge"),
            "reasons": dec.get("live_rotation_reasons") or [],
            "chase_flags": dec.get("chase_flags") or [],
            "position_plan": sizing,
        })

    no_chase: list[dict] = []
    for row in rejected:
        no_chase.append({
            "symbol": _symbol(row),
            "name": _name(row),
            "reasons": row.get("opening_gate_reasons") or [],
        })
    for dec in rotation_actions:
        if dec.get("chase_flags"):
            no_chase.append({
                "symbol": dec.get("challenger_symbol"),
                "name": dec.get("challenger_name"),
                "reasons": dec.get("chase_flags"),
            })

    action_priority = {"ROTATE": 2, "WATCH_ROTATION": 1, "KEEP_CURRENT": 0}
    rotation_actions.sort(
        key=lambda x: (
            action_priority.get(str(x.get("action")), 0),
            float(x.get("live_rotation_edge") or 0.0),
        ),
        reverse=True,
    )
    selected_rotations = _select_executable_rotations(rotation_actions)
    execution = build_execution_plan(
        top_candidates=[_candidate_view(r) for r in enriched_top],
        capital_plan=capital,
        holding_weights=holding_weights,
        selected_rotations=selected_rotations,
        defensive_reduction_plan=defensive_reduction,
    )

    return {
        "phase_minutes": int(phase_minutes),
        "top_candidates": [_candidate_view(r) for r in enriched_top],
        "capital_plan": capital,
        "portfolio_exposure": exposure,
        "dynamic_exposure_policy": dynamic_policy,
        "defensive_reduction_plan": defensive_reduction,
        "holdings": holding_views,
        "rotation_actions": rotation_actions,
        "selected_rotations": selected_rotations,
        "execution_plan": execution,
        "no_chase": no_chase,
        "summary": {
            "top_candidate": _symbol(enriched_top[0]) if enriched_top else None,
            "rotation_count": sum(1 for x in selected_rotations if x.get("action") == "ROTATE"),
            "watch_rotation_count": sum(
                1 for x in selected_rotations if x.get("action") == "WATCH_ROTATION"
            ),
            "cash_weight": capital.get("cash_weight"),
            "total_exposure": exposure.get("total_exposure"),
            "remaining_total_capacity": exposure.get("remaining_total_capacity"),
            "regime_v2": dynamic_policy.get("regime_v2"),
            "max_total_exposure": dynamic_policy.get("max_total_exposure"),
            "max_sector_exposure": dynamic_policy.get("max_sector_exposure"),
            "needs_defensive_reduction": defensive_reduction.get("needs_reduction"),
            "execution_buy_count": execution.get("buy_count"),
            "execution_sell_count": execution.get("sell_count"),
            "defensive_reduction_weight": sum(
                float(x.get("reduce_weight") or 0.0)
                for x in defensive_reduction.get("actions") or []
            ),
        },
    }
