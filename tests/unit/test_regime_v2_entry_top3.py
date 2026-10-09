from taiwan_stock_agent.domain.regime_v2 import classify_regime_v2
from taiwan_stock_agent.domain.entry_exit import entry_exit_plan
from taiwan_stock_agent.domain.top3_quality import top3_quality


def test_regime_v2_trend_expansion():
    r = classify_regime_v2({
        "market_state": "broad_rally",
        "market_breadth": 82,
        "market_return_5d": 4.0,
    })
    assert r["regime_v2"] == "trend_expansion"
    assert r["aggression_multiplier"] > 1


def test_entry_breakout_confirm():
    p = entry_exit_plan({
        "practical_score": 86,
        "price": 100,
        "dt_metrics": {
            "breakout_price": 101,
            "recent_support": 98,
            "suggested_stop": 97.5,
            "vwap": 99.5,
            "volume_accel_5m": 1.8,
            "return_15m_pct": 0.5,
        },
    })
    assert p["entry_mode"] == "BREAKOUT_CONFIRM"
    assert p["entry_trigger"] == 101


def test_entry_pullback_for_non_breakout():
    p = entry_exit_plan({
        "practical_score": 75,
        "dt_metrics": {
            "recent_support": 50,
            "vwap": 51,
            "volume_accel_5m": 0.8,
            "return_15m_pct": -0.1,
        },
    })
    assert p["entry_mode"] == "PULLBACK_BUY"
    assert p["entry_trigger"] == 50


def test_top3_quality_rewards_confirmed_leader():
    score, reasons = top3_quality({
        "practical_score": 80,
        "practical_flags": [
            "RELATIVE_STRENGTH_LEADER",
            "LIVERMORE_PIVOT_CONFIRM",
            "ONEIL_LEADER_BREAKOUT",
        ],
    })
    assert score > 80
    assert "RS_LEADER" in reasons


def test_top3_quality_penalizes_danger_flags():
    score, reasons = top3_quality({
        "practical_score": 88,
        "practical_flags": [
            "FAILED_BREAKOUT_WEAK_CLOSE",
            "BEARISH_VOLUME_PRICE_DIVERGENCE",
        ],
    })
    assert score < 80
