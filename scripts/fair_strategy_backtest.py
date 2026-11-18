"""Fair, source-agnostic OHLCV replay for risk-first vs momentum watchlists.

REQUIRES a normalized historical market panel: date,symbol,open,high,low,close,
volume,trade_value. Only one panel and common signal dates are compared.
No prices obtained from the future are used in signal generation.
Hypothetical fills at NEXT OPEN and exits at D+1 / D+2 CLOSE; no stop/target
orders assumed filled. This is research, not an actual execution backtest.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from datetime import date
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.risk_first_radar import evaluate

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {"date", "symbol", "open", "high", "low", "close", "volume", "trade_value"}
STRATEGIES = ("PANIC_REVERSAL_WATCH", "EXTENDED_OR_BREAKOUT_WATCH")
COST_BPS = 58.5  # illustrative fees both directions 0.1425% each + sale tax 0.3%.
# 28.5 bp commissions + 30 bp sale tax = 58.5 bp, no fee discounts.
HOLD_SESSIONS = (1, 2)


def read_panel(path):
    """Strictly validate daily OHLCV, exclude duplicates rather than overwrite."""
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not REQUIRED.issubset(set(reader.fieldnames or [])):
            raise ValueError("MISSING_PANEL_COLUMNS")
        panel = {}
        seen_dates = set()
        for raw in reader:
            try:
                day = date.fromisoformat(raw["date"]).isoformat()
                symbol = str(raw["symbol"]).strip()
                nums = {k: float(raw[k]) for k in
                        ("open", "high", "low", "close", "volume", "trade_value")}
            except (ValueError, TypeError, KeyError) as exc:
                raise ValueError("INVALID_OHLCV_ROW") from exc
            if (len(symbol) != 4 or not symbol.isdigit() or
                    not all(math.isfinite(v) for v in nums.values()) or
                    min(nums["open"], nums["high"], nums["low"], nums["close"]) <= 0 or
                    nums["high"] < max(nums["open"], nums["close"], nums["low"]) or
                    nums["low"] > min(nums["open"], nums["close"], nums["high"]) or
                    nums["volume"] <= 0 or nums["trade_value"] <= 0):
                raise ValueError("INVALID_OHLCV_ROW")
            key = (day, symbol)
            if key in panel:
                raise ValueError("DUPLICATE_DATE_SYMBOL")
            panel[key] = dict(date=day, symbol=symbol, **nums)
            seen_dates.add(day)
    return panel, sorted(seen_dates)


def signal_for(bar, prior):
    """Signal date close + that date's range only, never future OHLC."""
    if prior["close"] <= 0:
        return None
    change = 100 * (bar["close"] / prior["close"] - 1)
    span = bar["high"] - bar["low"]
    strength = (bar["close"] - bar["low"]) / span if span > 0 else None
    return evaluate({
        "symbol": bar["symbol"], "name": bar["symbol"],
        "close": bar["close"], "high": bar["high"], "low": bar["low"],
        "change_pct": change, "close_strength": strength,
        "value": bar["trade_value"],
    }) if strength is not None else None


