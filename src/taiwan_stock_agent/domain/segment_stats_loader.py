from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path


def _summary(values: list[float]) -> dict:
    if not values:
        return {"n": 0, "t5_avg": None, "t5_win": None, "failure_rate": None}
    n = len(values)
    return {
        "n": n,
        "t5_avg": round(sum(values) / n, 3),
        "t5_win": round(sum(1 for x in values if x > 0) / n * 100, 1),
        "failure_rate": round(sum(1 for x in values if x < 0) / n * 100, 1),
    }


def build_segment_stats_from_csv(csv_path: Path, min_score: float = 55.0) -> dict:
    industries: dict[str, list[float]] = defaultdict(list)
    patterns: dict[str, list[float]] = defaultdict(list)
    combos: dict[str, list[float]] = defaultdict(list)
    sample_n = 0

    if not csv_path.exists():
        return {"sample_n": 0, "by_industry": {}, "by_pattern": {}, "industry_pattern": {}}

    with csv_path.open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                score = float(row.get("score") or 0)
                t5 = float(row.get("t5"))
            except (TypeError, ValueError):
                continue
            if score < min_score:
                continue

            sample_n += 1
            industry = str(row.get("industry") or "")
            industries[industry].append(t5)

            flags = {
                x.split(":")[0]
                for x in str(row.get("flags") or "").split("|")
                if x
            }
            for flag in flags:
                patterns[flag].append(t5)
                combos[f"{industry}|{flag}"].append(t5)

    return {
        "sample_n": sample_n,
        "by_industry": {k: _summary(v) for k, v in industries.items()},
        "by_pattern": {
            k: s for k, v in patterns.items()
            if (s := _summary(v))["n"] >= 10
        },
        "industry_pattern": {
            k: s for k, v in combos.items()
            if (s := _summary(v))["n"] >= 6
        },
    }


def load_or_build_segment_stats(
    stats_path: Path,
    backtest_csv: Path,
) -> tuple[dict, str]:
    if stats_path.exists():
        try:
            data = json.loads(stats_path.read_text(encoding="utf-8"))
            if int(data.get("sample_n") or 0) > 0:
                return data, "json"
        except Exception:
            pass

    return build_segment_stats_from_csv(backtest_csv), "rebuilt_csv"
