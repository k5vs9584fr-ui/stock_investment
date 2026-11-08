from __future__ import annotations

from taiwan_stock_agent.domain.regime_v2 import classify_regime_v2


def dynamic_exposure_policy(
    market_context: dict | None,
    *,
    base_max_total: float = 0.90,
    base_max_sector: float = 0.50,
) -> dict:
    """Map market regime to portfolio-level exposure limits."""
    regime = classify_regime_v2(market_context)
    phase = str(regime.get("regime_v2") or "range_or_mixed")

    total_map = {
        "trend_expansion": 0.95,
        "early_or_healthy_uptrend": 0.90,
        "improving_transition": 0.85,
        "range_or_mixed": 0.75,
        "narrow_leadership": 0.70,
        "weak_transition": 0.60,
        "panic_or_selloff": 0.45,
    }
    sector_map = {
        "trend_expansion": 0.55,
        "early_or_healthy_uptrend": 0.50,
        "improving_transition": 0.45,
        "range_or_mixed": 0.40,
        "narrow_leadership": 0.35,
        "weak_transition": 0.30,
        "panic_or_selloff": 0.25,
    }

    dynamic_total = min(float(base_max_total), total_map.get(phase, 0.75))
    dynamic_sector = min(float(base_max_sector), sector_map.get(phase, 0.40))

    return {
        "regime_v2": phase,
        "aggression_multiplier": regime.get("aggression_multiplier"),
        "max_total_exposure": round(dynamic_total, 4),
        "max_sector_exposure": round(dynamic_sector, 4),
    }
