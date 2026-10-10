from scripts.intraday_orders import merge_live_intraday, derive_holding_weights


def test_merge_live_intraday_overrides_dt_metrics_and_price():
    ranked = [{
        "symbol":"8150",
        "name":"南茂",
        "price":128.5,
        "dt_metrics":{"vwap_gap_pct":0.1},
    }]
    live = {
        "stocks":[{
            "symbol":"8150",
            "price":130.0,
            "dt_score":88,
            "dt_phase":"DT-A：可當沖",
            "dt_metrics":{
                "vwap_gap_pct":0.8,
                "return_15m_pct":1.2,
                "volume_accel_5m":1.6,
                "near_intraday_high":0.995,
            },
        }]
    }
    out = merge_live_intraday(ranked, live)
    assert out[0]["price"] == 130.0
    assert out[0]["dt_metrics"]["vwap_gap_pct"] == 0.8
    assert out[0]["live_overlay"] is True


def test_derive_holding_weights_prefers_explicit_weight():
    holdings = [{"symbol":"H","shares":1000,"weight":0.25}]
    rows = [{"symbol":"H","price":100}]
    out = derive_holding_weights(holdings, rows, portfolio_value=500000)
    assert out["H"] == 0.25


def test_derive_holding_weights_uses_shares_times_live_price():
    holdings = [{"symbol":"H","shares":1000}]
    rows = [{"symbol":"H","price":120}]
    out = derive_holding_weights(holdings, rows, portfolio_value=600000)
    assert out["H"] == 0.20


def test_missing_portfolio_value_does_not_invent_weight():
    holdings = [{"symbol":"H","shares":1000}]
    rows = [{"symbol":"H","price":120}]
    out = derive_holding_weights(holdings, rows, portfolio_value=None)
    assert "H" not in out
