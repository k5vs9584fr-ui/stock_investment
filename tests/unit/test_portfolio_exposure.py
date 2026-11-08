from taiwan_stock_agent.domain.portfolio_exposure import (
    portfolio_exposure_guard,
    rotation_exposure_capacity,
)


def test_portfolio_exposure_guard_tracks_total_and_sector_capacity():
    out = portfolio_exposure_guard(
        holding_weights={"A":0.35,"B":0.30,"C":0.20},
        symbol_sectors={"A":"24","B":"24","C":"27"},
        max_total_exposure=0.90,
        max_sector_exposure=0.50,
    )
    assert out["total_exposure"] == 0.85
    assert out["remaining_total_capacity"] == 0.05
    assert out["sector_exposure"]["24"] == 0.65


def test_rotation_capacity_respects_total_exposure_after_sale():
    out = rotation_exposure_capacity(
        held_symbol="H",
        challenger_symbol="C",
        sell_weight=0.10,
        holding_weights={"H":0.10,"X":0.75},
        symbol_sectors={"H":"24","X":"25","C":"27"},
        max_total_exposure=0.90,
        max_sector_exposure=0.50,
    )
    assert out["total_after_sale"] == 0.75
    assert out["total_capacity"] == 0.15
    assert out["max_buy_capacity"] == 0.15


def test_rotation_capacity_respects_sector_limit():
    out = rotation_exposure_capacity(
        held_symbol="H",
        challenger_symbol="C",
        sell_weight=0.20,
        holding_weights={"H":0.20,"A":0.45,"B":0.20},
        symbol_sectors={"H":"27","A":"24","B":"25","C":"24"},
        max_total_exposure=0.95,
        max_sector_exposure=0.50,
    )
    assert out["sector_after_sale"] == 0.45
    assert out["sector_capacity"] == 0.05
    assert out["max_buy_capacity"] == 0.05
