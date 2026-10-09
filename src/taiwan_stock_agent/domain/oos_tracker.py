from __future__ import annotations

import csv
from pathlib import Path
from datetime import date, datetime

FIELDS = [
    "signal_date",
    "symbol",
    "name",
    "rank",
    "hybrid_action_score",
    "practical_score",
    "final_score",
    "entry_mode",
    "entry_trigger",
    "close_price",
    "t1_return",
    "t3_return",
    "t5_return",
    "max_adverse_5d",
    "max_favorable_5d",
    "resolved_t1",
    "resolved_t3",
    "resolved_t5",
]


def append_signal_snapshot(report: dict, out_path: Path) -> int:
    top3 = report.get("primary_top3") or []
    if not top3:
        return 0

    existing = set()
    if out_path.exists():
        with out_path.open("r", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                existing.add((row.get("signal_date"), row.get("symbol")))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not out_path.exists()

    added = 0
    with out_path.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if write_header:
            w.writeheader()

        for row in top3:
            key = (str(report.get("scan_date") or ""), str(row.get("symbol") or ""))
            if key in existing:
                continue

            plan = row.get("entry_exit_plan") or {}
            w.writerow({
                "signal_date": key[0],
                "symbol": key[1],
                "name": row.get("name") or "",
                "rank": row.get("practical_rank") or "",
                "hybrid_action_score": row.get("hybrid_action_score") or "",
                "practical_score": row.get("practical_score") or "",
                "final_score": row.get("final_score") or "",
                "entry_mode": plan.get("entry_mode") or "",
                "entry_trigger": plan.get("entry_trigger") or "",
                "close_price": row.get("price") or "",
                "t1_return": "",
                "t3_return": "",
                "t5_return": "",
                "max_adverse_5d": "",
                "max_favorable_5d": "",
                "resolved_t1": False,
                "resolved_t3": False,
                "resolved_t5": False,
            })
            added += 1

    return added
