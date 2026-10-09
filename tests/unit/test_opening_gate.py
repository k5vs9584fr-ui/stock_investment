from taiwan_stock_agent.domain.opening_gate import opening_eligibility, promote_opening_candidates


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


def test_promote_replaces_rejected_top3_with_next_best():
    rows = [
        {"symbol":"A","hybrid_action_score":95,"opening_reorder_score":96,"dt_metrics":{"vwap_gap_pct":-1.2,"return_15m_pct":-1.3,"volume_accel_5m":0.5,"near_intraday_high":0.92}},
        {"symbol":"B","hybrid_action_score":92,"opening_reorder_score":93,"dt_metrics":{"vwap_gap_pct":0.5,"return_15m_pct":0.8,"volume_accel_5m":1.4,"near_intraday_high":0.99}},
        {"symbol":"C","hybrid_action_score":90,"opening_reorder_score":91,"dt_metrics":{"vwap_gap_pct":0.2,"return_15m_pct":0.4,"volume_accel_5m":1.2,"near_intraday_high":0.98}},
        {"symbol":"D","hybrid_action_score":88,"opening_reorder_score":94,"dt_metrics":{"vwap_gap_pct":0.7,"return_15m_pct":1.0,"volume_accel_5m":1.8,"near_intraday_high":0.995}},
    ]
    selected, rejected = promote_opening_candidates(rows, target_n=3)
    assert [x["symbol"] for x in selected] == ["D","B","C"]
    assert [x["symbol"] for x in rejected] == ["A"]
