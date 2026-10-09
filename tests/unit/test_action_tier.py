from taiwan_stock_agent.domain.action_tier import action_tier, allocation_weight


def test_top3_are_primary_when_score_is_actionable():
    assert action_tier(1, 85) == "PRIMARY_TOP3"
    assert action_tier(3, 74) == "PRIMARY_TOP3"


def test_rank4_5_are_secondary():
    assert action_tier(4, 70) == "SECONDARY_TOP5"
    assert action_tier(5, 63) == "SECONDARY_TOP5"


def test_low_score_is_watch_only():
    assert action_tier(2, 60) == "WATCH_ONLY"


def test_primary_weights_sum_to_one():
    total = sum(allocation_weight(i, 80) for i in (1, 2, 3))
    assert round(total, 2) == 1.00
