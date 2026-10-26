from taiwan_stock_agent.domain.chip_persistence import chip_persistence_overlay
from taiwan_stock_agent.domain.hybrid_action_score import hybrid_action_score


def test_persistent_institutional_buying_is_rewarded():
    bonus, flags = chip_persistence_overlay({
        "chip_metrics": {
            "days": 5,
            "foreign_buy_days": 4,
            "foreign_5d": 1000,
            "trust_buy_days": 4,
            "trust_5d": 500,
            "inst_buy_days": 4,
            "inst_total_5d": 1800,
            "margin_change_pct": -1.2,
        }
    })
    assert bonus > 0
    assert "INST_PERSISTENT_CONSENSUS" in flags
    assert "SMART_MONEY_WITH_MARGIN_CLEANUP" in flags


def test_bad_chip_combination_is_penalized():
    bonus, flags = chip_persistence_overlay({
        "chip_metrics": {
            "days": 5,
            "foreign_buy_days": 1,
            "foreign_5d": -1000,
            "trust_buy_days": 0,
            "trust_5d": -500,
            "inst_buy_days": 1,
            "inst_total_5d": -1800,
            "margin_change_pct": 3.0,
        }
    })
    assert bonus < 0
    assert "BAD_CHIP_COMBINATION" in flags


def test_hybrid_action_score_is_balanced():
    assert hybrid_action_score(90, 70) == 80.0
