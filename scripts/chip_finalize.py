import json
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from taiwan_stock_agent.infrastructure.twse_client import ChipProxyFetcher

WATCHLIST = ROOT / "data" / "electronic_watchlist.json"
FINAL_OUT = ROOT / "data" / "final_scan_results.json"
CACHE_DIR = ROOT / "data" / "cache"


def g(obj, name, default=0):
    value = getattr(obj, name, default)
    return default if value is None else value


def clamp(v, lo=0.0, hi=100.0):
    return max(lo, min(hi, float(v)))


def classify_final(score):
    if score >= 82:
        return "A+級：預備發動"
    if score >= 72:
        return "A級：潛伏"
    if score >= 60:
        return "B級：觀察"
    return "C級：暫不碰"


def chip_score(proxy, volume):
    if not g(proxy, "is_available", False):
        return 50.0, ["CHIP_DATA_NEUTRAL"], 0.0

    score = 50.0
    flags = []

    foreign = float(g(proxy, "foreign_net_buy", 0))
    trust = float(g(proxy, "trust_net_buy", 0))
    dealer = float(g(proxy, "dealer_net_buy", 0))
    vol = max(float(volume or 0), 1.0)

    inst_ratio = (foreign + trust) / vol

    if foreign > 0:
        score += 7
        flags.append("FOREIGN_BUY")
        if foreign / vol >= 0.01:
            score += 5
            flags.append("FOREIGN_BUY_STRONG")
    elif foreign < 0:
        score -= 5
        flags.append("FOREIGN_SELL")

    if trust > 0:
        score += 7
        flags.append("TRUST_BUY")
        if trust / vol >= 0.005:
            score += 4
            flags.append("TRUST_BUY_STRONG")
    elif trust < 0:
        score -= 4
        flags.append("TRUST_SELL")

    if dealer > 0:
        score += 2

    if g(proxy, "foreign_and_trust_both_buy", False):
        score += 7
        flags.append("FOREIGN_TRUST_BOTH_BUY")

    foreign_consec = int(g(proxy, "foreign_consecutive_buy_days", 0))
    trust_consec = int(g(proxy, "trust_consecutive_buy_days", 0))
    dealer_consec = int(g(proxy, "dealer_consecutive_buy_days", 0))

    if foreign_consec >= 3:
        score += min(8, 3 + foreign_consec)
        flags.append(f"FOREIGN_CONSEC_{foreign_consec}")
    if trust_consec >= 3:
        score += min(6, 2 + trust_consec)
        flags.append(f"TRUST_CONSEC_{trust_consec}")
    if dealer_consec >= 3:
        score += 2

    if g(proxy, "institution_buy_2_of_3", False):
        score += 7
        flags.append("INST_BUY_2_OF_3")

    cumul_foreign = float(g(proxy, "cumul_foreign_20d", 0))
    cumul_trust = float(g(proxy, "cumul_trust_20d", 0))
    if cumul_foreign > 0:
        score += 6
        flags.append("FOREIGN_20D_POSITIVE")
    elif cumul_foreign < 0:
        score -= 4
    if cumul_trust > 0:
        score += 5
        flags.append("TRUST_20D_POSITIVE")

    buy_days_ratio = float(g(proxy, "inst_buy_days_ratio", 0))
    if buy_days_ratio >= 0.65:
        score += 6
        flags.append("INST_BUY_DAYS_HIGH")
    elif buy_days_ratio >= 0.55:
        score += 3

    accel = float(g(proxy, "inst_flow_accel", 0))
    if accel >= 1.5:
        score += 6
        flags.append("INST_FLOW_ACCEL")
    elif accel >= 1.15:
        score += 3

    accel_3d = float(g(proxy, "inst_accel_3d_10d", 0))
    if accel_3d >= 1.5:
        score += 5
        flags.append("INST_3D_ACCEL")

    margin_chg = float(g(proxy, "margin_balance_change", 0))
    if margin_chg < 0:
        score += 6
        flags.append("MARGIN_DECLINE")
    elif margin_chg > 0 and inst_ratio <= 0:
        score -= 4
        flags.append("MARGIN_CHASE")

    margin_streak = int(g(proxy, "margin_decline_streak", 0))
    if margin_streak >= 5:
        score += 6
        flags.append("MARGIN_DECLINE_5D")
    elif margin_streak >= 3:
        score += 3
        flags.append("MARGIN_DECLINE_3D")

    margin_util = g(proxy, "margin_utilization_rate", None)
    if margin_util is not None:
        margin_util = float(margin_util)
        if 0 < margin_util < 0.20:
            score += 3
        elif margin_util > 0.80:
            score -= 5
            flags.append("MARGIN_UTIL_HIGH")

    large = float(g(proxy, "large_holder_chg_pct", 0))
    retail = float(g(proxy, "retail_holder_chg_pct", 0))
    if large > 0:
        score += 7
        flags.append("LARGE_HOLDER_UP")
    elif large < 0:
        score -= 4
    if retail < 0:
        score += 7
        flags.append("RETAIL_HOLDER_DOWN")
    elif retail > 0:
        score -= 3
    if large > 0 and retail < 0:
        score += 6
        flags.append("OWNERSHIP_CONCENTRATING")

    super_large = float(g(proxy, "super_large_holder_chg_pct", 0))
    if super_large > 0:
        score += 4
        flags.append("SUPER_LARGE_UP")

    large_2w = float(g(proxy, "large_holder_2w_trend", 0))
    if large_2w > 0:
        score += 4

    holder_chg = float(g(proxy, "holder_count_chg_weekly", 0))
    holder_decline_weeks = int(g(proxy, "holder_count_decline_weeks", 0))
    if holder_chg < 0:
        score += 4
        flags.append("HOLDER_COUNT_DOWN")
    if holder_decline_weeks >= 2:
        score += 4
        flags.append("HOLDER_COUNT_MULTI_WEEK_DOWN")

    short_cover = float(g(proxy, "short_cover_rate", 0))
    if short_cover >= 0.15:
        score += 4
        flags.append("SHORT_COVER_STRONG")
    elif short_cover >= 0.08:
        score += 2

    sbl = float(g(proxy, "sbl_ratio", 0))
    if sbl > 0.10:
        score -= 8
        flags.append("SBL_PRESSURE_HIGH")
    elif sbl > 0.05:
        score -= 4

    daytrade = float(g(proxy, "daytrade_ratio", 0))
    if daytrade > 0.35:
        score -= 5
        flags.append("DAYTRADE_HEAT")

    if g(proxy, "short_balance_increased", False):
        score -= 2

    if g(proxy, "is_disposal", False) or g(proxy, "is_trading_halt", False):
        score -= 25
        flags.append("HARD_RISK_FLAG")
    if g(proxy, "is_daytrade_restricted", False):
        score -= 8

    quality = 1.0
    dq = list(g(proxy, "data_quality_flags", []))
    if dq:
        quality = max(0.35, 1.0 - 0.08 * len(dq))

    return round(clamp(score), 1), flags + dq[:5], round(quality, 2)


