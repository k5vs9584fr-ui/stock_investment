import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from taiwan_stock_agent.infrastructure.twse_client import ChipProxyFetcher

WATCHLIST = ROOT / "data" / "electronic_watchlist.json"
OUT = ROOT / "data" / "electronic_final_watchlist.json"


def clamp(v, lo=0.0, hi=100.0):
    return max(lo, min(hi, v))


def chip_score(proxy):
    if not proxy.is_available:
        return 45.0, ["CHIP_UNAVAILABLE"], "UNAVAILABLE"

    score = 50.0
    flags = []

    fn = proxy.foreign_net_buy
    tn = proxy.trust_net_buy
    dn = proxy.dealer_net_buy

    if fn > 0:
        score += 8
        flags.append("FOREIGN_BUY")
    elif fn < 0:
        score -= 6
        flags.append("FOREIGN_SELL")

    if tn > 0:
        score += 8
        flags.append("TRUST_BUY")
    elif tn < 0:
        score -= 5
        flags.append("TRUST_SELL")

    if dn > 0:
        score += 3
        flags.append("DEALER_BUY")
    elif dn < 0:
        score -= 2

    if proxy.foreign_and_trust_both_buy:
        score += 6
        flags.append("FOREIGN_TRUST_BOTH_BUY")

    if proxy.institution_buy_2_of_3:
        score += 8
        flags.append("INST_BUY_2_OF_3")

    if proxy.foreign_consecutive_buy_days >= 5:
        score += 8
        flags.append("FOREIGN_CONTINUITY_5D")
    elif proxy.foreign_consecutive_buy_days >= 3:
        score += 5
        flags.append("FOREIGN_CONTINUITY_3D")
    elif proxy.foreign_consecutive_buy_days >= 2:
        score += 2

    if proxy.trust_consecutive_buy_days >= 3:
        score += 6
        flags.append("TRUST_CONTINUITY_3D")
    elif proxy.trust_consecutive_buy_days >= 2:
        score += 3

    if proxy.dealer_consecutive_buy_days >= 3:
        score += 2

    if proxy.cumul_foreign_20d > 0 and proxy.cumul_trust_20d > 0:
        score += 6
        flags.append("DUAL_INST_20D_POSITIVE")

    if proxy.inst_buy_days_ratio >= 0.65:
        score += 6
        flags.append("INST_BUY_DAYS_HIGH")
    elif proxy.inst_buy_days_ratio >= 0.55:
        score += 3
    elif 0 < proxy.inst_buy_days_ratio < 0.40:
        score -= 3

    if proxy.inst_flow_accel >= 1.5:
        score += 7
        flags.append("INST_FLOW_ACCEL_STRONG")
    elif proxy.inst_flow_accel >= 1.15:
        score += 4
        flags.append("INST_FLOW_ACCEL")
    elif 0 < proxy.inst_flow_accel < 0.75:
        score -= 4
        flags.append("INST_FLOW_SLOWING")

    if proxy.foreign_trend_accel >= 1.3:
        score += 4
        flags.append("FOREIGN_TREND_ACCEL")

    if proxy.inst_accel_3d_10d >= 1.3:
        score += 4
        flags.append("INST_3D_ACCEL")

    if proxy.margin_balance_change < 0:
        score += 6
        flags.append("MARGIN_DECLINE")
    elif proxy.margin_balance_change > 0:
        score -= 3
        flags.append("MARGIN_INCREASE")

    if proxy.margin_decline_streak >= 5:
        score += 7
        flags.append("MARGIN_DECLINE_5D")
    elif proxy.margin_decline_streak >= 3:
        score += 4
        flags.append("MARGIN_DECLINE_3D")
    elif proxy.margin_decline_streak >= 1:
        score += 2

    if proxy.margin_utilization_rate is not None:
        if proxy.margin_utilization_rate < 0.20:
            score += 3
            flags.append("LOW_MARGIN_UTIL")
        elif proxy.margin_utilization_rate > 0.75:
            score -= 5
            flags.append("HIGH_MARGIN_UTIL")

    if proxy.large_holder_chg_pct is not None:
        if proxy.large_holder_chg_pct > 0:
            score += 7
            flags.append("LARGE_HOLDER_UP")
        elif proxy.large_holder_chg_pct < 0:
            score -= 7
            flags.append("LARGE_HOLDER_DOWN")

    if proxy.retail_holder_chg_pct is not None:
        if proxy.retail_holder_chg_pct < 0:
            score += 7
            flags.append("RETAIL_EXIT")
        elif proxy.retail_holder_chg_pct > 0:
            score -= 5
            flags.append("RETAIL_INFLOW")

    if (
        proxy.large_holder_chg_pct is not None
        and proxy.retail_holder_chg_pct is not None
        and proxy.large_holder_chg_pct > 0
        and proxy.retail_holder_chg_pct < 0
    ):
        score += 5
        flags.append("OWNERSHIP_CONCENTRATING")

    if proxy.super_large_holder_chg_pct is not None and proxy.super_large_holder_chg_pct > 0:
        score += 4
        flags.append("SUPER_LARGE_UP")

    if proxy.super_large_holder_count_chg is not None and proxy.super_large_holder_count_chg > 0:
        score += 2

    if proxy.large_holder_2w_trend is not None and proxy.large_holder_2w_trend > 0:
        score += 4
        flags.append("LARGE_HOLDER_2W_UP")

    if proxy.holder_count_chg_weekly is not None and proxy.holder_count_chg_weekly < 0:
        score += 3
        flags.append("HOLDER_COUNT_DOWN")

    if proxy.holder_count_decline_weeks >= 2:
        score += 5
        flags.append("HOLDER_COUNT_DECLINE_2W")
    elif proxy.holder_count_decline_weeks >= 1:
        score += 2

    if proxy.sbl_available:
        if proxy.sbl_ratio > 0.10:
            score -= 8
            flags.append("SBL_PRESSURE_HIGH")
        elif proxy.sbl_ratio > 0.05:
            score -= 4
            flags.append("SBL_PRESSURE")

    if proxy.daytrade_ratio is not None and proxy.daytrade_ratio > 0.40:
        score -= 5
        flags.append("DAYTRADE_HEAT")

    if proxy.short_balance_increased:
        score -= 3
        flags.append("SHORT_BALANCE_RISING")

    if proxy.short_margin_ratio > 0.40 and proxy.short_cover_rate > 0.15:
        score += 4
        flags.append("SHORT_SQUEEZE_SETUP")

    if proxy.is_disposal:
        score -= 25
        flags.append("DISPOSAL")
    if proxy.is_trading_halt:
        score = 0
        flags.append("TRADING_HALT")

    score = round(clamp(score), 1)

    if score >= 65:
        status = "CONFIRMED"
    elif score >= 50:
        status = "NEUTRAL"
    else:
        status = "WEAK"

    return score, flags, status


