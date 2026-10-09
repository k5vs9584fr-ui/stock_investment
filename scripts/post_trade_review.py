from __future__ import annotations

from pathlib import Path
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "ai_backtest.csv"
OUT = ROOT / "data" / "post_trade_review.json"


def flag_tokens(s: str) -> list[str]:
    return [x for x in str(s or "").split("|") if x]


def main() -> None:
    df = pd.read_csv(SRC)
    df["t5"] = pd.to_numeric(df["t5"], errors="coerce")
    df["score"] = pd.to_numeric(df["score"], errors="coerce")

    high = df[df["score"] >= 55].copy()
    failed = high[high["t5"] < 0].copy()

    counts: dict[str, int] = {}
    for flags in failed["flags"].fillna(""):
        for flag in flag_tokens(flags):
            key = flag.split(":")[0]
            counts[key] = counts.get(key, 0) + 1

    n = len(failed)
    common = [
        {
            "flag": k,
            "count": v,
            "share": round(v / n, 3) if n else 0.0,
        }
        for k, v in sorted(counts.items(), key=lambda x: x[1], reverse=True)
    ]

    out = {
        "high_score_sample": int(len(high)),
        "failed_high_score": int(n),
        "failure_rate": round(n / len(high), 3) if len(high) else None,
        "common_failure_flags": common[:20],
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
