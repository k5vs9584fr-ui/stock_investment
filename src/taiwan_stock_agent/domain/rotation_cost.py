from __future__ import annotations


def estimate_rotation_cost_pct(
    sell_fee_pct: float = 0.1425,
    buy_fee_pct: float = 0.1425,
    sell_tax_pct: float = 0.30,
    slippage_pct: float = 0.20,
) -> float:
    """Approximate round-trip rotation friction in percentage points.

    Defaults are configurable and intentionally conservative. This function
    models friction only; brokers may apply discounts and Taiwan tax treatment
    differs by product/instrument.
    """
    return round(
        float(sell_fee_pct)
        + float(buy_fee_pct)
        + float(sell_tax_pct)
        + float(slippage_pct),
        4,
    )


def cost_adjusted_rotation(
    decision: dict,
    cost_pct: float,
    score_per_pct: float = 2.0,
    rotate_threshold: float = 8.0,
    watch_threshold: float = 3.0,
) -> dict:
    """Downgrade rotation decisions after estimated execution friction.

    Converts cost percentage into score-equivalent friction. This preserves the
    opportunity-cost model scale while preventing marginal rotations.
    """
    raw_edge = float(decision.get("edge") or 0.0)
    friction_score = max(0.0, float(cost_pct)) * float(score_per_pct)
    net_edge = raw_edge - friction_score

    if net_edge >= rotate_threshold:
        action = "ROTATE"
    elif net_edge >= watch_threshold:
        action = "WATCH_ROTATION"
    else:
        action = "KEEP_CURRENT"

    return {
        **decision,
        "estimated_cost_pct": round(float(cost_pct), 4),
        "friction_score": round(friction_score, 2),
        "net_edge": round(net_edge, 2),
        "action_after_cost": action,
    }