def final_phase(final_score, chip_status):
    if chip_status == "UNAVAILABLE":
        if final_score >= 70:
            return "A級：潛伏（籌碼待確認）"
        if final_score >= 60:
            return "B級：觀察"
        return "C級：暫不碰"

    if final_score >= 80 and chip_status == "CONFIRMED":
        return "A+級：預備發動"
    if final_score >= 70:
        return "A級：潛伏"
    if final_score >= 60:
        return "B級：觀察"
    return "C級：暫不碰"


def main():
    if not WATCHLIST.exists():
        raise RuntimeError("electronic_watchlist.json 不存在")

    with WATCHLIST.open("r", encoding="utf-8") as f:
        data = json.load(f)

    scan_date = date.fromisoformat(data["scan_date"])
    rows = data.get("stocks") or []

    fetcher = ChipProxyFetcher()
    out = []

    for i, row in enumerate(rows, 1):
        ticker = str(row.get("symbol", ""))
        volume = int(float(row.get("volume") or 0))

        try:
            proxy = fetcher.fetch(
                ticker=ticker,
                trade_date=scan_date,
                today_volume=volume,
            )

            c_score, c_flags, c_status = chip_score(proxy)
            refined = float(row.get("refined_score") or 0)

            if c_status == "UNAVAILABLE":
                f_score = refined * 0.94
            else:
                f_score = refined * 0.68 + c_score * 0.32
                if c_score >= 70:
                    f_score += 3
                elif c_score < 40:
                    f_score -= 5

            if proxy.is_disposal or proxy.is_trading_halt:
                f_score = 0

            f_score = round(clamp(f_score), 1)

            enriched = {
                **row,
                "chip_score": c_score,
                "chip_status": c_status,
                "chip_flags": c_flags,
                "final_score": f_score,
                "final_phase": final_phase(f_score, c_status),
                "chip": {
                    "foreign_net_buy": proxy.foreign_net_buy,
                    "trust_net_buy": proxy.trust_net_buy,
                    "dealer_net_buy": proxy.dealer_net_buy,
                    "foreign_consecutive_buy_days": proxy.foreign_consecutive_buy_days,
                    "trust_consecutive_buy_days": proxy.trust_consecutive_buy_days,
                    "dealer_consecutive_buy_days": proxy.dealer_consecutive_buy_days,
                    "institution_buy_2_of_3": proxy.institution_buy_2_of_3,
                    "cumul_foreign_20d": proxy.cumul_foreign_20d,
                    "cumul_trust_20d": proxy.cumul_trust_20d,
                    "inst_buy_days_ratio": round(proxy.inst_buy_days_ratio, 3),
                    "inst_flow_accel": round(proxy.inst_flow_accel, 3),
                    "foreign_trend_accel": round(proxy.foreign_trend_accel, 3),
                    "inst_accel_3d_10d": round(proxy.inst_accel_3d_10d, 3),
                    "margin_balance_change": proxy.margin_balance_change,
                    "margin_decline_streak": proxy.margin_decline_streak,
                    "margin_utilization_rate": proxy.margin_utilization_rate,
                    "large_holder_chg_pct": proxy.large_holder_chg_pct,
                    "retail_holder_chg_pct": proxy.retail_holder_chg_pct,
                    "super_large_holder_chg_pct": proxy.super_large_holder_chg_pct,
                    "super_large_holder_count_chg": proxy.super_large_holder_count_chg,
                    "large_holder_2w_trend": proxy.large_holder_2w_trend,
                    "holder_count_chg_weekly": proxy.holder_count_chg_weekly,
                    "holder_count_decline_weeks": proxy.holder_count_decline_weeks,
                    "sbl_ratio": round(proxy.sbl_ratio, 4),
                    "sbl_available": proxy.sbl_available,
                    "daytrade_ratio": proxy.daytrade_ratio,
                    "short_margin_ratio": round(proxy.short_margin_ratio, 4),
                    "short_cover_rate": round(proxy.short_cover_rate, 4),
                    "is_available": proxy.is_available,
                    "data_quality_flags": proxy.data_quality_flags,
                },
            }
            out.append(enriched)

            print(
                f"[{i:02d}/{len(rows)}] {ticker} {row.get('name','')} "
                f"refined={refined:.1f} chip={c_score:.1f} "
                f"final={f_score:.1f} {enriched['final_phase']}"
            )
        except Exception as e:
            fallback = {
                **row,
                "chip_score": 45.0,
                "chip_status": "UNAVAILABLE",
                "chip_flags": [f"CHIP_ERROR:{type(e).__name__}"],
                "final_score": round(float(row.get("refined_score") or 0) * 0.94, 1),
                "final_phase": final_phase(
                    float(row.get("refined_score") or 0) * 0.94,
                    "UNAVAILABLE",
                ),
                "chip": {"is_available": False, "error": str(e)},
            }
            out.append(fallback)
            print(f"[{i:02d}/{len(rows)}] {ticker} ERROR: {e}")

    out.sort(key=lambda x: x.get("final_score", 0), reverse=True)

    payload = {
        "scan_date": data.get("scan_date"),
        "count": len(out),
        "stocks": out,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print("\n=== FINAL TOP 20 ===")
    for i, r in enumerate(out[:20], 1):
        print(
            f"{i:02d}. {r['symbol']} {r['name']} | "
            f"refined {r.get('refined_score',0):.1f} | "
            f"chip {r.get('chip_score',0):.1f} | "
            f"final {r.get('final_score',0):.1f} | "
            f"{r.get('final_phase','')}"
        )


if __name__ == "__main__":
    main()
