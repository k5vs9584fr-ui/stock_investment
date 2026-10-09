from taiwan_stock_agent.domain.opening_gate import (
    opening_confirmation_score,
    opening_eligibility,
    promote_opening_candidates,
)


def test_opening_gate_keeps_pending_data_neutral():
    ok, reasons = opening_eligibility({"hybrid_action_score": 90, "dt_metrics": {}})
    assert ok is True
    assert reasons == ["OPEN_DATA_PENDING"]


def test_opening_gate_rejects_failed_open():
    ok, reasons = opening_eligibility({
        "price": 98,
        "dt_metrics": {
            "vwap_gap_pct": -1.1,
            "return_15m_pct": -1.5,
            "volume_accel_5m": 0.5,
            "near_intraday_high": 0.92,
            "recent_support": 99,
        },
    })
    assert ok is False
    assert "OPEN_FAIL_BELOW_VWAP" in reasons
    assert "OPEN_FAIL_MOMENTUM" in reasons


def test_opening_confirmation_rewards_vwap_volume_and_high_hold():
    score, reasons = opening_confirmation_score({
        "opening_reorder_score": 82,
        "hybrid_action_score": 82,
        "dt_metrics": {
            "vwap_gap_pct": 0.8,
            "return_15m_pct": 1.1,
            "volume_accel_5m": 1.8,
            "near_intraday_high": 0.993,
        },
    })
    assert score > 82
    assert "OPEN_ABOVE_VWAP" in reasons
    assert "OPEN_NEAR_HIGH" in reasons


def test_promote_replaces_rejected_top3_with_next_best():
    rows = [
        {"symbol":"A","industry_code":"24","hybrid_action_score":95,"dt_metrics":{"vwap_gap_pct":-1.2,"return_15m_pct":-1.3,"volume_accel_5m":0.5,"near_intraday_high":0.92}},
        {"symbol":"B","industry_code":"24","hybrid_action_score":92,"dt_metrics":{"vwap_gap_pct":0.5,"return_15m_pct":0.8,"volume_accel_5m":1.4,"near_intraday_high":0.99}},
        {"symbol":"C","industry_code":"27","hybrid_action_score":90,"dt_metrics":{"vwap_gap_pct":0.2,"return_15m_pct":0.4,"volume_accel_5m":1.2,"near_intraday_high":0.98}},
        {"symbol":"D","industry_code":"24","hybrid_action_score":88,"dt_metrics":{"vwap_gap_pct":0.7,"return_15m_pct":1.0,"volume_accel_5m":1.8,"near_intraday_high":0.995}},
    ]
    selected, rejected = promote_opening_candidates(rows, target_n=3)
    assert {x["symbol"] for x in selected} == {"B","C","D"}
    assert [x["symbol"] for x in rejected] == ["A"]


def test_live_rank_can_promote_better_confirmed_name():
    rows = [
        {"symbol":"A","industry_code":"24","hybrid_action_score":94,"dt_metrics":{"vwap_gap_pct":4.5,"return_15m_pct":5.5,"volume_accel_5m":0.7,"near_intraday_high":0.95}},
        {"symbol":"B","industry_code":"27","hybrid_action_score":90,"dt_metrics":{"vwap_gap_pct":0.8,"return_15m_pct":1.1,"volume_accel_5m":1.8,"near_intraday_high":0.995}},
    ]
    selected, _ = promote_opening_candidates(rows, target_n=2)
    assert [x["symbol"] for x in selected] == ["B","A"]


def test_sector_cap_prefers_diversified_third_name():
    rows = [
        {"symbol":"A","industry_code":"24","hybrid_action_score":95,"dt_metrics":{"vwap_gap_pct":0.5,"return_15m_pct":1.0,"volume_accel_5m":1.8,"near_intraday_high":0.995}},
        {"symbol":"B","industry_code":"24","hybrid_action_score":93,"dt_metrics":{"vwap_gap_pct":0.6,"return_15m_pct":1.0,"volume_accel_5m":1.7,"near_intraday_high":0.994}},
        {"symbol":"C","industry_code":"24","hybrid_action_score":92,"dt_metrics":{"vwap_gap_pct":0.7,"return_15m_pct":1.0,"volume_accel_5m":1.6,"near_intraday_high":0.993}},
        {"symbol":"D","industry_code":"27","hybrid_action_score":89,"dt_metrics":{"vwap_gap_pct":0.6,"return_15m_pct":0.8,"volume_accel_5m":1.4,"near_intraday_high":0.99}},
    ]
    selected, _ = promote_opening_candidates(rows, target_n=3, max_per_sector=2)
    assert [x["symbol"] for x in selected] == ["A","B","D"]


def test_phase_is_written_to_selected_rows():
    rows = [{
        "symbol":"A",
        "industry_code":"24",
        "hybrid_action_score":90,
        "dt_metrics":{"vwap_gap_pct":0.5,"return_5m_pct":0.7,"return_15m_pct":0.8,"volume_accel_5m":1.8,"near_intraday_high":0.99},
    }]
    selected, _ = promote_opening_candidates(rows, target_n=1, phase_minutes=5)
    assert selected[0]["opening_phase_minutes"] == 5


def test_failed_fresh_ignition_drops_below_confirmed_candidate_at_30m():
    rows = [
        {
            "symbol":"HOT",
            "industry_code":"24",
            "hybrid_action_score":96,
            "surge_score":84,
            "surge_stage":"S級：首發動可追",
            "surge_flags":["FRESH_IGNITION_CHASABLE","VOLUME_EXPANSION"],
            "surge_metrics":{
                "return3_pct":2.6,
                "return5_pct":4.1,
                "return10_pct":5.0,
                "fresh_ignition":True,
                "early_main_move":False,
                "trend_accelerator":False,
                "overextended":False,
                "chaseable":True,
                "volume3_vs_20":1.8,
            },
            "dt_metrics":{
                "vwap_gap_pct":-0.7,
                "return_15m_pct":-0.4,
                "return_30m_pct":-0.3,
                "volume_accel_5m":0.6,
                "near_intraday_high":0.93,
            },
        },
        {
            "symbol":"GOOD",
            "industry_code":"27",
            "hybrid_action_score":88,
            "surge_score":65,
            "surge_stage":"A級：剛發動",
            "surge_flags":["VOLUME_EXPANSION"],
            "surge_metrics":{
                "return3_pct":1.8,
                "return5_pct":3.2,
                "return10_pct":4.0,
                "fresh_ignition":False,
                "early_main_move":False,
                "trend_accelerator":True,
                "overextended":False,
                "chaseable":True,
                "volume3_vs_20":1.6,
            },
            "dt_metrics":{
                "vwap_gap_pct":0.6,
                "return_15m_pct":1.0,
                "return_30m_pct":1.5,
                "volume_accel_5m":1.5,
                "near_intraday_high":0.99,
            },
        },
    ]
    selected, _ = promote_opening_candidates(rows, target_n=2, phase_minutes=30)
    assert [x["symbol"] for x in selected] == ["GOOD","HOT"]
    assert selected[1]["opening_confirmation_score"] <= 59
