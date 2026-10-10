from taiwan_stock_agent.domain.practical_score import calculate_practical_score


def test_stagnant_high_model_is_penalized():
    score, flags = calculate_practical_score({
        "final_score": 90,
        "chip_score": 85,
        "surge_score": 20,
        "close_strength": 0.8,
        "surge_metrics": {
            "return3_pct": 0.2,
            "return5_pct": 0.6,
            "return10_pct": 1.0,
            "fresh_ignition": False,
            "early_main_move": False,
            "overextended": False,
            "trend_accelerator": False,
        },
    })
    assert "MODEL_ONLY_STAGNATION_PENALTY" in flags
    assert score < 70


def test_fresh_ignition_beats_stagnant_candidate():
    stagnant, _ = calculate_practical_score({
        "final_score": 90,
        "chip_score": 85,
        "surge_score": 20,
        "close_strength": 0.8,
        "surge_metrics": {
            "return3_pct": 0.2,
            "return5_pct": 0.6,
            "return10_pct": 1.0,
        },
    })
    ignition, flags = calculate_practical_score({
        "final_score": 76,
        "chip_score": 70,
        "surge_score": 68,
        "close_strength": 0.9,
        "surge_flags": ["VOLUME_EXPANSION"],
        "surge_metrics": {
            "return3_pct": 3.0,
            "return5_pct": 4.5,
            "return10_pct": 7.0,
            "fresh_ignition": True,
            "early_main_move": False,
            "overextended": False,
            "trend_accelerator": True,
        },
    })
    assert "FRESH_IGNITION_BONUS" in flags
    assert ignition > stagnant


def test_weak_ignition_is_not_given_full_breakout_bonus():
    score, flags = calculate_practical_score({
        "final_score": 80,
        "chip_score": 78,
        "surge_score": 66,
        "close_strength": 0.52,
        "surge_flags": [],
        "surge_metrics": {
            "return3_pct": 2.8,
            "return5_pct": 3.6,
            "return10_pct": 5.1,
            "fresh_ignition": True,
            "early_main_move": False,
            "overextended": False,
            "trend_accelerator": False,
        },
    })
    assert "FRESH_IGNITION_BONUS" not in flags
    assert "FALSE_BREAKOUT_RISK_PENALTY" in flags
    assert "WEAK_IGNITION_CONFIRMATION" in flags
    assert score < 80


def test_fast_move_with_weak_close_gets_rejection_penalty():
    _, flags = calculate_practical_score({
        "final_score": 78,
        "chip_score": 75,
        "surge_score": 70,
        "close_strength": 0.48,
        "surge_flags": [],
        "surge_metrics": {
            "return3_pct": 5.2,
            "return5_pct": 7.0,
            "return10_pct": 10.0,
            "fresh_ignition": False,
            "early_main_move": False,
            "overextended": False,
            "trend_accelerator": True,
        },
    })
    assert "LATE_REJECTION_PENALTY" in flags


def test_overextended_candidate_is_penalized():
    score, flags = calculate_practical_score({
        "final_score": 88,
        "chip_score": 95,
        "surge_score": 100,
        "close_strength": 0.95,
        "surge_stage": "X級：延伸過熱/不追",
        "surge_metrics": {
            "return3_pct": 9,
            "return5_pct": 16,
            "return10_pct": 35,
            "overextended": True,
            "trend_accelerator": True,
        },
    })
    assert "OVEREXTENDED_PENALTY" in flags
    assert score < 90
