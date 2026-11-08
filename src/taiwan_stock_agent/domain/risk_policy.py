from __future__ import annotations

from taiwan_stock_agent.domain.loss_streak import loss_streak_multiplier

def risk_policy(practical_score: float, market_context: dict | None = None, consecutive_losses: int = 0) -> dict:
    state = str((market_context or {}).get("market_state") or "mixed")

    if practical_score >= 82:
        risk_pct = 0.75
        max_position_pct = 20.0
    elif practical_score >= 72:
        risk_pct = 0.50
        max_position_pct = 15.0
    else:
        risk_pct = 0.25
        max_position_pct = 10.0

    if state == "broad_selloff":
        risk_pct *= 0.5
        max_position_pct *= 0.5
    elif state == "narrow_leadership":
        risk_pct *= 0.75
        max_position_pct *= 0.75
    elif state == "broad_rally":
        max_position_pct = min(25.0, max_position_pct * 1.15)

    streak_mult = loss_streak_multiplier(consecutive_losses)
    risk_pct *= streak_mult
    max_position_pct *= streak_mult

    return {
        "risk_per_trade_pct": round(risk_pct, 2),
        "max_position_pct": round(max_position_pct, 1),
        "loss_streak_multiplier": streak_mult,
        "add_rule": "ADD_ONLY_AFTER_CONFIRMATION_AND_PROFIT",
        "average_down": False,
        "stop_rule": "TECHNICAL_STOP_OR_MAX_7_8_PERCENT",
    }
