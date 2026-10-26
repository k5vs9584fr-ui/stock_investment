from taiwan_stock_agent.domain.score_confidence import score_confidence
from taiwan_stock_agent.domain.sector_concentration import apply_sector_concentration


def test_score_confidence_detects_conflict():
    c = score_confidence({
        "final_score": 92,
        "practical_score": 58,
        "top3_quality_score": 55,
    })
    assert c["level"] == "CONFLICT"
    assert c["position_multiplier"] < 0.5


def test_score_confidence_high_when_models_agree():
    c = score_confidence({
        "final_score": 82,
        "practical_score": 79,
        "top3_quality_score": 84,
    })
    assert c["level"] == "HIGH"


def test_sector_cap_limits_same_industry():
    rows = [
        {"industry_code": "24", "allocation_weight": 0.40},
        {"industry_code": "24", "allocation_weight": 0.33},
        {"industry_code": "25", "allocation_weight": 0.27},
    ]
    out = apply_sector_concentration(rows, max_sector_weight=0.50)
    assert out[0]["allocation_weight_sector_capped"] == 0.40
    assert out[1]["allocation_weight_sector_capped"] == 0.10
    assert out[1]["sector_cap_applied"] is True
    assert out[2]["allocation_weight_sector_capped"] == 0.27
