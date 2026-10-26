from taiwan_stock_agent.domain.explosive_lifecycle import classify_explosive_lifecycle


def test_fresh_ignition_is_classified_as_first_launch():
    out = classify_explosive_lifecycle({
        "surge_score": 74,
        "surge_stage": "S級：首發動可追",
        "surge_flags": ["BREAKOUT_20D", "FRESH_IGNITION_CHASABLE"],
        "surge_metrics": {
            "return3_pct": 3.0,
            "return5_pct": 2.5,
            "return10_pct": 3.0,
            "fresh_ignition": True,
            "early_main_move": False,
            "trend_accelerator": False,
            "overextended": False,
            "chaseable": True,
            "volume3_vs_20": 1.6,
        },
    })
    assert out["phase"] == "FRESH_IGNITION"
    assert out["label"] == "首發動"
    assert out["action"] == "ATTACK_ON_CONFIRMATION"


def test_early_main_move_has_highest_priority():
    out = classify_explosive_lifecycle({
        "surge_score": 90,
        "surge_stage": "S+級：主升初段可追",
        "surge_flags": ["EARLY_MAIN_MOVE_CHASABLE"],
        "surge_metrics": {
            "return3_pct": 2.0,
            "return5_pct": 7.0,
            "return10_pct": 15.0,
            "fresh_ignition": False,
            "early_main_move": True,
            "trend_accelerator": False,
            "overextended": False,
            "chaseable": True,
            "volume3_vs_20": 1.4,
        },
    })
    assert out["phase"] == "EARLY_MAIN_MOVE"
    assert out["priority"] == 5
    assert out["action"] == "ATTACK_PULLBACK_OR_BREAKOUT"


def test_overheated_is_always_no_chase():
    out = classify_explosive_lifecycle({
        "surge_score": 98,
        "surge_stage": "X級：延伸過熱/不追",
        "surge_flags": ["CHASE_OVEREXTENDED", "VOLUME_EXPANSION"],
        "surge_metrics": {
            "return3_pct": 8.0,
            "return5_pct": 15.0,
            "return10_pct": 30.0,
            "fresh_ignition": True,
            "early_main_move": True,
            "trend_accelerator": True,
            "overextended": True,
            "chaseable": False,
            "volume3_vs_20": 2.5,
        },
    })
    assert out["phase"] == "OVERHEATED"
    assert out["priority"] == 0
    assert out["score"] == 0.0
    assert out["action"] == "NO_CHASE"
