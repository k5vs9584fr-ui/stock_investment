from pathlib import Path

from taiwan_stock_agent.domain.live_capital import live_capital_plan
from taiwan_stock_agent.domain.holdings import load_holdings, enrich_holdings


def _row(symbol, industry, confidence="HIGH"):
    return {
        "symbol": symbol,
        "name": symbol,
        "industry_code": industry,
        "score_confidence": {"level": confidence},
    }


def test_sector_cap():
    plan = live_capital_plan([
        _row("A","24"),
        _row("B","24"),
        _row("C","25"),
    ])
    same_sector = sum(
        x["final_weight"] for x in plan["positions"] if x["sector"] == "24"
    )
    assert round(same_sector, 4) <= 0.50


def test_low_confidence_scales_weight():
    high = live_capital_plan([_row("A","24","HIGH")])
    low = live_capital_plan([_row("A","24","LOW")])
    assert low["positions"][0]["final_weight"] < high["positions"][0]["final_weight"]


def test_unused_capital_remains_cash():
    plan = live_capital_plan([_row("A","24")])
    assert plan["cash_weight"] > 0
    assert round(plan["deployed_weight"] + plan["cash_weight"], 4) == 1.0


def test_oos_multiplier_scales_position():
    plan = live_capital_plan(
        [_row("A","24")],
        oos_guard={"position_multiplier":0.70},
    )
    assert plan["positions"][0]["final_weight"] == 0.28


def test_missing_holdings_file_is_safe(tmp_path):
    assert load_holdings(tmp_path / "missing.json") == []


def test_holdings_match_current_scan(tmp_path):
    p = tmp_path / "holdings.json"
    p.write_text(
        '{"holdings":[{"symbol":"2303","name":"聯電","cost":148.5,"shares":300}]}',
        encoding="utf-8",
    )
    holdings = load_holdings(p)
    ranked = [{
        "symbol":"2303",
        "name":"聯電",
        "price":150,
        "hybrid_action_score":80,
        "practical_score":78,
        "score_confidence":{"level":"MEDIUM"},
        "entry_exit_plan":{},
    }]
    out = enrich_holdings(holdings, ranked)
    assert out[0]["matched"] is True
    assert out[0]["cost"] == 148.5
    assert out[0]["position_decision"]["mode"] == "EXISTING_POSITION"


def test_unmatched_holding_is_never_fabricated():
    out = enrich_holdings(
        [{"symbol":"9999","cost":10,"shares":100,"name":"X"}],
        [],
    )
    assert out[0]["matched"] is False
    assert out[0]["position_decision"]["action"] == "NO_CURRENT_SIGNAL"


def test_rotation_cost_only_downgrades_marginal_edge():
    from taiwan_stock_agent.domain.rotation_cost import cost_adjusted_rotation
    out = cost_adjusted_rotation(
        {"edge": 8.5, "action": "ROTATE"},
        cost_pct=0.785,
    )
    assert out["net_edge"] < 8.5
    assert out["action_after_cost"] in {"WATCH_ROTATION", "KEEP_CURRENT"}


def test_strong_rotation_survives_cost():
    from taiwan_stock_agent.domain.rotation_cost import cost_adjusted_rotation
    out = cost_adjusted_rotation(
        {"edge": 15.0, "action": "ROTATE"},
        cost_pct=0.785,
    )
    assert out["action_after_cost"] == "ROTATE"


def test_keep_never_upgrades_from_cost_adjustment():
    from taiwan_stock_agent.domain.rotation_cost import cost_adjusted_rotation
    out = cost_adjusted_rotation(
        {"edge": 1.0, "action": "KEEP_CURRENT"},
        cost_pct=0.0,
    )
    assert out["action_after_cost"] == "KEEP_CURRENT"


def test_same_sector_rotation_is_penalized():
    from taiwan_stock_agent.domain.rotation_risk import rotation_risk_adjustment
    held = {"industry_code":"24"}
    challenger = {"industry_code":"24"}
    out = rotation_risk_adjustment(
        held,
        challenger,
        {"net_edge":9.0,"action_after_cost":"ROTATE"},
    )
    assert out["risk_adjustment"] < 0
    assert "ROTATION_SAME_SECTOR" in out["rotation_risk_reasons"]
    assert out["action_after_risk"] != "ROTATE"


