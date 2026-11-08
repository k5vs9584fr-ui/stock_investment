from taiwan_stock_agent.domain.explosive_failure import explosive_failure_adjustment
from taiwan_stock_agent.domain.opening_reorder import opening_reorder_score


def _fresh(dt):
    return {
        "hybrid_action_score": 88,
        "surge_score": 82,
        "surge_stage": "S級：首發動可追",
        "surge_flags": ["FRESH_IGNITION_CHASABLE", "VOLUME_EXPANSION"],
        "surge_metrics": {
            "return3_pct": 2.5,
            "return5_pct": 4.0,
            "return10_pct": 5.0,
            "fresh_ignition": True,
            "early_main_move": False,
            "trend_accelerator": False,
            "overextended": False,
            "chaseable": True,
            "volume3_vs_20": 1.8,
        },
        "dt_metrics": dt,
    }


def test_fresh_ignition_soft_fails_when_15m_followthrough_is_weak():
    row = _fresh({
        "vwap_gap_pct": -0.5,
        "return_15m_pct": 0.1,
        "volume_accel_5m": 0.7,
        "near_intraday_high": 0.97,
    })
    out = explosive_failure_adjustment(row, phase_minutes=15)
    assert out["failed"] is True
    assert out["severity"] in {"SOFT_FAIL", "HARD_FAIL"}
    assert "EXPLOSIVE_FAIL_BELOW_VWAP" in out["reasons"]


def test_fresh_ignition_hard_fails_by_30m_if_it_loses_high_and_momentum():
    row = _fresh({
        "vwap_gap_pct": -0.7,
        "return_15m_pct": -0.4,
        "return_30m_pct": -0.3,
        "volume_accel_5m": 0.6,
        "near_intraday_high": 0.93,
    })
    out = explosive_failure_adjustment(row, phase_minutes=30)
    assert out["severity"] == "HARD_FAIL"
    assert out["action"] == "DROP_FROM_ATTACK"


def test_hard_failed_explosive_setup_is_capped_below_actionable_tier():
    row = _fresh({
        "vwap_gap_pct": -0.7,
        "return_15m_pct": -0.4,
        "return_30m_pct": -0.3,
        "volume_accel_5m": 0.6,
        "near_intraday_high": 0.93,
    })
    score, flags = opening_reorder_score(row, phase_minutes=30)
    assert score <= 59
    assert "EXPLOSIVE_HARD_FAIL_DROP" in flags


def test_confirmed_fresh_ignition_keeps_attack_status():
    row = _fresh({
        "vwap_gap_pct": 0.8,
        "return_15m_pct": 1.4,
        "return_30m_pct": 2.0,
        "volume_accel_5m": 1.8,
        "near_intraday_high": 0.992,
    })
    out = explosive_failure_adjustment(row, phase_minutes=30)
    assert out["failed"] is False
    assert out["severity"] == "NONE"
