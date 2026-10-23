from __future__ import annotations

from taiwan_stock_agent.domain.opening_gate import opening_confirmation_score, opening_eligibility
from taiwan_stock_agent.domain.opportunity_cost import replacement_decision
from taiwan_stock_agent.domain.rotation_cost import cost_adjusted_rotation, estimate_rotation_cost_pct
from taiwan_stock_agent.domain.rotation_risk import rotation_risk_adjustment


_CHASE_FLAGS = {
    "ENTRY_STRETCHED_FROM_VWAP",
    "MISSED_PLANNED_ENTRY",
    "ENTRY_MOMENTUM_CHASE_RISK",
    "ENTRY_NEAR_HIGH_CHASE_RISK",
    "OPEN5_TOO_HOT",
    "OPEN30_TOO_EXTENDED",
    "OPEN_VWAP_CHASE_RISK",
}


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def live_rotation_decision(
    held_row: dict,
    challenger_row: dict,
    *,
    phase_minutes: int = 15,
    cost_pct: float | None = None,
    min_edge: float = 8.0,
    watch_edge: float = 3.0,
) -> dict:
    base = replacement_decision(held_row, challenger_row, min_edge=min_edge)

    if cost_pct is None:
        cost_pct = estimate_rotation_cost_pct()

    after_cost = cost_adjusted_rotation(
        base,
        cost_pct=cost_pct,
        rotate_threshold=min_edge,
        watch_threshold=watch_edge,
    )
    after_risk = rotation_risk_adjustment(
        held_row,
        challenger_row,
        after_cost,
    )

    held_live, held_live_flags = opening_confirmation_score(
        held_row, phase_minutes=phase_minutes
    )
    challenger_live, challenger_live_flags = opening_confirmation_score(
        challenger_row, phase_minutes=phase_minutes
    )

    held_anchor = float(held_row.get("hybrid_action_score") or 0.0)
    challenger_anchor = float(challenger_row.get("hybrid_action_score") or 0.0)

    held_open_delta = held_live - held_anchor
    challenger_open_delta = challenger_live - challenger_anchor
    opening_edge_adjustment = _clip(
        challenger_open_delta - held_open_delta,
        -10.0,
        10.0,
    )

    risk_edge = float(after_risk.get("risk_adjusted_edge") or 0.0)
    live_edge = risk_edge + opening_edge_adjustment

    challenger_ok, challenger_gate = opening_eligibility(challenger_row)
    chase_flags = sorted(_CHASE_FLAGS.intersection(set(challenger_live_flags)))

    reasons: list[str] = []
    if not challenger_ok:
        action = "KEEP_CURRENT"
        reasons.append("ROTATION_CHALLENGER_OPEN_FAIL")
    elif chase_flags:
        action = "KEEP_CURRENT"
        reasons.append("ROTATION_NO_CHASE")
    elif live_edge >= min_edge:
        action = "ROTATE"
        reasons.append("ROTATION_LIVE_EDGE_CONFIRMED")
    elif live_edge >= watch_edge:
        action = "WATCH_ROTATION"
        reasons.append("ROTATION_LIVE_EDGE_MARGINAL")
    else:
        action = "KEEP_CURRENT"
        reasons.append("ROTATION_EDGE_INSUFFICIENT")

    return {
        **after_risk,
        "phase_minutes": int(phase_minutes),
        "held_opening_score": round(held_live, 1),
        "challenger_opening_score": round(challenger_live, 1),
        "held_opening_flags": held_live_flags,
        "challenger_opening_flags": challenger_live_flags,
        "challenger_opening_gate": challenger_gate,
        "opening_edge_adjustment": round(opening_edge_adjustment, 2),
        "live_rotation_edge": round(live_edge, 2),
        "chase_flags": chase_flags,
        "live_rotation_reasons": reasons,
        "final_action": action,
    }
