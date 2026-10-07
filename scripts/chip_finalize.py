import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "final_signal_report.json"
STRUCTURE_WATCHLIST = ROOT / "data" / "electronic_watchlist.json"
WATCHLIST = ROOT / "data" / "electronic_final_watchlist.json"
OUT = ROOT / "data" / "final_scan_results.json"


def load_json(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main():
    if not SOURCE.exists():
        raise RuntimeError("final_signal_report.json 不存在")
    if not STRUCTURE_WATCHLIST.exists():
        raise RuntimeError("electronic_watchlist.json 不存在")

    payload = load_json(SOURCE)
    structure = load_json(STRUCTURE_WATCHLIST)

    expected_date = structure.get("scan_date")
    actual_date = payload.get("scan_date")
    if not expected_date or actual_date != expected_date:
        raise RuntimeError(
            f"final signal 日期不一致：watchlist={expected_date}, signal={actual_date}"
        )

    rows = payload.get("stocks") or []
    if not rows:
        raise RuntimeError("final_signal_report.json 沒有 stocks")

    rows.sort(key=lambda x: x.get("final_score", 0), reverse=True)

    report = {
        "scan_date": actual_date,
        "model_version": "complete-v3",
        "source": payload.get("source", "final_signal_report.json"),
        "pipeline": [
            "intraday_latent",
            "multi_day_structure",
            "chip_refinement",
            "freshness_guard",
            "final_ranking",
        ],
        "count": len(rows),
        "a_plus": [x for x in rows if str(x.get("final_phase", "")).startswith("A+")],
        "a": [x for x in rows if str(x.get("final_phase", "")).startswith("A級")],
        "b": [x for x in rows if str(x.get("final_phase", "")).startswith("B級")],
        "top_final": rows,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)

    with WATCHLIST.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "scan_date": actual_date,
                "model_version": "complete-v3",
                "source": payload.get("source", "final_signal_report.json"),
                "count": len(rows),
                "stocks": rows,
            },
            f,
            ensure_ascii=False,
            indent=2,
            default=str,
        )

    print("\n=== COMPLETE V3 FINAL TOP 20 ===")
    for i, r in enumerate(rows[:20], 1):
        print(
            f"{i:02d}. {r.get('symbol')} {r.get('name','')} | "
            f"final={float(r.get('final_score') or 0):.1f} | "
            f"refined={float(r.get('refined_score') or 0):.1f} | "
            f"chip={float(r.get('chip_score') or 0):+.1f} | "
            f"{r.get('final_phase','')}"
        )


if __name__ == "__main__":
    main()