def test_cross_sector_rotation_gets_diversification_bonus():
    from taiwan_stock_agent.domain.rotation_risk import rotation_risk_adjustment
    held = {"industry_code":"24"}
    challenger = {"industry_code":"27"}
    out = rotation_risk_adjustment(
        held,
        challenger,
        {"net_edge":6.5,"action_after_cost":"WATCH_ROTATION"},
    )
    assert out["risk_adjustment"] > 0
    assert "ROTATION_DIVERSIFICATION_BONUS" in out["rotation_risk_reasons"]
    assert out["risk_adjusted_edge"] > 6.5


def test_theme_overlap_penalizes_rotation():
    from taiwan_stock_agent.domain.rotation_risk import rotation_risk_adjustment
    held = {"industry_code":"24","hot_concepts":["AI","HBM"]}
    challenger = {"industry_code":"27","hot_concepts":["AI"]}
    out = rotation_risk_adjustment(
        held,
        challenger,
        {"net_edge":8.5,"action_after_cost":"ROTATE"},
    )
    assert "ROTATION_THEME_OVERLAP" in out["rotation_risk_reasons"]
    assert out["risk_adjustment"] == 0.0


def _rotation_row(symbol, sector, hybrid, practical, surge, dt):
    return {
        "symbol": symbol,
        "industry_code": sector,
        "hybrid_action_score": hybrid,
        "practical_score": practical,
        "surge_score": surge,
        "score_confidence": {"level": "HIGH"},
        "risk_policy": {"max_position_pct": 20},
        "dt_metrics": dt,
    }


def test_live_rotation_switches_only_when_edge_survives_all_layers():
    from taiwan_stock_agent.domain.live_rotation import live_rotation_decision
    held = _rotation_row("H", "24", 70, 68, 55, {
        "vwap_gap_pct": -0.4,
        "return_15m_pct": -0.2,
        "volume_accel_5m": 0.9,
        "near_intraday_high": 0.97,
    })
    challenger = _rotation_row("C", "27", 90, 88, 82, {
        "vwap_gap_pct": 0.8,
        "return_15m_pct": 1.2,
        "volume_accel_5m": 1.8,
        "near_intraday_high": 0.995,
    })
    out = live_rotation_decision(held, challenger, cost_pct=0.5)
    assert out["final_action"] == "ROTATE"
    assert out["live_rotation_edge"] >= 8


def test_live_rotation_forbids_chasing_missed_entry():
    from taiwan_stock_agent.domain.live_rotation import live_rotation_decision
    held = _rotation_row("H", "24", 72, 70, 60, {
        "vwap_gap_pct": 0.1,
        "return_15m_pct": 0.2,
        "volume_accel_5m": 1.0,
        "near_intraday_high": 0.98,
    })
    challenger = _rotation_row("C", "27", 95, 92, 90, {
        "vwap_gap_pct": 4.6,
        "planned_entry_gap_pct": 4.0,
        "return_15m_pct": 5.2,
        "volume_accel_5m": 1.8,
        "near_intraday_high": 0.998,
    })
    out = live_rotation_decision(held, challenger, cost_pct=0.0)
    assert out["final_action"] == "KEEP_CURRENT"
    assert "ROTATION_NO_CHASE" in out["live_rotation_reasons"]
    assert out["chase_flags"]


def test_live_rotation_rejects_failed_open_even_with_high_model_score():
    from taiwan_stock_agent.domain.live_rotation import live_rotation_decision
    held = _rotation_row("H", "24", 75, 74, 62, {
        "vwap_gap_pct": 0.2,
        "return_15m_pct": 0.3,
        "volume_accel_5m": 1.1,
        "near_intraday_high": 0.98,
    })
    challenger = _rotation_row("C", "27", 96, 94, 90, {
        "vwap_gap_pct": -1.2,
        "return_15m_pct": -1.5,
        "volume_accel_5m": 0.5,
        "near_intraday_high": 0.92,
    })
    out = live_rotation_decision(held, challenger, cost_pct=0.0)
    assert out["final_action"] == "KEEP_CURRENT"
    assert "ROTATION_CHALLENGER_OPEN_FAIL" in out["live_rotation_reasons"]
