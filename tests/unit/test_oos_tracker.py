from pathlib import Path
import csv

from taiwan_stock_agent.domain.oos_tracker import append_signal_snapshot


def test_oos_tracker_is_idempotent(tmp_path: Path):
    p = tmp_path / "oos.csv"
    report = {
        "scan_date": "2026-10-09",
        "primary_top3": [
            {
                "symbol": "2332",
                "name": "友訊",
                "practical_rank": 1,
                "hybrid_action_score": 91.0,
                "practical_score": 100.0,
                "final_score": 82.1,
                "price": 20.0,
                "entry_exit_plan": {
                    "entry_mode": "BREAKOUT_CONFIRM",
                    "entry_trigger": 20.5,
                },
            }
        ],
    }

    assert append_signal_snapshot(report, p) == 1
    assert append_signal_snapshot(report, p) == 0

    rows = list(csv.DictReader(p.open("r", encoding="utf-8")))
    assert len(rows) == 1
    assert rows[0]["symbol"] == "2332"
    assert rows[0]["resolved_t5"].lower() == "false"
