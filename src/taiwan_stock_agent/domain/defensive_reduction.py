from __future__ import annotations

from taiwan_stock_agent.domain.explosive_lifecycle import classify_explosive_lifecycle
from taiwan_stock_agent.domain.opening_gate import opening_eligibility


def build_defensive_reduction_plan(
    holdings: list[dict],
    *,
    holding_weights: dict[str, float],
    symbol_sectors: dict[str, str],
    max_total_exposure: float,
    max_sector_exposure: float,
) -> dict:
    """Build a prioritized de-risking plan when portfolio exposure exceeds limits."""
    total = sum(max(0.0, float(w)) for w in (holding_weights or {}).values())
    total_excess = max(0.0, total - max_total_exposure)

    sector_weights: dict[str, float] = {}
    for symbol, weight in (holding_weights or {}).items():
        sector = str(symbol_sectors.get(str(symbol), "UNKNOWN"))
        sector_weights[sector] = sector_weights.get(sector, 0.0) + max(0.0, float(weight))

    sector_excess = {
        sector: max(0.0, weight - max_sector_exposure)
        for sector, weight in sector_weights.items()
    }

    if total_excess <= 1e-9 and not any(v > 1e-9 for v in sector_excess.values()):
        return {
            "needs_reduction": False,
            "total_excess": 0.0,
            "actions": [],
        }

    ranked: list[dict] = []
    for row in holdings:
        symbol = str(row.get("symbol") or row.get("ticker") or "")
        weight = max(0.0, float(holding_weights.get(symbol, 0.0)))
        if weight <= 0:
            continue

        lifecycle = classify_explosive_lifecycle(row)
        phase = str(lifecycle.get("phase") or "")
        action_score = float(row.get("hybrid_action_score") or 0.0)
        practical = float(row.get("practical_score") or 0.0)
        sector = str(symbol_sectors.get(symbol, "UNKNOWN"))
        open_ok, open_reasons = opening_eligibility(row)

        protect = 0.0
        if phase == "EARLY_MAIN_MOVE":
            protect += 20.0
        elif phase == "FRESH_IGNITION":
            protect += 16.0
        elif phase == "ACCELERATING":
            protect += 10.0

        sector_pressure = 20.0 if sector_excess.get(sector, 0.0) > 0 else 0.0
        open_failure = 0.0 if open_ok else 18.0
        weakness = max(0.0, 80.0 - action_score) + max(0.0, 72.0 - practical) * 0.5
        reduction_priority = weakness + sector_pressure + open_failure - protect

        protected_floor = 0.0
        if phase == "EARLY_MAIN_MOVE" and open_ok:
            protected_floor = min(weight, 0.15)
        elif phase == "FRESH_IGNITION" and open_ok:
            protected_floor = min(weight, 0.10)

        ranked.append({
            "symbol": symbol,
            "name": row.get("name") or symbol,
            "weight": weight,
            "sector": sector,
            "phase": phase,
            "action_score": action_score,
            "practical_score": practical,
            "reduction_priority": reduction_priority,
            "opening_eligible": open_ok,
            "opening_reasons": open_reasons,
            "protected_floor": protected_floor,
        })

    ranked.sort(key=lambda x: (x["reduction_priority"], x["weight"]), reverse=True)

    remaining_total = total_excess
    remaining_sector = dict(sector_excess)
    actions: list[dict] = []

    for row in ranked:
        sector = row["sector"]
        sector_need = max(0.0, remaining_sector.get(sector, 0.0))
        need = max(remaining_total, sector_need)
        if need <= 1e-9:
            break

        max_reducible = max(0.0, row["weight"] - row.get("protected_floor", 0.0))
        reduce_weight = min(max_reducible, need)
        if reduce_weight <= 1e-9:
            continue

        actions.append({
            "symbol": row["symbol"],
            "name": row["name"],
            "sector": sector,
            "phase": row["phase"],
            "current_weight": round(row["weight"], 4),
            "reduce_weight": round(reduce_weight, 4),
            "remaining_weight": round(max(0.0, row["weight"] - reduce_weight), 4),
            "reason": "SECTOR_AND_TOTAL_EXCESS" if sector_need > 0 and remaining_total > 0
                else "SECTOR_EXCESS" if sector_need > 0
                else "TOTAL_EXPOSURE_EXCESS",
            "opening_eligible": row.get("opening_eligible"),
            "opening_reasons": row.get("opening_reasons") or [],
            "protected_floor": round(float(row.get("protected_floor") or 0.0), 4),
        })

        remaining_total = max(0.0, remaining_total - reduce_weight)
        if sector in remaining_sector:
            remaining_sector[sector] = max(0.0, remaining_sector[sector] - reduce_weight)

    total_reduced = sum(float(x.get("reduce_weight") or 0.0) for x in actions)
    post_total = max(0.0, total - total_reduced)
    post_sectors = dict(sector_weights)
    for action in actions:
        sector = str(action.get("sector") or "UNKNOWN")
        post_sectors[sector] = max(
            0.0,
            float(post_sectors.get(sector, 0.0)) - float(action.get("reduce_weight") or 0.0),
        )

    return {
        "needs_reduction": bool(actions),
        "total_excess": round(total_excess, 4),
        "sector_excess": {k: round(v, 4) for k, v in sector_excess.items()},
        "actions": actions,
        "total_reduce_weight": round(total_reduced, 4),
        "post_reduction_total_exposure": round(post_total, 4),
        "post_reduction_sector_exposure": {k: round(v, 4) for k, v in post_sectors.items()},
        "remaining_total_excess": round(remaining_total, 4),
    }
