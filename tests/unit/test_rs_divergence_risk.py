from taiwan_stock_agent.domain.relative_strength import relative_strength_overlay
from taiwan_stock_agent.domain.divergence_overlay import divergence_overlay
from taiwan_stock_agent.domain.loss_streak import loss_streak_multiplier
from taiwan_stock_agent.domain.risk_policy import risk_policy


def test_relative_strength_leader():
    bonus, flags = relative_strength_overlay(
        {"surge_metrics": {"return5_pct": 5, "return10_pct": 8}},
        {"market_return_5d": 0, "market_return_10d": 1},
    )
    assert bonus > 0
    assert "RELATIVE_STRENGTH_LEADER" in flags


def test_relative_strength_laggard():
    bonus, flags = relative_strength_overlay(
        {"surge_metrics": {"return5_pct": -2, "return10_pct": -4}},
        {"market_return_5d": 3, "market_return_10d": 4},
    )
    assert bonus < 0
    assert "RELATIVE_STRENGTH_LAGGARD" in flags


def test_failed_breakout_divergence_penalty():
    bonus, flags = divergence_overlay({
        "close_strength": 0.35,
        "surge_flags": ["BREAKOUT_20D"],
        "surge_metrics": {"return3_pct": 0.2, "return5_pct": 2, "volume3_vs_20": 2.0},
        "structure_metrics": {"near_20d_high": 0.98},
    })
    assert bonus < 0
    assert "FAILED_BREAKOUT_WEAK_CLOSE" in flags


def test_loss_streak_reduces_risk():
    assert loss_streak_multiplier(0) == 1.0
    assert loss_streak_multiplier(3) == 0.50
    p = risk_policy(85, {"market_state": "mixed"}, consecutive_losses=3)
    assert p["risk_per_trade_pct"] < 0.75
    assert p["loss_streak_multiplier"] == 0.50
