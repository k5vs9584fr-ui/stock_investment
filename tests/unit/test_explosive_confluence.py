from taiwan_stock_agent.domain.explosive_confluence import explosive_confluence_adjustment


def test_triple_confirm_explosive_setup_gets_bonus():
    row = {
        "surge_score": 88,
        "surge_stage": "S+級：主升初段可追",
        "surge_metrics": {
            "early_main_move": True,
            "fresh_ignition": False,
            "trend_accelerator": False,
            "overextended": False,
        },
        "catalyst_type": "revenue",
        "catalyst_strength": 85,
        "catalyst_age_days": 1,
        "chip_metrics": {
            "days": 5,
            "foreign_5d": 3000,
            "foreign_buy_days": 3,
            "trust_5d": 800,
            "trust_buy_days": 2,
            "inst_total_5d": 4200,
            "inst_buy_days": 3,
        },
    }
    bonus, flags = explosive_confluence_adjustment(row)
    assert bonus >= 10
    assert "CONFLUENCE_TRIPLE_CONFIRM" in flags


def test_explosive_pattern_is_penalized_on_institutional_reversal():
    row = {
        "surge_score": 78,
        "surge_stage": "S級：首發動可追",
        "surge_metrics": {
            "fresh_ignition": True,
            "early_main_move": False,
            "trend_accelerator": False,
            "overextended": False,
        },
        "chip_metrics": {
            "days": 5,
            "foreign_5d": -5000,
            "foreign_buy_days": 1,
            "trust_5d": 0,
            "trust_buy_days": 0,
            "inst_total_5d": -5200,
            "inst_buy_days": 1,
        },
    }
    bonus, flags = explosive_confluence_adjustment(row)
    assert bonus <= -8
    assert "CONFLUENCE_INSTITUTIONAL_REVERSAL" in flags


def test_preignition_with_fresh_catalyst_and_positive_chips_gets_small_bonus():
    row = {
        "surge_score": 45,
        "surge_stage": "B級：非飆股型",
        "surge_metrics": {
            "fresh_ignition": False,
            "early_main_move": False,
            "trend_accelerator": False,
            "overextended": False,
        },
        "catalyst_type": "earnings",
        "catalyst_strength": 70,
        "catalyst_age_days": 2,
        "chip_metrics": {
            "days": 5,
            "foreign_5d": 1200,
            "foreign_buy_days": 2,
            "inst_total_5d": 1500,
            "inst_buy_days": 2,
        },
    }
    bonus, flags = explosive_confluence_adjustment(row)
    assert bonus >= 2
    assert "CONFLUENCE_PREIGNITION_CATALYST_CHIPS" in flags
