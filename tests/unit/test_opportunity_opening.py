from taiwan_stock_agent.domain.opportunity_cost import opportunity_cost_score, replacement_decision
from taiwan_stock_agent.domain.opening_reorder import opening_reorder_score


def test_opportunity_cost_rewards_actionable_candidate():
    score, flags = opportunity_cost_score({
        "hybrid_action_score": 88,
        "practical_score": 90,
        "surge_score": 82,
        "score_confidence": {"level": "HIGH"},
        "risk_policy": {"max_position_pct": 20},
        "practical_flags": [],
    })
    assert score > 85
    assert "OC_HIGH_CONFIDENCE" in flags


def test_opportunity_cost_penalizes_stagnant_conflicted_name():
    score, flags = opportunity_cost_score({
        "hybrid_action_score": 82,
        "practical_score": 58,
        "surge_score": 20,
        "score_confidence": {"level": "CONFLICT"},
        "risk_policy": {"max_position_pct": 10},
        "practical_flags": ["MODEL_ONLY_STAGNATION_PENALTY"],
    })
    assert score < 65
    assert "OC_MODEL_CONFLICT" in flags
    assert "OC_POOR_CAPITAL_EFFICIENCY" in flags


def test_replacement_requires_meaningful_edge():
    held = {
        "hybrid_action_score": 70,
        "practical_score": 68,
        "surge_score": 35,
        "score_confidence": {"level": "MEDIUM"},
        "risk_policy": {"max_position_pct": 15},
        "practical_flags": [],
    }
    challenger = {
        "hybrid_action_score": 90,
        "practical_score": 92,
        "surge_score": 85,
        "score_confidence": {"level": "HIGH"},
        "risk_policy": {"max_position_pct": 20},
        "practical_flags": [],
    }
    out = replacement_decision(held, challenger)
    assert out["action"] == "ROTATE"
    assert out["edge"] >= 8


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
