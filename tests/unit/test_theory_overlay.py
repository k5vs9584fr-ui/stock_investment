from taiwan_stock_agent.domain.theory_overlay import calculate_theory_overlay


def test_oneil_minervini_livermore_alignment_adds_bonus():
    bonus, flags = calculate_theory_overlay({
        "chip_score": 80,
        "close_strength": 0.9,
        "structure_flags": ["NEAR_BREAKOUT", "NOT_EXTENDED_10D", "MA20_RISING"],
        "structure_metrics": {
            "ma_spread_pct": 2.5,
            "vol5_vs_20": 0.7,
            "near_20d_high": 0.97,
            "range20_pct": 14,
        },
        "surge_flags": ["BREAKOUT_20D", "MA_BULL_STACK"],
        "surge_metrics": {
            "return3_pct": 2.0,
            "return5_pct": 5.0,
            "volume3_vs_20": 1.4,
        },
    })
    assert bonus > 0
    assert "ONEIL_LEADER_BREAKOUT" in flags
    assert "MINERVINI_VCP_LIKE_UNCONFIRMED" in flags
    assert "LIVERMORE_PIVOT_CONFIRM" in flags
    assert "WEINSTEIN_STAGE2_PROXY" in flags


def test_wyckoff_effort_without_result_penalizes():
    bonus, flags = calculate_theory_overlay({
        "chip_score": 55,
        "close_strength": 0.45,
        "structure_flags": [],
        "structure_metrics": {
            "ma_spread_pct": 8,
            "vol5_vs_20": 1.6,
            "near_20d_high": 0.7,
            "range20_pct": 25,
        },
        "surge_flags": [],
        "surge_metrics": {
            "return3_pct": 0.2,
            "return5_pct": 1.0,
            "volume3_vs_20": 2.2,
        },
    })
    assert bonus < 0
    assert "WYCKOFF_EFFORT_NO_RESULT_WARNING" in flags
