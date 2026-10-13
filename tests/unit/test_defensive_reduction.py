from taiwan_stock_agent.domain.defensive_reduction import build_defensive_reduction_plan


def _row(symbol, sector, hybrid, practical, dt, phase=None):
    row = {
        "symbol": symbol,
        "name": symbol,
        "industry_code": sector,
        "hybrid_action_score": hybrid,
        "practical_score": practical,
        "dt_metrics": dt,
    }
    if phase == "EARLY_MAIN_MOVE":
        row["surge_stage"] = "S+級：主升初段可追"
        row["surge_metrics"] = {
            "early_main_move": True,
            "fresh_ignition": False,
            "trend_accelerator": False,
            "overextended": False,
        }
    elif phase == "FRESH_IGNITION":
        row["surge_stage"] = "S級：首發動可追"
        row["surge_metrics"] = {
            "early_main_move": False,
            "fresh_ignition": True,
            "trend_accelerator": False,
            "overextended": False,
        }
    return row


def test_failed_open_is_reduced_before_healthy_strong_holding():
    holdings = [
        _row("WEAK", "24", 62, 58, {
            "vwap_gap_pct": -1.1,
            "return_15m_pct": -1.4,
            "volume_accel_5m": 0.5,
            "near_intraday_high": 0.92,
        }),
        _row("STRONG", "25", 90, 86, {
            "vwap_gap_pct": 0.6,
            "return_15m_pct": 1.0,
            "volume_accel_5m": 1.5,
            "near_intraday_high": 0.99,
        }, phase="EARLY_MAIN_MOVE"),
    ]
    out = build_defensive_reduction_plan(
        holdings,
        holding_weights={"WEAK":0.35,"STRONG":0.35},
        symbol_sectors={"WEAK":"24","STRONG":"25"},
        max_total_exposure=0.45,
        max_sector_exposure=0.50,
    )
    assert out["needs_reduction"] is True
    assert out["actions"][0]["symbol"] == "WEAK"
    assert out["actions"][0]["opening_eligible"] is False


def test_healthy_early_main_move_keeps_protected_floor():
    holdings = [
        _row("STRONG", "24", 92, 88, {
            "vwap_gap_pct": 0.5,
            "return_15m_pct": 1.1,
            "volume_accel_5m": 1.6,
            "near_intraday_high": 0.995,
        }, phase="EARLY_MAIN_MOVE"),
    ]
    out = build_defensive_reduction_plan(
        holdings,
        holding_weights={"STRONG":0.40},
        symbol_sectors={"STRONG":"24"},
        max_total_exposure=0.20,
        max_sector_exposure=0.50,
    )
    assert out["actions"]
    action = out["actions"][0]
    assert action["protected_floor"] == 0.15
    assert action["remaining_weight"] >= 0.15


def test_fresh_ignition_keeps_smaller_protected_floor():
    holdings = [
        _row("FRESH", "24", 86, 82, {
            "vwap_gap_pct": 0.4,
            "return_15m_pct": 0.8,
            "volume_accel_5m": 1.4,
            "near_intraday_high": 0.99,
        }, phase="FRESH_IGNITION"),
    ]
    out = build_defensive_reduction_plan(
        holdings,
        holding_weights={"FRESH":0.30},
        symbol_sectors={"FRESH":"24"},
        max_total_exposure=0.15,
        max_sector_exposure=0.50,
    )
    assert out["actions"][0]["protected_floor"] == 0.10
    assert out["actions"][0]["remaining_weight"] >= 0.10


def test_defensive_reduction_returns_executable_share_count():
    holdings = [
        {
            **_row("WEAK", "24", 60, 56, {
                "vwap_gap_pct": -1.0,
                "return_15m_pct": -1.0,
                "volume_accel_5m": 0.6,
                "near_intraday_high": 0.93,
            }),
            "shares": 1000,
        },
    ]
    out = build_defensive_reduction_plan(
        holdings,
        holding_weights={"WEAK":0.40},
        symbol_sectors={"WEAK":"24"},
        max_total_exposure=0.20,
        max_sector_exposure=0.50,
    )
    action = out["actions"][0]
    assert action["reduce_fraction"] == 0.5
    assert action["reduce_shares"] == 500
    assert action["remaining_shares"] == 500
