from taiwan_stock_agent.domain.opening_reorder import (
    missed_entry_penalty,
    opening_reorder_score,
)


def test_opening_reorder_neutral_without_intraday_metrics():
    score, flags = opening_reorder_score({
        "hybrid_action_score": 80,
        "dt_metrics": {},
    })
    assert score == 80
    assert flags == []


def test_opening_reorder_rewards_confirmed_strength():
    score, flags = opening_reorder_score({
        "hybrid_action_score": 80,
        "dt_metrics": {
            "volume_accel_5m": 1.8,
            "return_15m_pct": 1.2,
            "vwap_gap_pct": 0.8,
            "near_intraday_high": 0.995,
        },
    })
    assert score > 95
    assert "OPEN_VOL_ACCEL_PRIME" in flags
    assert "OPEN_ABOVE_VWAP" in flags


def test_opening_reorder_penalizes_failed_open():
    score, flags = opening_reorder_score({
        "hybrid_action_score": 85,
        "dt_metrics": {
            "volume_accel_5m": 0.8,
            "return_15m_pct": -1.0,
            "vwap_gap_pct": -1.2,
            "near_intraday_high": 0.94,
        },
    })
    assert score < 75
    assert "OPEN_BELOW_VWAP" in flags


def test_5m_phase_rewards_early_volume_ignition():
    score, flags = opening_reorder_score({
        "hybrid_action_score": 80,
        "dt_metrics": {
            "volume_accel_5m": 2.0,
            "return_5m_pct": 0.9,
            "vwap_gap_pct": 0.6,
            "near_intraday_high": 0.99,
        },
    }, phase_minutes=5)
    assert score > 90
    assert "OPEN5_VOL_IGNITION" in flags


def test_30m_phase_penalizes_failed_spike():
    score, flags = opening_reorder_score({
        "hybrid_action_score": 88,
        "dt_metrics": {
            "volume_accel_5m": 0.7,
            "return_30m_pct": -0.4,
            "vwap_gap_pct": -0.6,
            "near_intraday_high": 0.93,
        },
    }, phase_minutes=30)
    assert score < 75
    assert "OPEN30_FAILED_SPIKE" in flags


def test_missed_entry_penalty_marks_chase_risk():
    penalty, flags = missed_entry_penalty({
        "dt_metrics": {
            "vwap_gap_pct": 3.4,
            "planned_entry_gap_pct": 3.1,
            "return_15m_pct": 4.8,
            "near_intraday_high": 0.998,
        },
    })
    assert penalty <= -15
    assert "MISSED_PLANNED_ENTRY" in flags
    assert "ENTRY_MOMENTUM_CHASE_RISK" in flags
