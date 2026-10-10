from taiwan_stock_agent.domain.segmented_risk import segmented_risk_adjustment


def test_segmented_risk_penalizes_high_failure_pattern():
    stats = {
        "by_pattern": {
            "RSI_HOT": {"n": 30, "failure_rate": 60.0}
        },
        "industry_pattern": {},
    }
    score, flags = segmented_risk_adjustment("半導體業", ["RSI_HOT:78"], stats)
    assert score < 0
    assert any("PATTERN_HIGH_FAIL" in x for x in flags)


def test_segmented_risk_ignores_small_samples():
    stats = {
        "by_pattern": {
            "RSI_HOT": {"n": 5, "failure_rate": 80.0}
        },
        "industry_pattern": {},
    }
    score, flags = segmented_risk_adjustment("半導體業", ["RSI_HOT:78"], stats)
    assert score == 0
    assert flags == []


def test_segmented_risk_rewards_low_failure_combo_with_enough_samples():
    stats = {
        "by_pattern": {},
        "industry_pattern": {
            "光電業|BREAKOUT_20D": {"n": 12, "failure_rate": 25.0}
        },
    }
    score, flags = segmented_risk_adjustment("光電業", ["BREAKOUT_20D:100>98"], stats)
    assert score > 0
    assert any("INDUSTRY_PATTERN_LOW_FAIL" in x for x in flags)
