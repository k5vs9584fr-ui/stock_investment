from __future__ import annotations

from pathlib import Path
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "ai_backtest.csv"
OUT = ROOT / "data" / "segmented_failure_review.json"


def split_flags(s: str) -> list[str]:
    return [x.split(":")[0] for x in str(s or "").split("|") if x]


def summarize_group(g: pd.DataFrame) -> dict:
    t5 = pd.to_numeric(g["t5"], errors="coerce")
    valid = t5.dropna()
    if valid.empty:
        return {
            "n": 0,
            "t5_avg": None,
            "t5_win": None,
            "failure_rate": None,
        }
    return {
        "n": int(len(valid)),
        "t5_avg": round(float(valid.mean()), 3),
        "t5_win": round(float((valid > 0).mean() * 100), 1),
        "failure_rate": round(float((valid < 0).mean() * 100), 1),
    }


def main() -> None:
    df = pd.read_csv(SRC)
    df["score"] = pd.to_numeric(df["score"], errors="coerce")
    df = df[df["score"] >= 55].copy()

    result: dict[str, object] = {
        "sample_n": int(len(df)),
        "by_industry": {},
        "by_pattern": {},
        "industry_pattern": {},
    }

    for industry, g in df.groupby("industry"):
        result["by_industry"][str(industry)] = summarize_group(g)

    pattern_rows = []
    for _, row in df.iterrows():
        for flag in split_flags(row.get("flags", "")):
            pattern_rows.append({
                "industry": row.get("industry"),
                "pattern": flag,
                "t5": row.get("t5"),
            })
    pf = pd.DataFrame(pattern_rows)

    if not pf.empty:
        for pattern, g in pf.groupby("pattern"):
            s = summarize_group(g)
            if s["n"] >= 10:
                result["by_pattern"][str(pattern)] = s

        for (industry, pattern), g in pf.groupby(["industry", "pattern"]):
            s = summarize_group(g)
            if s["n"] >= 6:
                key = f"{industry}|{pattern}"
                result["industry_pattern"][key] = s

    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