def replay(panel, dates, *, minimum_symbols=100, minimum_signal_dates=10,
           minimum_trades_per_style=30, cost_bps=COST_BPS,
           train_fraction=0.6):
    """Use trading-calendar indices, without calendar-day approximations.

    Only evaluate dates with complete lookahead (one next-session entry and two
    exit sessions). Return separate in-time and later held-out test summaries.
    Missing OHLCV for any required entry/exit is excluded and counted.
    """
    if not (0 <= cost_bps <= 300):
        raise ValueError("INVALID_COST_BPS")
    if not (0.4 <= train_fraction <= 0.8):
        raise ValueError("INVALID_TRAIN_FRACTION")
    if len(dates) < 8:
        raise ValueError("INSUFFICIENT_MARKET_SESSIONS")
    symbols = {sym for (_, sym) in panel}
    if len(symbols) < minimum_symbols:
        raise ValueError("INSUFFICIENT_UNIVERSE_COVERAGE")

    data_dates = dates[:-3]
    split_index = int(len(data_dates) * train_fraction)
    records = []
    missing = defaultdict(int)
    date_coverage = []
    for idx in range(1, len(dates) - 3):
        day = dates[idx]
        prev_day = dates[idx-1]
        eligible_symbols = [
            sym for sym in symbols
            if (day, sym) in panel and (prev_day, sym) in panel
        ]
        date_coverage.append({"date": day, "symbols_with_two_bars": len(eligible_symbols)})
        if len(eligible_symbols) < minimum_symbols:
            missing["low_coverage_signal_dates"] += 1
            continue
        for symbol in eligible_symbols:
            item = signal_for(panel[(day, symbol)], panel[(prev_day, symbol)])
            if item is None:
                continue
            if item["style"] == "PANIC_REVERSAL_WATCH" and not item["watch_eligible"]:
                continue
            if item["style"] not in STRATEGIES:
                continue
            entry = panel.get((dates[idx+1], symbol))
            if entry is None:
                missing["missing_next_open"] += 1
                continue
            entry_open = entry["open"]
            if not math.isfinite(entry_open) or entry_open <= 0:
                missing["invalid_next_open"] += 1
                continue
            for hold in HOLD_SESSIONS:
                # Hold=1 means exit at entry-day close; hold=2 means exit next day's close.
                exit_idx = idx + hold
                exitbar = panel.get((dates[exit_idx], symbol))
                if exitbar is None:
                    missing[f"missing_exit_{hold}"] += 1
                    continue
                lows = [panel.get((dates[k], symbol)) for k in range(idx+1, exit_idx+1)]
                if any(x is None for x in lows):
                    missing[f"missing_path_{hold}"] += 1
                    continue
                adverse = (min(x["low"] for x in lows) / entry_open - 1) * 100
                gross = (exitbar["close"] / entry_open - 1) * 100
                records.append({
                    "date": day, "symbol": symbol, "strategy": item["style"],
                    "hold_sessions": hold, "signal_close": panel[(day, symbol)]["close"],
                    "entry_date": dates[idx+1], "exit_date": dates[exit_idx],
                    "entry_open": entry_open, "exit_close": exitbar["close"],
                    "gross_return_pct": round(gross, 6),
                    "net_return_pct": round(gross - cost_bps/100, 6),
                    "path_min_return_pct": round(adverse, 6),
                    "stage": "train" if idx < split_index else "test",
                })
    summaries = []
    for stage in ("train", "test"):
        for style in STRATEGIES:
            for hold in HOLD_SESSIONS:
                trades = [x for x in records if x["stage"] == stage and
                          x["strategy"] == style and x["hold_sessions"] == hold]
                days = {x["date"] for x in trades}
                enough = (len(trades) >= minimum_trades_per_style and
                          len(days) >= minimum_signal_dates)
                summary = {"stage": stage, "strategy": style,
                           "holding_sessions": hold, "completed_trades": len(trades),
                           "independent_signal_dates": len(days),
                           "sufficient_data": enough}
                if enough:
                    net = sorted(x["net_return_pct"] for x in trades)
                    n = len(net)
                    per_day = defaultdict(list)
                    for t in trades:
                        per_day[t["date"]].append(t["net_return_pct"])
                    summary.update({
                        "mean_net_pct": round(sum(net)/n, 4),
                        "median_net_pct": round(
                            (net[(n-1)//2] + net[n//2])/2, 4),
                        "positive_net_fraction": round(sum(v > 0 for v in net)/n, 4),
                        "p10_net_pct": round(net[max(0, math.ceil(n*.1)-1)], 4),
                        "worst_net_pct": round(net[0], 4),
                        "worst_intraday_adverse_pct": round(
                            min(x["path_min_return_pct"] for x in trades), 4),
                        "mean_of_daily_equal_weight_net_pct": round(
                            sum(sum(v)/len(v) for v in per_day.values())/len(per_day), 4),
                    })
                else:
                    summary["reason"] = "NOT_ENOUGH_SIGNALS_OR_DATES"
                summaries.append(summary)
    return {
        "data_status": "HISTORICAL_RESEARCH_ONLY",
        "period_start": dates[0], "period_end": dates[-1],
        "symbols_with_any_data": len(symbols), "market_sessions": len(dates),
        "minimum_universe_symbols": minimum_symbols,
        "trade_count": len(records),
        "cost_bps_illustrative": cost_bps, "train_fraction": train_fraction,
        "train_test_split": data_dates[split_index] if split_index < len(data_dates) else None,
        "coverage_by_signal_date": date_coverage,
        "missing_counts": dict(missing),
        "comparisons": summaries,
        "disclaimer": (
            "Same historical panel and next-day-open entry for both categories. "
            "Not live executable trades. Open slippage, daily-limit fillability, "
            "adjustments, survivorship bias, fees/ETFs and stop execution not verified. "
            "No optimizations should use held-out test dates."
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--panel", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=ROOT/"data"/"fair_backtest_report.json")
    parser.add_argument("--min-symbols", type=int, default=100)
    parser.add_argument("--min-dates", type=int, default=10)
    parser.add_argument("--min-trades", type=int, default=30)
    args = parser.parse_args()
    panel, dates = read_panel(args.panel)
    result = replay(panel, dates, minimum_symbols=args.min_symbols,
                    minimum_signal_dates=args.min_dates,
                    minimum_trades_per_style=args.min_trades)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print(json.dumps({key: result[key] for key in
          ("data_status", "symbols_with_any_data", "market_sessions",
           "trade_count", "missing_counts", "comparisons")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
