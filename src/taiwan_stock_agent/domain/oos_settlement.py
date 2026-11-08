from __future__ import annotations

from datetime import date
from typing import Iterable

import pandas as pd


def _scalar(value):
    """Return a numeric scalar from pandas scalar/Series-like cells."""
    if hasattr(value, "iloc"):
        if len(value) == 0:
            raise ValueError("empty value")
        value = value.iloc[0]
    return float(value)


def extract_future_ohlc(df: pd.DataFrame, signal_date: date) -> list[dict]:
    """Normalize yfinance single- or multi-index OHLC output.

    Only rows strictly after signal_date are returned, preventing look-ahead
    leakage into T+1/T+3/T+5 settlement.
    """
    out: list[dict] = []
    for idx, rec in df.iterrows():
        d = idx.date() if hasattr(idx, "date") else pd.Timestamp(idx).date()
        if d <= signal_date:
            continue
        try:
            out.append({
                "date": d.isoformat(),
                "close": _scalar(rec["Close"]),
                "high": _scalar(rec["High"]),
                "low": _scalar(rec["Low"]),
            })
        except Exception:
            continue
    return out


def pct(entry: float, value: float) -> float:
    if entry <= 0:
        raise ValueError("entry must be positive")
    return (value / entry - 1.0) * 100.0


def settle_row(row: dict, future_ohlc: Iterable[dict]) -> tuple[dict, bool]:
    """Fill only horizons that have enough completed future trading sessions."""
    data = list(future_ohlc)
    changed = False
    out = dict(row)

    if len(data) >= 1 and str(out.get("resolved_t1")).lower() != "true":
        out["t1_return"] = round(pct(float(out["close_price"]), float(data[0]["close"])), 3)
        out["resolved_t1"] = True
        changed = True

    if len(data) >= 3 and str(out.get("resolved_t3")).lower() != "true":
        out["t3_return"] = round(pct(float(out["close_price"]), float(data[2]["close"])), 3)
        out["resolved_t3"] = True
        changed = True

    if len(data) >= 5:
        entry = float(out["close_price"])
        if str(out.get("resolved_t5")).lower() != "true":
            out["t5_return"] = round(pct(entry, float(data[4]["close"])), 3)
            out["resolved_t5"] = True
            changed = True

        mae = min(pct(entry, float(x["low"])) for x in data[:5])
        mfe = max(pct(entry, float(x["high"])) for x in data[:5])
        out["max_adverse_5d"] = round(mae, 3)
        out["max_favorable_5d"] = round(mfe, 3)

    return out, changed
