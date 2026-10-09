from taiwan_stock_agent.domain.live_capital import live_capital_plan


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
