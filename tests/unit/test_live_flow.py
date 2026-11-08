from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from scripts.live_flow import auto_phase, snapshot_name, build_flow_summary


def _dt(hour, minute):
    return datetime(2026, 10, 12, hour, minute, tzinfo=ZoneInfo("Asia/Taipei"))


def test_auto_phase_opening_checkpoints():
    assert auto_phase(_dt(9, 5)) == 5
    assert auto_phase(_dt(9, 15)) == 15
    assert auto_phase(_dt(9, 30)) == 30


def test_snapshot_name_contains_phase_and_time():
    name = snapshot_name(15, now=_dt(9, 15))
    assert name == "20261012_091500_phase15.json"


def test_build_flow_summary_reads_order_sheet(tmp_path: Path):
    p = tmp_path / "snapshot.json"
    p.write_text(
        """{
          "summary": {"top_candidate": "8150", "regime_v2": "early_or_healthy_uptrend"},
          "order_sheet": {
            "ready_order_count": 2,
            "weight_only_count": 1,
            "orders": [{"symbol": "8150", "side": "BUY"}]
          }
        }""",
        encoding="utf-8",
    )
    out = build_flow_summary(p)
    assert out["top_candidate"] == "8150"
    assert out["ready_order_count"] == 2
    assert out["orders"][0]["symbol"] == "8150"
