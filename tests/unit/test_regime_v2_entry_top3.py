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


def test_top3_quality_prefers_explosive_early_move():
    slow_score, _ = top3_quality({
        "practical_score": 82,
        "surge_score": 35,
        "surge_stage": "B級：非飆股型",
        "surge_metrics": {
            "return3_pct": 0.4,
            "return5_pct": 1.0,
            "fresh_ignition": False,
            "early_main_move": False,
            "trend_accelerator": False,
            "overextended": False,
            "volume3_vs_20": 0.9,
        },
        "practical_flags": [],
        "surge_flags": [],
    })
    explosive_score, reasons = top3_quality({
        "practical_score": 78,
        "surge_score": 72,
        "surge_stage": "A級：剛發動",
        "surge_metrics": {
            "return3_pct": 2.8,
            "return5_pct": 5.2,
            "fresh_ignition": True,
            "early_main_move": True,
            "trend_accelerator": True,
            "overextended": False,
            "volume3_vs_20": 1.8,
        },
        "practical_flags": [],
        "surge_flags": ["VOLUME_EXPANSION"],
    })
    assert explosive_score > slow_score
    assert "EXPLOSIVE_FRESH_IGNITION" in reasons
    assert "EXPLOSIVE_EARLY_MAIN_MOVE" in reasons
    assert "EXPLOSIVE_VOLUME_CONFIRM" in reasons


def test_top3_quality_never_rewards_overextended_explosive_name():
    score, reasons = top3_quality({
        "practical_score": 90,
        "surge_score": 98,
        "surge_stage": "X級：延伸過熱/不追",
        "surge_metrics": {
            "return3_pct": 8.0,
            "return5_pct": 14.0,
            "fresh_ignition": True,
            "early_main_move": True,
            "trend_accelerator": True,
            "overextended": True,
            "volume3_vs_20": 2.5,
        },
        "practical_flags": [],
        "surge_flags": ["VOLUME_EXPANSION"],
    })
    assert score <= 59
    assert "EXPLOSIVE_OVEREXTENDED_NO_CHASE" in reasons
