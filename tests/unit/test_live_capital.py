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
