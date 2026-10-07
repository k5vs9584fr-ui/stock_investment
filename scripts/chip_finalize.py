import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "final_signal_report.json"
WATCHLIST = ROOT / "data" / "electronic_watchlist.json"
OUT = ROOT / "data" / "final_scan_results.json"


def main():
    if not SOURCE.exists():
        raise RuntimeError("final_signal_report.json 不存在")

    with SOURCE.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    rows = payload.get("stocks") or []
    rows.sort(key=lambda x: x.get("final_score", 0), reverse=True)

    report = {
        "scan_date": payload.get("scan_date"),
        "model_version": "complete-v1",
        "pipeline": [
            "intraday_latent",
            "multi_day_structure",
            "light_chip_confirmation",
            "full_chip_refinement",
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

    # 盤中快速掃描直接沿用完成版排名與 chip/final 分數
    with WATCHLIST.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "scan_date": payload.get("scan_date"),
                "model_version": "complete-v1",
                "count": len(rows),
                "stocks": rows,
            },
            f,
            ensure_ascii=False,
            indent=2,
            default=str,
        )

    print("\n=== COMPLETE V1 FINAL TOP 20 ===")
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
