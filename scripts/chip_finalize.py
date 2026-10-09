import json
from pathlib import Path

from taiwan_stock_agent.domain.practical_score import (
    calculate_practical_score,
    practical_phase,
)
from taiwan_stock_agent.domain.risk_policy import risk_policy
from taiwan_stock_agent.domain.action_tier import action_tier, allocation_weight
from taiwan_stock_agent.domain.regime_v2 import classify_regime_v2
from taiwan_stock_agent.domain.entry_exit import entry_exit_plan
from taiwan_stock_agent.domain.top3_quality import top3_quality
from taiwan_stock_agent.domain.hybrid_action_score import hybrid_action_score
from taiwan_stock_agent.domain.score_confidence import score_confidence
from taiwan_stock_agent.domain.sector_concentration import apply_sector_concentration
from taiwan_stock_agent.domain.segment_stats_loader import load_or_build_segment_stats
from taiwan_stock_agent.domain.oos_tracker import append_signal_snapshot

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "final_signal_report.json"
STRUCTURE_WATCHLIST = ROOT / "data" / "electronic_watchlist.json"
WATCHLIST = ROOT / "data" / "electronic_final_watchlist.json"
OUT = ROOT / "data" / "final_scan_results.json"
HEAT_DIR = ROOT / "data" / "market_heat"
SEGMENT_STATS = ROOT / "data" / "segmented_failure_review.json"
BACKTEST_CSV = ROOT / "data" / "ai_backtest.csv"


def load_json(path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_market_context(scan_date):
    if not HEAT_DIR.exists():
        return None
    files = sorted(HEAT_DIR.glob("heat_*.json"))
    eligible = [p for p in files if p.stem.replace("heat_", "") <= str(scan_date)]
    if not eligible:
        return None
    try:
        data = load_json(eligible[-1])
        industries = list((data.get("industries") or {}).values())
        ret5_values = [
            float(x.get("ret_5d_pct"))
            for x in industries
            if x.get("ret_5d_pct") is not None
        ]
        market_return_5d = (
            sum(ret5_values) / len(ret5_values)
            if ret5_values else None
        )
        return {
            "market_state": data.get("market_state", "mixed"),
            "market_breadth": data.get("market_breadth", 50),
            "market_return_5d": market_return_5d,
        }
    except Exception:
        return None


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

    market_context = load_market_context(actual_date)
    segment_stats, segment_stats_source = load_or_build_segment_stats(
        SEGMENT_STATS,
        BACKTEST_CSV,
    )
    regime_v2 = classify_regime_v2(market_context)
    if market_context is None:
        market_context = {}
    market_context = {**market_context, **regime_v2}

    # Preserve the original model score, then add a second ranking layer that
    # rewards realized momentum/ignition and penalizes stagnant or overextended
    # candidates. This makes the ranking auditable and easy to A/B test.
    for row in rows:
        row["segment_stats"] = segment_stats
        pscore, pflags = calculate_practical_score(row, market_context=market_context)
        row.pop("segment_stats", None)
        row["practical_score"] = pscore
        row["practical_phase"] = practical_phase(pscore)
        row["practical_flags"] = pflags
        row["risk_policy"] = risk_policy(pscore, market_context=market_context)

    model_ranked = sorted(rows, key=lambda x: x.get("final_score", 0), reverse=True)
    rows.sort(
        key=lambda x: (
            x.get("practical_score", 0),
            x.get("final_score", 0),
        ),
        reverse=True,
    )

    for row in rows:
        qscore, qflags = top3_quality(row)
        row["top3_quality_score"] = qscore
        row["top3_quality_flags"] = qflags
        row["hybrid_action_score"] = hybrid_action_score(
            float(row.get("final_score") or 0),
            qscore,
        )
        row["score_confidence"] = score_confidence(row)

    rows.sort(
        key=lambda x: (
            x.get("hybrid_action_score", 0),
            x.get("top3_quality_score", 0),
            x.get("practical_score", 0),
        ),
        reverse=True,
    )

    for rank, row in enumerate(rows, 1):
        row["practical_rank"] = rank
        row["action_tier"] = action_tier(rank, float(row.get("practical_score") or 0))
        row["allocation_weight"] = allocation_weight(rank, float(row.get("practical_score") or 0))
        row["entry_exit_plan"] = entry_exit_plan(row, market_context=market_context)

    primary_top3 = [x for x in rows if x.get("action_tier") == "PRIMARY_TOP3"]
    primary_top3 = apply_sector_concentration(primary_top3)

    report = {
        "scan_date": actual_date,
        "model_version": "complete-v3",
        "ranking_version": "practical-v1",
        "source": payload.get("source", "final_signal_report.json"),
        "market_context": market_context,
        "regime_v2": regime_v2,
        "segment_stats_source": segment_stats_source,
        "segment_stats_sample_n": int(segment_stats.get("sample_n") or 0),
        "pipeline": [
            "intraday_latent",
            "multi_day_structure",
            "chip_refinement",
            "freshness_guard",
            "practical_momentum_overlay",
            "final_ranking",
        ],
        "count": len(rows),
        "practical_a_plus": [
            x for x in rows if str(x.get("practical_phase", "")).startswith("P-A+")
        ],
        "practical_a": [
            x for x in rows if str(x.get("practical_phase", "")).startswith("P-A：")
        ],
        "practical_b": [
            x for x in rows if str(x.get("practical_phase", "")).startswith("P-B")
        ],
        "a_plus": [x for x in rows if str(x.get("final_phase", "")).startswith("A+")],
        "a": [x for x in rows if str(x.get("final_phase", "")).startswith("A級")],
        "b": [x for x in rows if str(x.get("final_phase", "")).startswith("B級")],
        "primary_top3": primary_top3,
        "secondary_top5": [x for x in rows if x.get("action_tier") == "SECONDARY_TOP5"],
        "top_practical": rows,
        "top_model_score": model_ranked,
        "top_final": rows,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)

    append_signal_snapshot(
        report,
        ROOT / "data" / "oos_top3_tracking.csv",
    )

    with WATCHLIST.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "scan_date": actual_date,
                "model_version": "complete-v3",
                "ranking_version": "practical-v1",
                "source": payload.get("source", "final_signal_report.json"),
                "count": len(rows),
                "stocks": rows,
            },
            f,
            ensure_ascii=False,
            indent=2,
            default=str,
        )

    print("\n=== PRACTICAL V1 TOP 20 ===")
    for i, r in enumerate(rows[:20], 1):
        print(
            f"{i:02d}. {r.get('symbol')} {r.get('name','')} | "
            f"practical={float(r.get('practical_score') or 0):.1f} | "
            f"final={float(r.get('final_score') or 0):.1f} | "
            f"surge={float(r.get('surge_score') or 0):.1f} | "
            f"chip={float(r.get('chip_score') or 0):+.1f} | "
            f"{r.get('practical_phase','')}"
        )


if __name__ == "__main__":
    main()
