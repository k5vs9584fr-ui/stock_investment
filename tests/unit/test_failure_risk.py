from taiwan_stock_agent.domain.failure_risk import failure_risk_overlay


def test_hot_rsi_penalty():
    score, flags = failure_risk_overlay({"surge_flags": ["RSI_HOT:78.0"]})
    assert score < 0
    assert "FAILURE_RISK_RSI_HOT" in flags


def test_hyperchase_penalty():
    score, flags = failure_risk_overlay({"surge_flags": ["VOL_HYPERCHASE:5.2x"]})
    assert score < 0
    assert "FAILURE_RISK_VOL_HYPERCHASE" in flags


def test_heat_combo_penalty_is_stronger():
    score, flags = failure_risk_overlay({
        "surge_flags": ["RSI_HOT:80.0", "VOL_HYPERCHASE:6.0x"]
    })
    assert score <= -12
    assert "FAILURE_RISK_HEAT_COMBO" in flags
