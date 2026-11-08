from taiwan_stock_agent.domain.chip_persistence import chip_persistence_overlay
from taiwan_stock_agent.domain.segmented_risk import normalize_industry, segmented_risk_adjustment


def test_current_chip_schema_is_supported():
    bonus, flags = chip_persistence_overlay({
        "chip_flags": [
            "INST_CONSEC_2D",
            "INST_BUY_2_OF_3",
            "INST_CUMUL_5D_POS",
            "MARGIN_DECLINING",
        ],
        "chip_metrics": {
            "available": True,
            "latest": {
                "foreign": 1168886,
                "trust": 20000,
                "dealer": -28963,
                "inst": 1188886,
            },
            "foreign_consecutive_buy_days": 2,
            "trust_consecutive_buy_days": 1,
            "inst_cumul_5d": 2146704,
            "margin_change": -11,
        },
    })
    assert bonus > 0
    assert "FOREIGN_PERSISTENT_SHORT" in flags
    assert "INST_PERSISTENT_CONSENSUS_SHORT" in flags
    assert "SMART_MONEY_WITH_MARGIN_CLEANUP" in flags


def test_industry_code_normalization():
    assert normalize_industry("24") == "半導體業"
    assert normalize_industry("27") == "通信網路業"


def test_segmented_risk_uses_normalized_industry_code():
    stats = {
        "by_pattern": {},
        "industry_pattern": {
            "半導體業|BREAKOUT_20D": {"n": 12, "failure_rate": 25.0}
        },
    }
    score, flags = segmented_risk_adjustment("24", ["BREAKOUT_20D:100>98"], stats)
    assert score > 0
    assert any("INDUSTRY_PATTERN_LOW_FAIL" in x for x in flags)
