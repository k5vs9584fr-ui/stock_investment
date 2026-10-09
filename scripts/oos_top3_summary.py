from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRACK = ROOT / "data" / "oos_top3_tracking.csv"
OUT = ROOT / "data" / "oos_top3_summary.json"


def fnum(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def main():
    if not TRACK.exists():
        OUT.write_text(json.dumps({"sample_n": 0}, indent=2), encoding="utf-8")
        return

    rows = list(csv.DictReader(TRACK.open("r", encoding="utf-8")))
    resolved = [r for r in rows if str(r.get("resolved_t5")).lower() == "true"]

    t1 = [fnum(r.get("t1_return")) for r in rows if str(r.get("resolved_t1")).lower() == "true"]
    t3 = [fnum(r.get("t3_return")) for r in rows if str(r.get("resolved_t3")).lower() == "true"]
    t5 = [fnum(r.get("t5_return")) for r in resolved]

    t1 = [x for x in t1 if x is not None]
    t3 = [x for x in t3 if x is not None]
    t5 = [x for x in t5 if x is not None]

    out = {
        "signals_total": len(rows),
        "resolved_t1_n": len(t1),
        "resolved_t3_n": len(t3),
        "resolved_t5_n": len(t5),
        "t1_avg": round(sum(t1) / len(t1), 3) if t1 else None,
        "t3_avg": round(sum(t3) / len(t3), 3) if t3 else None,
        "t5_avg": round(sum(t5) / len(t5), 3) if t5 else None,
        "t5_win_rate": round(sum(1 for x in t5 if x > 0) / len(t5) * 100, 1) if t5 else None,
        "t5_loss_rate": round(sum(1 for x in t5 if x < 0) / len(t5) * 100, 1) if t5 else None,
    }

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
