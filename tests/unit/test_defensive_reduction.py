from taiwan_stock_agent.domain.defensive_reduction import build_defensive_reduction_plan


def test_reduction_prefers_weaker_holding_over_early_main_move():
    holdings = [
        {
            "symbol":"WEAK","name":"WEAK","hybrid_action_score":62,"practical_score":58,
            "surge_stage":"B級：非飆股型","surge_metrics":{"overextended":False},
        },
        {
            "symbol":"STRONG","name":"STRONG","hybrid_action_score":90,"practical_score":86,
            "surge_stage":"S+級：主升初段可追",
            "surge_metrics":{"early_main_move":True,"overextended":False},
        },
    ]
    out = build_defensive_reduction_plan(
        holdings,
        holding_weights={"WEAK":0.35,"STRONG":0.35},
        symbol_sectors={"WEAK":"24","STRONG":"25"},
        max_total_exposure=0.50,
        max_sector_exposure=0.50,
    )
    assert out["needs_reduction"] is True
    assert out["actions"][0]["symbol"] == "WEAK"


def test_sector_excess_is_reduced_from_overweight_sector():
    holdings = [
        {"symbol":"A","hybrid_action_score":70,"practical_score":68,"surge_metrics":{"overextended":False}},
        {"symbol":"B","hybrid_action_score":75,"practical_score":72,"surge_metrics":{"overextended":False}},
        {"symbol":"C","hybrid_action_score":88,"practical_score":84,"surge_metrics":{"overextended":False}},
    ]
    out = build_defensive_reduction_plan(
        holdings,
        holding_weights={"A":0.30,"B":0.25,"C":0.20},
        symbol_sectors={"A":"24","B":"24","C":"27"},
        max_total_exposure=0.90,
        max_sector_exposure=0.40,
    )
    assert out["sector_excess"]["24"] == 0.15
    assert out["actions"]
    assert out["actions"][0]["sector"] == "24"


def test_no_reduction_when_within_limits():
    out = build_defensive_reduction_plan(
        [{"symbol":"A","hybrid_action_score":80,"practical_score":78,"surge_metrics":{"overextended":False}}],
        holding_weights={"A":0.30},
        symbol_sectors={"A":"24"},
        max_total_exposure=0.75,
        max_sector_exposure=0.40,
    )
    assert out["needs_reduction"] is False
    assert out["actions"] == []


def test_post_reduction_exposure_returns_within_limits():
    holdings = [
        {"symbol":"A","hybrid_action_score":62,"practical_score":60,"surge_metrics":{"overextended":False}},
        {"symbol":"B","hybrid_action_score":74,"practical_score":70,"surge_metrics":{"overextended":False}},
        {"symbol":"C","hybrid_action_score":88,"practical_score":84,"surge_metrics":{"fresh_ignition":True,"overextended":False}},
    ]
    out = build_defensive_reduction_plan(
        holdings,
        holding_weights={"A":0.30,"B":0.25,"C":0.25},
        symbol_sectors={"A":"24","B":"24","C":"25"},
        max_total_exposure=0.60,
        max_sector_exposure=0.35,
    )
    assert out["needs_reduction"] is True
    assert out["post_reduction_total_exposure"] <= 0.60
    assert out["post_reduction_sector_exposure"]["24"] <= 0.35
    assert out["total_reduce_weight"] >= 0.20
