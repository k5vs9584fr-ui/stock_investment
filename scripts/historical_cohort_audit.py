"""Audit existing SURGE backtest cohorts without lookahead or data fabrication.

IMPORTANT: data/surge_backtest.csv contains only historical SURGE-detected stocks.
It cannot validate low-buy / panic-reversal signals or all-market efficacy.
Outcomes are signal-close to future-close and not executable returns.
"""
from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "surge_backtest.csv"
OUT = ROOT / "data" / "historical_cohort_audit.json"
COLUMNS = {"signal_date", "ticker", "day_chg_pct", "close_strength",
           "t5_return_pct", "t10_return_pct"}
MIN_DATES = 10
MIN_ROWS = 30


def _percentile(sorted_values, q):
    """Nearest-rank quantile, conservative at lower tail."""
    if not sorted_values:
        return None
    return sorted_values[max(0, math.ceil(q * len(sorted_values)) - 1)]


def _median(vals):
    vals = sorted(vals)
    n = len(vals)
    return (vals[(n - 1) // 2] + vals[n // 2]) / 2


def bucket(change):
    if 0 <= change < 4:
        return "0_to_4_pct"
    if 4 <= change < 7:
        return "4_to_7_pct"
    if change >= 7:
        return "7_plus_pct"
    return "negative_day"


def clean_rows(rows):
    cleaned = []
    seen = set()
    for row in rows:
        if not COLUMNS.issubset(row):
            raise ValueError("MISSING_REQUIRED_COLUMNS")
        try:
            date = str(row["signal_date"]).strip()
            symbol = str(row["ticker"]).strip()
            change = float(row["day_chg_pct"])
            strength = float(row["close_strength"])
            raw5 = row["t5_return_pct"]
            raw10 = row["t10_return_pct"]
            t5 = float(raw5) if raw5 is not None and str(raw5).strip() else None
            t10 = float(raw10) if raw10 is not None and str(raw10).strip() else None
        except (TypeError, ValueError) as exc:
            raise ValueError("INVALID_HISTORICAL_ROW") from exc
        if (len(date) != 10 or not date[:4].isdigit()
                or not symbol.isdigit() or not all(
                    math.isfinite(x) for x in (change, strength, t5, t10) if x is not None)
                or not (0 <= strength <= 1) or not (-100 < change <= 100)):
            raise ValueError("INVALID_HISTORICAL_ROW")
        key = (date, symbol)
        if key in seen:
            raise ValueError("DUPLICATE_HISTORICAL_SIGNAL")
        seen.add(key)
        cleaned.append({"date": date, "symbol": symbol, "change": change,
                        "strength": strength, "t5": t5, "t10": t10,
                        "bucket": bucket(change)})
    return cleaned


def analyze(rows, minimum_rows=MIN_ROWS, minimum_dates=MIN_DATES):
    cleaned = clean_rows(rows)
    groups = defaultdict(list)
    for row in cleaned:
        groups[row["bucket"]].append(row)
    result = []
    for cohort in ("negative_day", "0_to_4_pct", "4_to_7_pct", "7_plus_pct"):
        items = groups[cohort]
        dates = {x["date"] for x in items}
        observation = {"cohort": cohort, "signal_count": len(items),
                       "signal_dates": len(dates)}
        for horizon in ("t5", "t10"):
            matured = [x for x in items if x[horizon] is not None]
            horizon_dates = {x["date"] for x in matured}
            enough = (len(matured) >= minimum_rows and
                      len(horizon_dates) >= minimum_dates)
            if not enough:
                observation[horizon] = {
                    "completed_samples": len(matured),
                    "completed_signal_dates": len(horizon_dates),
                    "eligible_to_report": False,
                    "reason": "INSUFFICIENT_MATURED_OUTCOMES_OR_DATES",
                }
                continue
            returns = sorted(x[horizon] for x in matured)
            means_by_date = defaultdict(list)
            for item in matured:
                means_by_date[item["date"]].append(item[horizon])
            daily_means = [sum(v) / len(v) for v in means_by_date.values()]
            observation[horizon] = {
                "completed_samples": len(matured),
                "completed_signal_dates": len(horizon_dates),
                "eligible_to_report": True,
                "mean_pct": round(sum(returns) / len(returns), 4),
                "median_pct": round(_median(returns), 4),
                "positive_fraction": round(
                    sum(v > 0 for v in returns) / len(returns), 4),
                "p10_pct": round(_percentile(returns, 0.10), 4),
                "worst_pct": round(returns[0], 4),
                "mean_of_date_means_pct": round(
                    sum(daily_means) / len(daily_means), 4),
                "illustrative_mean_after_0_6pct_roundtrip_cost": round(
                    sum(returns) / len(returns) - 0.6, 4),
            }
        result.append(observation)
    return {
        "dataset": "data/surge_backtest.csv",
        "source_scope": "SURGE_SIGNALS_ONLY_NOT_WHOLE_MARKET",
        "start": min((x["date"] for x in cleaned), default=None),
        "end": max((x["date"] for x in cleaned), default=None),
        "signals_total": len(cleaned),
        "unique_signal_dates": len({x["date"] for x in cleaned}),
        "cohorts": result,
        "caveats": [
            "This audit does not test the new panic-reversal model.",
            "Outcomes are precomputed close-to-future-close and do not model executable fills.",
            "No intraday stop, gap risk, liquidity constraint, or market benchmark.",
            "Illustrative flat 0.6 percentage-point deduction is NOT a full trade simulation.",
            "Signals on the same date are correlated; do not treat stock count as independent trials.",
            "Any rule selected by inspecting these outcomes requires untouched out-of-sample data.",
        ],
        "decision": "EVIDENCE_NOT_SUFFICIENT_TO_REMOVE_BREAKOUT_STRATEGY",
    }


def main():
    with SOURCE.open(newline="", encoding="utf-8") as fh:
        report = analyze(csv.DictReader(fh))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
