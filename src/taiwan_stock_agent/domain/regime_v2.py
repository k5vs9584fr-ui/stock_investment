from __future__ import annotations


def classify_regime_v2(context: dict | None) -> dict:
    ctx = context or {}
    state = str(ctx.get("market_state") or "mixed")
    breadth = float(ctx.get("market_breadth") or 50.0)
    ret5 = ctx.get("market_return_5d")
    ret5 = float(ret5) if ret5 is not None else 0.0

    if state == "broad_selloff":
        phase = "panic_or_selloff"
        aggression = 0.45
    elif state == "broad_rally" and ret5 >= 3.0 and breadth >= 75:
        phase = "trend_expansion"
        aggression = 1.15
    elif state == "broad_rally":
        phase = "early_or_healthy_uptrend"
        aggression = 1.00
    elif state == "narrow_leadership":
        phase = "narrow_leadership"
        aggression = 0.70
    elif ret5 <= -3.0 and breadth < 45:
        phase = "weak_transition"
        aggression = 0.60
    elif ret5 >= 2.0 and breadth >= 55:
        phase = "improving_transition"
        aggression = 0.85
    else:
        phase = "range_or_mixed"
        aggression = 0.75

    return {
        "regime_v2": phase,
        "aggression_multiplier": aggression,
    }
