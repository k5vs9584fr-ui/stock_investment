from __future__ import annotations

import csv
from pathlib import Path
from datetime import datetime

import yfinance as yf

from taiwan_stock_agent.domain.oos_settlement import extract_future_ohlc, settle_row

ROOT = Path(__file__).resolve().parents[1]
TRACK = ROOT / "data" / "oos_top3_tracking.csv"


def tw_symbol(symbol: str) -> list[str]:
    s = str(symbol).strip()
    return [f"{s}.TW", f"{s}.TWO"]


def fetch_history(symbol: str, start: str):
    for code in tw_symbol(symbol):
        try:
            df = yf.download(code, start=start, progress=False, auto_adjust=False)
            if not df.empty:
                return df
        except Exception:
            continue
    return None


def main():
    if not TRACK.exists():
        print("no OOS tracking file")
        return

    rows = list(csv.DictReader(TRACK.open("r", encoding="utf-8")))
    changed = False
    settled = []

    for row in rows:
        if str(row.get("resolved_t5")).lower() == "true":
            settled.append(row)
            continue

        try:
            signal_date = datetime.strptime(row["signal_date"], "%Y-%m-%d").date()
            entry = float(row["close_price"])
            if entry <= 0:
                raise ValueError("invalid close_price")
        except Exception:
            settled.append(row)
            continue

        df = fetch_history(row["symbol"], signal_date.isoformat())
        if df is None or df.empty:
            settled.append(row)
            continue

        future = extract_future_ohlc(df, signal_date)
        updated, row_changed = settle_row(row, future)
        settled.append(updated)
        changed = changed or row_changed

    if changed and settled:
        with TRACK.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=settled[0].keys())
            w.writeheader()
            w.writerows(settled)

    print(f"processed {len(rows)} OOS signals; changed={changed}")


if __name__ == "__main__":
    main()
