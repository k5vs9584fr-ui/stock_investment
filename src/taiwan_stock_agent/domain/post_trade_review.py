from __future__ import annotations

from collections import Counter
from typing import Iterable


def classify_outcome(t5_return: float | None, mae_15: float | None = None) -> str:
    if t5_return is None:
        return "UNRESOLVED"
    if t5_return >= 5:
        return "WIN_STRONG"
    if t5_return > 0:
        return "WIN_SMALL"
    if mae_15 is not None and mae_15 <= -8:
        return "LOSS_LARGE"
    return "LOSS"


def review_failures(records: Iterable[dict], min_score: float = 72.0) -> dict:
    failed = []
    flag_counter: Counter[str] = Counter()

    for row in records:
        score = float(
            row.get("hybrid_action_score")
            or row.get("practical_score")
            or row.get("final_score")
            or 0.0
        )
        t5 = row.get("t5_return")
        if t5 is None:
            t5 = row.get("t5")
        t5 = float(t5) if t5 not in (None, "") else None

        if score < min_score or t5 is None or t5 >= 0:
            continue

        failed.append(row)
        for key in ("practical_flags", "top3_quality_flags", "chip_flags"):
            for flag in row.get(key) or []:
                flag_counter[str(flag)] += 1

    n = len(failed)
    common = [
        {"flag": flag, "count": count, "share": round(count / n, 3)}
        for flag, count in flag_counter.most_common()
    ] if n else []

    return {
        "failed_high_score_count": n,
        "common_failure_flags": common,
    }
