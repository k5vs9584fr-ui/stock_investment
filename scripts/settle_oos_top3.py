from __future__ import annotations

import csv
from pathlib import Path
from datetime import datetime
import yfinance as yf

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
            pass
    return None


def pct(a, b):
    return (b / a - 1.0) * 100.0


def main():
    if not TRACK.exists():
        print("no OOS tracking file")
        return

    rows = list(csv.DictReader(TRACK.open("r", encoding="utf-8")))
    changed = False

    for row in rows:
        if str(row.get("resolved_t5")).lower() == "true":
            continue

        try:
            signal_date = datetime.strptime(row["signal_date"], "%Y-%m-%d").date()
            entry = float(row["close_price"])
        except Exception:
            continue

        df = fetch_history(row["symbol"], signal_date.isoformat())
        if df is None or df.empty:
            continue

        closes = []
        highs = []
        lows = []
        for idx, rec in df.iterrows():
            d = idx.date()
            if d <= signal_date:
                continue
            try:
                closes.append(float(rec["Close"]))
                highs.append(float(rec["High"]))
                lows.append(float(rec["Low"]))
            except Exception:
                continue

        if len(closes) >= 1 and str(row.get("resolved_t1")).lower() != "true":
            row["t1_return"] = round(pct(entry, closes[0]), 3)
            row["resolved_t1"] = True
            changed = True

        if len(closes) >= 3 and str(row.get("resolved_t3")).lower() != "true":
            row["t3_return"] = round(pct(entry, closes[2]), 3)
            row["resolved_t3"] = True
            changed = True

        if len(closes) >= 5:
            if str(row.get("resolved_t5")).lower() != "true":
                row["t5_return"] = round(pct(entry, closes[4]), 3)
                row["resolved_t5"] = True
                changed = True
            row["max_adverse_5d"] = round(min(pct(entry, x) for x in lows[:5]), 3)
            row["max_favorable_5d"] = round(max(pct(entry, x) for x in highs[:5]), 3)

    if changed:
        with TRACK.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=rows[0].keys())
            w.writeheader()
            w.writerows(rows)

    print(f"processed {len(rows)} OOS signals")


if __name__ == "__main__":
    main()
