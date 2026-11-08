from taiwan_stock_agent.domain.catalyst_overlay import catalyst_overlay
from taiwan_stock_agent.domain.post_trade_review import classify_outcome, review_failures


def test_catalyst_requires_price_confirmation():
    bonus, flags = catalyst_overlay({
        "catalyst_type": "revenue",
        "catalyst_strength": 85,
        "catalyst_age_days": 1,
        "close_strength": 0.8,
        "surge_metrics": {"return3_pct": 2.0, "volume3_vs_20": 1.5},
    })
    assert bonus > 0
    assert "CATALYST_CONFIRMED" in flags


def test_rejected_catalyst_is_penalized():
    bonus, flags = catalyst_overlay({
        "catalyst_type": "earnings",
        "catalyst_strength": 90,
        "catalyst_age_days": 1,
        "close_strength": 0.3,
        "surge_metrics": {"return3_pct": -2.0, "volume3_vs_20": 2.0},
    })
    assert bonus < 0
    assert "CATALYST_REJECTED_BY_PRICE" in flags


def test_review_failure_flags():
    out = review_failures([
        {
            "hybrid_action_score": 85,
            "t5_return": -6,
            "practical_flags": ["FAILED_BREAKOUT_WEAK_CLOSE", "RS_LEADER"],
        },
        {
            "hybrid_action_score": 80,
            "t5_return": -2,
            "practical_flags": ["FAILED_BREAKOUT_WEAK_CLOSE"],
        },
    ])
    assert out["failed_high_score_count"] == 2
    assert out["common_failure_flags"][0]["flag"] == "FAILED_BREAKOUT_WEAK_CLOSE"


def test_outcome_classifier():
    assert classify_outcome(6.0) == "WIN_STRONG"
    assert classify_outcome(-2.0, -9.0) == "LOSS_LARGE"
