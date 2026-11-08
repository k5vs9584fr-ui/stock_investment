from datetime import date

import pandas as pd

from taiwan_stock_agent.domain.oos_settlement import extract_future_ohlc, settle_row


def test_extract_future_ohlc_excludes_signal_day():
    df = pd.DataFrame(
        {
            "Close": [100, 102, 103],
            "High": [101, 103, 104],
            "Low": [99, 101, 102],
        },
        index=pd.to_datetime(["2026-10-09", "2026-10-12", "2026-10-13"]),
    )
    out = extract_future_ohlc(df, date(2026, 10, 9))
    assert len(out) == 2
    assert out[0]["date"] == "2026-10-12"


def test_settlement_waits_for_enough_trading_days():
    row = {
        "close_price": "100",
        "resolved_t1": "false",
        "resolved_t3": "false",
        "resolved_t5": "false",
    }
    future = [
        {"close": 101, "high": 102, "low": 99},
        {"close": 102, "high": 103, "low": 100},
    ]
    out, changed = settle_row(row, future)
    assert changed is True
    assert out["resolved_t1"] is True
    assert str(out["resolved_t3"]).lower() == "false"
    assert str(out["resolved_t5"]).lower() == "false"


def test_settlement_resolves_t5_and_mae_mfe():
    row = {
        "close_price": "100",
        "resolved_t1": "false",
        "resolved_t3": "false",
        "resolved_t5": "false",
    }
    future = [
        {"close": 101, "high": 102, "low": 99},
        {"close": 98, "high": 102, "low": 96},
        {"close": 103, "high": 104, "low": 97},
        {"close": 104, "high": 106, "low": 102},
        {"close": 105, "high": 108, "low": 103},
    ]
    out, changed = settle_row(row, future)
    assert changed is True
    assert out["t5_return"] == 5.0
    assert out["max_adverse_5d"] == -4.0
    assert out["max_favorable_5d"] == 8.0


def test_extract_yfinance_multiindex_columns():
    cols = pd.MultiIndex.from_tuples([
        ("Close", "2330.TW"),
        ("High", "2330.TW"),
        ("Low", "2330.TW"),
    ])
    df = pd.DataFrame(
        [[100, 101, 99], [102, 103, 100]],
        index=pd.to_datetime(["2026-10-09", "2026-10-12"]),
        columns=cols,
    )
    out = extract_future_ohlc(df, date(2026, 10, 9))
    assert len(out) == 1
    assert out[0]["close"] == 102.0
