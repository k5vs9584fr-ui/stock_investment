from taiwan_stock_agent.domain.action_tier import action_tier, allocation_weight
from taiwan_stock_agent.domain.leadership_overlay import leadership_overlay
from taiwan_stock_agent.domain.position_decision import position_decision


def test_action_tier_uses_action_score_scale():
    assert action_tier(1, 82) == "PRIMARY_TOP3"
    assert action_tier(3, 71.9) == "SECONDARY_TOP5"
    assert action_tier(4, 70) == "SECONDARY_TOP5"


def test_primary_weights_still_sum_to_one():
    total = sum(allocation_weight(i, 85) for i in (1, 2, 3))
    assert round(total, 2) == 1.00


def test_leadership_rewards_strong_industry_and_rs():
    bonus, flags = leadership_overlay({
        "industry_rank_pct": 90,
        "relative_strength_pct": 6,
        "hot_concepts": ["AI伺服器"],
    })
    assert bonus >= 9
    assert "INDUSTRY_LEADER" in flags
    assert "MARKET_RS_LEADER" in flags


def test_popular_but_laggard_is_penalized():
    bonus, flags = leadership_overlay({
        "industry_rank_pct": 10,
        "relative_strength_pct": -4,
    })
    assert bonus < 0
    assert "INDUSTRY_LAGGARD" in flags
    assert "MARKET_RS_LAGGARD" in flags


def test_existing_position_has_different_decision_from_new_entry():
    row = {
        "hybrid_action_score": 64,
        "practical_score": 58,
        "price": 110,
        "score_confidence": {"level": "LOW"},
        "entry_exit_plan": {},
    }
    new = position_decision(row, held=False)
    held = position_decision(row, held=True, cost=100)
    assert new["action"] == "NO_NEW_POSITION"
    assert held["action"] == "REDUCE_INTO_STRENGTH"
