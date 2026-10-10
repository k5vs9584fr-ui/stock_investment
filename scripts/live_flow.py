from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DAYTRADE_SCRIPT = ROOT / "scripts" / "daytrade_scan.py"
ORDERS_SCRIPT = ROOT / "scripts" / "intraday_orders.py"
ORDER_SHEET = ROOT / "data" / "intraday_order_sheet.json"
SNAPSHOT_DIR = ROOT / "data" / "intraday_snapshots"


def auto_phase(now: datetime | None = None) -> int:
    """Map Taipei clock to the intended opening checkpoint."""
    now = now or datetime.now(ZoneInfo("Asia/Taipei"))
    minutes = now.hour * 60 + now.minute
    if minutes <= 9 * 60 + 9:
        return 5
    if minutes <= 9 * 60 + 24:
        return 15
    return 30


def snapshot_name(phase: int, now: datetime | None = None) -> str:
    now = now or datetime.now(ZoneInfo("Asia/Taipei"))
    return f"{now:%Y%m%d_%H%M%S}_phase{phase}.json"


def run_step(cmd: list[str]) -> None:
    subprocess.run(cmd, cwd=ROOT, check=True)


def archive_order_sheet(
    *,
    phase: int,
    source: Path = ORDER_SHEET,
    snapshot_dir: Path = SNAPSHOT_DIR,
    now: datetime | None = None,
) -> Path:
    if not source.exists():
        raise RuntimeError(f"order sheet missing after live flow: {source}")
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    dest = snapshot_dir / snapshot_name(phase, now=now)
    shutil.copy2(source, dest)
    return dest


def build_flow_summary(snapshot: Path) -> dict:
    payload = json.loads(snapshot.read_text(encoding="utf-8"))
    summary = payload.get("summary") or {}
    order_sheet = payload.get("order_sheet") or {}
    return {
        "snapshot": str(snapshot),
        "top_candidate": summary.get("top_candidate"),
        "regime_v2": summary.get("regime_v2"),
        "ready_order_count": order_sheet.get("ready_order_count"),
        "weight_only_count": order_sheet.get("weight_only_count"),
        "orders": order_sheet.get("orders") or [],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh live scan and build archived intraday order sheet")
    parser.add_argument("--phase", choices=("auto", "5", "15", "30"), default="auto")
    parser.add_argument("--portfolio-value", type=float, default=None)
    parser.add_argument("--skip-scan", action="store_true", help="Reuse existing daytrade_results.json")
    parser.add_argument("--snapshot-dir", type=Path, default=SNAPSHOT_DIR)
    args = parser.parse_args()

    phase = auto_phase() if args.phase == "auto" else int(args.phase)
    python = sys.executable

    if not args.skip_scan:
        print(f"[live-flow] refresh daytrade scan for phase={phase}m")
        run_step([python, str(DAYTRADE_SCRIPT)])

    order_cmd = [
        python,
        str(ORDERS_SCRIPT),
        "--phase",
        str(phase),
    ]
    if args.portfolio_value is not None:
        order_cmd += ["--portfolio-value", str(args.portfolio_value)]

    print(f"[live-flow] build order sheet phase={phase}m")
    run_step(order_cmd)

    snapshot = archive_order_sheet(
        phase=phase,
        snapshot_dir=args.snapshot_dir,
    )
    summary = build_flow_summary(snapshot)

    print(f"[live-flow] snapshot: {snapshot}")
    print(
        f"[live-flow] top={summary.get('top_candidate')} "
        f"regime={summary.get('regime_v2')} "
        f"ready_orders={summary.get('ready_order_count')} "
        f"weight_only={summary.get('weight_only_count')}"
    )


if __name__ == "__main__":
    main()