def main():
    with WATCHLIST.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    scan_date = date.fromisoformat(payload["scan_date"])
    rows = payload.get("stocks") or []

    # 最終籌碼層只深挖前30檔，避免公開資料端點被打爆
    rows = rows[:30]

    fetcher = ChipProxyFetcher(cache_dir=CACHE_DIR)
    finals = []

    for idx, row in enumerate(rows, 1):
        symbol = row["symbol"]
        volume = int(float(row.get("volume") or 0))

        try:
            proxy = fetcher.fetch(symbol, scan_date, today_volume=volume)
            c_score, c_flags, c_quality = chip_score(proxy, volume)
            chip_available = bool(g(proxy, "is_available", False))
        except Exception as e:
            c_score = 50.0
            c_flags = [f"CHIP_FETCH_ERROR:{type(e).__name__}"]
            c_quality = 0.0
            chip_available = False
            proxy = None

        refined = float(row.get("refined_score") or 0)

        if chip_available:
            # 型態為主、籌碼做最後確認；避免單日籌碼把好型態完全推翻
            final = refined * 0.74 + c_score * 0.26
        else:
            final = refined

        # 已過熱 / 流動性不足沿用結構層風控
        if float(row.get("change_pct") or 0) >= 5:
            final -= 12
        if float(row.get("value") or 0) < 50_000_000:
            final -= 8

        final = round(clamp(final), 1)

        out = dict(row)
        out.update({
            "chip_score": c_score,
            "chip_available": chip_available,
            "chip_quality": c_quality,
            "chip_flags": c_flags,
            "final_score": final,
            "final_phase": classify_final(final),
        })

        if proxy is not None:
            out["chip_snapshot"] = {
                "foreign_net_buy": g(proxy, "foreign_net_buy", 0),
                "trust_net_buy": g(proxy, "trust_net_buy", 0),
                "dealer_net_buy": g(proxy, "dealer_net_buy", 0),
                "foreign_consecutive_buy_days": g(proxy, "foreign_consecutive_buy_days", 0),
                "trust_consecutive_buy_days": g(proxy, "trust_consecutive_buy_days", 0),
                "margin_balance_change": g(proxy, "margin_balance_change", 0),
                "margin_decline_streak": g(proxy, "margin_decline_streak", 0),
                "large_holder_chg_pct": g(proxy, "large_holder_chg_pct", 0),
                "retail_holder_chg_pct": g(proxy, "retail_holder_chg_pct", 0),
                "holder_count_chg_weekly": g(proxy, "holder_count_chg_weekly", 0),
                "inst_flow_accel": g(proxy, "inst_flow_accel", 0),
                "inst_accel_3d_10d": g(proxy, "inst_accel_3d_10d", 0),
            }

        finals.append(out)

        print(
            f"[{idx:02d}/{len(rows)}] {symbol} {row.get('name','')} | "
            f"refined={refined:.1f} chip={c_score:.1f} "
            f"final={final:.1f} {out['final_phase']}"
        )

    finals.sort(key=lambda x: x.get("final_score", 0), reverse=True)

    report = {
        "scan_date": payload.get("scan_date"),
        "model_version": "complete-v1",
        "scoring": {
            "intraday": "latent_score",
            "multi_day": "refined_score",
            "chip": "chip_score",
            "final": "74% refined + 26% chip when chip data available",
        },
        "count": len(finals),
        "a_plus": [x for x in finals if x.get("final_phase","").startswith("A+")],
        "a": [x for x in finals if x.get("final_phase","").startswith("A級")],
        "top_final": finals,
    }

    FINAL_OUT.parent.mkdir(parents=True, exist_ok=True)
    with FINAL_OUT.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # 同步覆寫快速掃描候選池排序，盤中直接沿用 final_score
    with WATCHLIST.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "scan_date": payload.get("scan_date"),
                "model_version": "complete-v1",
                "count": len(finals),
                "stocks": finals,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    print("\n=== 完成版 FINAL TOP 20 ===")
    for i, r in enumerate(finals[:20], 1):
        print(
            f"{i:02d}. {r['symbol']} {r.get('name','')} | "
            f"final {r['final_score']:.1f} | chip {r['chip_score']:.1f} | "
            f"refined {float(r.get('refined_score') or 0):.1f} | "
            f"{r['final_phase']}"
        )


if __name__ == "__main__":
    main()
