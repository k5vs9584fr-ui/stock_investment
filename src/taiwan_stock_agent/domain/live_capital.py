from __future__ import annotations

from taiwan_stock_agent.domain.rotation_cost import estimate_rotation_cost_pct, cost_adjusted_rotation
from taiwan_stock_agent.domain.rotation_risk import rotation_risk_adjustment


BASE_WEIGHTS = {1: 0.40, 2: 0.33, 3: 0.27}


def live_capital_plan(
    live_top3: list[dict],
    oos_guard: dict | None = None,
    max_sector_weight: float = 0.50,
) -> dict:
    """Allocate capital across the live opening Top3 without forcing full deployment."""
    guard_mult = float((oos_guard or {}).get("position_multiplier") or 1.0)
    used_sector: dict[str, float] = {}
    positions: list[dict] = []
    deployed = 0.0

    for rank, row in enumerate(live_top3[:3], 1):
        r = dict(row)
        raw = BASE_WEIGHTS.get(rank, 0.0)

        confidence = (r.get("score_confidence") or {}).get("level") or ""
        if confidence == "MEDIUM":
            raw *= 0.90
        elif confidence == "LOW":
            raw *= 0.65
        elif confidence == "CONFLICT":
            raw *= 0.45

        raw *= guard_mult

        sector = str(r.get("industry_code") or r.get("industry") or "UNKNOWN")
        available = max(0.0, max_sector_weight - used_sector.get(sector, 0.0))
        adjusted = min(raw, available)
        used_sector[sector] = used_sector.get(sector, 0.0) + adjusted
        deployed += adjusted

        positions.append({
            "symbol": r.get("symbol"),
            "name": r.get("name"),
            "live_rank": rank,
            "sector": sector,
            "raw_weight": round(raw, 4),
            "final_weight": round(adjusted, 4),
            "sector_cap_applied": adjusted + 1e-9 < raw,
            "confidence_level": confidence,
        })

    cash = max(0.0, 1.0 - deployed)
    return {
        "positions": positions,
        "deployed_weight": round(deployed, 4),
        "cash_weight": round(cash, 4),
        "oos_multiplier": round(guard_mult, 3),
    }


def build_rotation_table(
    holdings: list[dict],
    challengers: list[dict],
    replacement_fn,
    min_edge: float = 8.0,
) -> list[dict]:
    """Cross-compare holdings vs live challengers and rank best rotation opportunities."""
    rows: list[dict] = []

    for held in holdings:
        for challenger in challengers:
            if str(held.get("symbol")) == str(challenger.get("symbol")):
                continue
            dec = replacement_fn(held, challenger, min_edge=min_edge)
            friction = estimate_rotation_cost_pct()
            dec = cost_adjusted_rotation(dec, friction)
            dec = rotation_risk_adjustment(held, challenger, dec)
            rows.append({
                "held_symbol": held.get("symbol"),
                "held_name": held.get("name"),
                "challenger_symbol": challenger.get("symbol"),
                "challenger_name": challenger.get("name"),
                **dec,
            })

    rows.sort(key=lambda x: float(x.get("edge") or 0.0), reverse=True)
    return rows
