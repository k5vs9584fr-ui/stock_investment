"""Optional historical OHLCV ingestion for fair-strategy replay.

Research data, never intraday prices. Vendor availability and completeness
may vary. Historical universe is the CURRENT list -> survivorship bias.
No invented data or using ticker numerics to guess exchange.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UNIVERSE = ROOT / "data" / "stock_universe.json"
DATA_DIR = ROOT / "data"


def eligible_universe(raw):
    stocks = raw.get("stocks") or []
    result = {}
    for item in stocks:
        symbol = str(item.get("symbol") or "").strip()
        market = str(item.get("market") or "").upper()
        if (len(symbol) == 4 and symbol.isdigit() and symbol != "2344"
                and market in ("TWSE", "TSE", "TPEX", "OTC")):
            result[symbol] = "TW" if market in ("TWSE", "TSE") else "TWO"
    return result


def stable_sample(universe, limit):
    if limit < 1:
        raise ValueError("LIMIT_MUST_BE_POSITIVE")
    # Fixed-by-symbol ordering, no filtering on future return or rank.
    return sorted(universe, key=lambda sym: hashlib.sha256(
        f"2026-11-radar-research:{sym}".encode()).hexdigest())[:limit]


def fetch_one(symbol, suffix, start, exclusive_end):
    import yfinance as yf
    df = yf.Ticker(f"{symbol}.{suffix}").history(
        start=start, end=exclusive_end, interval="1d",
        auto_adjust=False, actions=False)
    if df is None or df.empty:
        return []
    rows = []
    for idx, rec in df.iterrows():
        try:
            d = idx.date().isoformat()
            o, h, l, c = [float(rec[key]) for key in
                           ("Open", "High", "Low", "Close")]
            vol = int(rec["Volume"])
            if not (o > 0 and h >= max(o, c, l) and
                    l <= min(o, c, h) and vol > 0):
                continue
            rows.append({
                "date": d, "symbol": symbol, "open": round(o, 6),
                "high": round(h, 6), "low": round(l, 6),
                "close": round(c, 6), "volume": vol,
                # Explicit proxy, not actual exchange transaction value.
                "trade_value": round(c * vol, 2),
            })
        except (ValueError, TypeError, KeyError, AttributeError):
            continue
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True, help="Last day inclusive")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--pause", type=float, default=0.3)
    parser.add_argument("--panel", type=Path,
                        default=DATA_DIR / "historical_replay_panel.csv")
    args = parser.parse_args()
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    if end <= start or (end - start).days < 60:
        raise ValueError("REQUIRE_AT_LEAST_60_CALENDAR_DAYS")
    if end > date.today():
        raise ValueError("FUTURE_HISTORY_DATE")
    raw = json.loads(UNIVERSE.read_text(encoding="utf-8"))
    universe = eligible_universe(raw)
    if len(universe) < 1500:
        raise ValueError("INCOMPLETE_UNIVERSE")
    selected = stable_sample(universe, args.limit)
    all_rows, missing = [], []
    for i, symbol in enumerate(selected, 1):
        try:
            rows = fetch_one(symbol, universe[symbol], start.isoformat(),
                             (end + timedelta(days=1)).isoformat())
            if not rows:
                missing.append(symbol)
            else:
                all_rows.extend(rows)
        except Exception as exc:
            missing.append(symbol)
            print(f"PROVIDER_UNAVAILABLE symbol={symbol} type={type(exc).__name__}",
                  flush=True)
        if i % 25 == 0:
            print(f"{i}/{len(selected)} scanned, {len(missing)} empty", flush=True)
        if args.pause > 0:
            time.sleep(args.pause)
    all_rows.sort(key=lambda r: (r["date"], r["symbol"]))
    if not all_rows:
        raise RuntimeError("NO_VALID_HISTORICAL_DATA")
    args.panel.parent.mkdir(parents=True, exist_ok=True)
    with args.panel.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=(
            "date", "symbol", "open", "high", "low", "close",
            "volume", "trade_value"))
        writer.writeheader()
        writer.writerows(all_rows)
    metadata = {
        "provider": "yfinance",
        "provider_price_mode": "UNADJUSTED_DAILY_OHLC",
        "turnover": "CLOSE_TIMES_VOLUME_PROXY_NOT_OFFICIAL_TRADE_VALUE",
        "universe": "CURRENT_STOCK_UNIVERSE_SURVIVORSHIP_BIAS",
        "selection": "DETERMINISTIC_HASH_SAMPLE_NOT_WHOLE_MARKET",
        "selected_symbols": len(selected),
        "symbols_with_records": len({x["symbol"] for x in all_rows}),
        "symbols_missing": missing,
        "rows": len(all_rows), "requested_start": str(start),
        "requested_end": str(end),
        "warning": "Potential split/dividend effects, missing rows and vendor errors. "
                   "This sample is a RESEARCH SAMPLE, not full-market coverage.",
    }
    (args.panel.with_suffix(".metadata.json")).write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in metadata.items()
                      if k != "symbols_missing"}, ensure_ascii=False))
    if len({x["symbol"] for x in all_rows}) < 100:
        raise RuntimeError("HISTORICAL_SAMPLE_BELOW_100_STOCKS")


if __name__ == "__main__":
    main()
