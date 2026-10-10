from taiwan_stock_agent.domain.dynamic_exposure import dynamic_exposure_policy


def test_trend_expansion_allows_high_exposure():
    out = dynamic_exposure_policy({
        "market_state": "broad_rally",
        "market_breadth": 82,
        "market_return_5d": 4.0,
    })
    assert out["regime_v2"] == "trend_expansion"
    assert out["max_total_exposure"] == 0.90
    assert out["max_sector_exposure"] == 0.50


def test_range_market_reduces_exposure():
    out = dynamic_exposure_policy({
        "market_state": "mixed",
        "market_breadth": 50,
        "market_return_5d": 0.2,
    })
    assert out["regime_v2"] == "range_or_mixed"
    assert out["max_total_exposure"] == 0.75
    assert out["max_sector_exposure"] == 0.40


def test_selloff_forces_defensive_exposure():
    out = dynamic_exposure_policy({
        "market_state": "broad_selloff",
        "market_breadth": 20,
        "market_return_5d": -6.0,
    })
    assert out["regime_v2"] == "panic_or_selloff"
    assert out["max_total_exposure"] == 0.45
    assert out["max_sector_exposure"] == 0.25


def test_user_caps_remain_hard_ceiling():
    out = dynamic_exposure_policy(
        {
            "market_state": "broad_rally",
            "market_breadth": 82,
            "market_return_5d": 4.0,
        },
        base_max_total=0.70,
        base_max_sector=0.35,
    )
    assert out["max_total_exposure"] == 0.70
    assert out["max_sector_exposure"] == 0.35
