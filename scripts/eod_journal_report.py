"""Aggregate matured signal-day-close to future-close outcomes by model class.

Research only: not realized trading P&L, and not an estimate of next-trade odds.
Requires >= 30 completed samples per style/horizon before displaying aggregates.
"""
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "eod_signal_journal.json"
DEST = ROOT / "data" / "eod_signal_report.json"
MIN_SAMPLE = 30


def summarize(journal, min_sample=MIN_SAMPLE):
    groups = defaultdict(list)
    for s in journal.get("signals", []):
        for horizon, ret in s.get("forward_close_returns_pct", {}).items():
            if ret is not None and horizon in ("1", "2", "5"):
                groups[(s["style"], horizon)].append(float(ret))
    table = []
    for (style, horizon), returns in sorted(groups.items()):
        n = len(returns)
        vals = sorted(returns)
        row = {"style": style, "horizon_sessions": int(horizon),
               "completed_samples": n, "sufficient_sample": n >= min_sample}
        if n >= min_sample:
            row.update({
                "mean_close_return_pct": round(sum(vals) / n, 3),
                "median_close_return_pct": round(
                    (vals[(n - 1) // 2] + vals[n // 2]) / 2, 3),
                "positive_close_fraction": round(sum(v > 0 for v in vals) / n, 4),
            })
        else:
            row["reason"] = "INSUFFICIENT_COMPLETED_SAMPLES"
        table.append(row)
    return {
        "data_status": "RESEARCH_CLOSE_TO_CLOSE_ONLY",
        "last_date": journal.get("last_date"),
        "min_sample": min_sample,
        "groups": table,
        "disclaimer": (
            "Look-ahead-free signal-date close to future close research. "
            "Not executed P&L; excludes realistic fills, commissions, tax, "
            "slippage, gaps, and market benchmark; do not infer predictive edge."
        ),
    }


def main():
    journal = json.loads(SOURCE.read_text(encoding="utf-8"))
    report = summarize(journal)
    DEST.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    print("Report groups:", len(report["groups"]))


if __name__ == "__main__":
    main()
