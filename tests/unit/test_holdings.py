from pathlib import Path

from taiwan_stock_agent.domain.holdings import load_holdings, enrich_holdings


def test_missing_holdings_file_is_safe(tmp_path):
    assert load_holdings(tmp_path / "missing.json") == []


def test_load_holdings_accepts_wrapped_schema(tmp_path):
    p = tmp_path / "holdings.json"
    p.write_text(
        '{"holdings":[{"symbol":"2303","name":"聯電","cost":148.5,"shares":300}]}',
        encoding="utf-8",
    )
    out = load_holdings(p)
    assert out[0]["symbol"] == "2303"
    assert out[0]["cost"] == 148.5
    assert out[0]["shares"] == 300


def test_enrich_holdings_matches_current_ranked_row():
    holdings = [{"symbol":"2303","cost":148.5,"shares":300,"name":"聯電"}]
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
    assert out[0]["position_decision"]["mode"] == "EXISTING_POSITION"


def test_unmatched_holding_is_not_fabricated():
    holdings = [{"symbol":"9999","cost":10,"shares":100,"name":"X"}]
    out = enrich_holdings(holdings, [])
    assert out[0]["matched"] is False
    assert out[0]["position_decision"]["action"] == "NO_CURRENT_SIGNAL"
