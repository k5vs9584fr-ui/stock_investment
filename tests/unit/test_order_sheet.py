from taiwan_stock_agent.domain.order_sheet import build_order_sheet


def test_buy_order_calculates_board_lots_and_odd_lot_shares():
    out = build_order_sheet(
        execution_plan={"orders":[{
            "symbol":"8150",
            "side":"BUY",
            "source":"FRESH_TOP3",
            "weight":0.30,
            "trigger":130.5,
        }]},
        ranked_rows=[{
            "symbol":"8150",
            "name":"南茂",
            "price":128.0,
            "entry_exit_plan":{
                "entry_trigger":130.5,
                "exit_rules":{"hard_stop":124.5},
            },
        }],
        holdings=[],
        portfolio_value=500000,
    )
    order = out["orders"][0]
    assert order["shares"] == 1149
    assert order["board_lots"] == 1
    assert order["odd_lot_shares"] == 149
    assert order["trigger_price"] == 130.5
    assert order["hard_stop"] == 124.5
    assert out["ready_order_count"] == 1


def test_missing_portfolio_value_keeps_weight_only_mode():
    out = build_order_sheet(
        execution_plan={"orders":[{
            "symbol":"3706",
            "side":"BUY",
            "source":"FRESH_TOP3",
            "weight":0.20,
            "trigger":82.1,
        }]},
        ranked_rows=[{"symbol":"3706","name":"神達","price":80.9}],
        holdings=[],
        portfolio_value=None,
    )
    order = out["orders"][0]
    assert order["shares"] is None
    assert order["sizing_mode"] == "WEIGHT_ONLY"
    assert out["weight_only_count"] == 1


def test_sell_order_uses_existing_explicit_share_count():
    out = build_order_sheet(
        execution_plan={"orders":[{
            "symbol":"H",
            "side":"SELL",
            "source":"DEFENSIVE_REDUCTION",
            "weight":0.20,
            "shares":500,
        }]},
        ranked_rows=[],
        holdings=[{"symbol":"H","name":"H","shares":1000}],
        portfolio_value=500000,
    )
    order = out["orders"][0]
    assert order["shares"] == 500
    assert order["odd_lot_shares"] == 500
