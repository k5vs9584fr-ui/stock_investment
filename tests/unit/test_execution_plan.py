from taiwan_stock_agent.domain.execution_plan import build_execution_plan


def test_same_symbol_sell_is_deduplicated_using_larger_weight():
    out = build_execution_plan(
        top_candidates=[],
        capital_plan={"positions":[]},
        holding_weights={"H":0.40},
        selected_rotations=[{
            "held_symbol":"H",
            "challenger_symbol":"C",
            "action":"ROTATE",
            "position_plan":{"sell_weight":0.40,"buy_weight":0.30},
        }],
        defensive_reduction_plan={
            "actions":[{"symbol":"H","reduce_weight":0.20,"reduce_shares":500,"reason":"TOTAL_EXPOSURE_EXCESS"}]
        },
    )
    sells = [x for x in out["orders"] if x["side"] == "SELL" and x["symbol"] == "H"]
    assert len(sells) == 1
    assert sells[0]["weight"] == 0.40
    assert sells[0]["source"] == "ROTATION"


def test_rotation_buy_is_not_duplicated_by_fresh_top3_buy():
    out = build_execution_plan(
        top_candidates=[{
            "symbol":"C",
            "explosive_label":"主升初段",
            "entry_trigger":101,
        }],
        capital_plan={"positions":[{"symbol":"C","final_weight":0.40}]},
        holding_weights={"H":0.40},
        selected_rotations=[{
            "held_symbol":"H",
            "challenger_symbol":"C",
            "action":"ROTATE",
            "position_plan":{"sell_weight":0.40,"buy_weight":0.30},
        }],
        defensive_reduction_plan={"actions":[]},
    )
    buys = [x for x in out["orders"] if x["side"] == "BUY" and x["symbol"] == "C"]
    assert len(buys) == 1
    assert buys[0]["source"] == "ROTATION"
    assert buys[0]["weight"] == 0.30


def test_fresh_top3_buy_uses_only_target_gap():
    out = build_execution_plan(
        top_candidates=[{
            "symbol":"A",
            "explosive_label":"首發動",
            "entry_trigger":50,
        }],
        capital_plan={"positions":[{"symbol":"A","final_weight":0.40}]},
        holding_weights={"A":0.15},
        selected_rotations=[],
        defensive_reduction_plan={"actions":[]},
    )
    buys = [x for x in out["orders"] if x["side"] == "BUY" and x["symbol"] == "A"]
    assert len(buys) == 1
    assert buys[0]["weight"] == 0.25
