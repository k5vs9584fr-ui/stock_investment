from taiwan_stock_agent.domain.darvas_overlay import darvas_overlay
from taiwan_stock_agent.domain.market_regime import market_regime_adjustment


def test_broad_selloff_reduces_conviction():
    adj, flags = market_regime_adjustment({
        "market_state": "broad_selloff",
        "market_breadth": 18,
    })
    assert adj <= -15
    assert "REGIME_BROAD_SELLOFF" in flags


def test_broad_rally_raises_conviction():
    adj, flags = market_regime_adjustment({
        "market_state": "broad_rally",
        "market_breadth": 82,
    })
    assert adj >= 8
    assert "REGIME_BROAD_RALLY" in flags


def test_darvas_box_breakout_bonus():
    bonus, flags = darvas_overlay({
        "close_strength": 0.88,
        "structure_flags": ["NOT_EXTENDED_10D", "AT_BREAKOUT"],
        "structure_metrics": {
            "range20_pct": 12,
            "near_20d_high": 0.97,
        },
        "surge_flags": ["BREAKOUT_20D"],
        "surge_metrics": {"return3_pct": 2.2},
    })
    assert bonus > 0
    assert "DARVAS_BOX_BREAKOUT" in flags


def test_failed_breakout_penalty():
    bonus, flags = darvas_overlay({
        "close_strength": 0.35,
        "structure_flags": ["AT_BREAKOUT"],
        "structure_metrics": {
            "range20_pct": 14,
            "near_20d_high": 0.98,
        },
        "surge_flags": ["BREAKOUT_20D"],
        "surge_metrics": {"return3_pct": 0.1},
    })
    assert bonus < 0
    assert "DARVAS_FAILED_BREAKOUT" in flags
