import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from taiwan_stock_agent.infrastructure.twse_client import ChipProxyFetcher

WATCHLIST = ROOT / "data" / "electronic_watchlist.json"
OUT = ROOT / "data" / "electronic_chip_results.json"


def clamp(x, lo=0.0, hi=100.0):
    return max(lo, min(hi, x))


def chip_score(proxy):
    if not proxy or not proxy.is_available:
        return None, ["CHIP_DATA_UNAVAILABLE"]

    score = 40.0
    flags = []

    # 法人連續性
    f = int(proxy.foreign_consecutive_buy_days or 0)
    t = int(proxy.trust_consecutive_buy_days or 0)

    if f >= 8:
        score += 16
        flags.append("FOREIGN_CONSEC_8D")
    elif f >= 5:
        score += 12
        flags.append("FOREIGN_CONSEC_5D")
    elif f >= 3:
        score += 8
        flags.append("FOREIGN_CONSEC_3D")

    if t >= 8:
        score += 20
        flags.append("TRUST_CONSEC_8D")
    elif t >= 5:
        score += 15
        flags.append("TRUST_CONSEC_5D")
    elif t >= 3:
        score += 10
        flags.append("TRUST_CONSEC_3D")

    if proxy.institution_buy_2_of_3:
        score += 8
        flags.append("INST_BUY_2_OF_3")

    if proxy.foreign_and_trust_both_buy:
        score += 8
        flags.append("FOREIGN_TRUST_BOTH_BUY")

    cumul = int(proxy.cumul_foreign_20d or 0) + int(proxy.cumul_trust_20d or 0)
    if cumul > 0:
        score += 6
        flags.append("CUMUL_INST_POSITIVE")
    elif cumul < 0:
        score -= 8
        flags.append("CUMUL_INST_NEGATIVE")

    if float(proxy.inst_flow_accel or 0) >= 1.2:
        score += 5
        flags.append("INST_FLOW_ACCEL")

    if float(proxy.inst_accel_3d_10d or 0) >= 1.2:
        score += 4
        flags.append("INST_3D_ACCEL")

    # 融資下降 = 籌碼變乾淨
    m = int(proxy.margin_decline_streak or 0)
    if m >= 8:
        score += 14
        flags.append("MARGIN_DECLINE_8D")
    elif m >= 5:
        score += 10
        flags.append("MARGIN_DECLINE_5D")
    elif m >= 3:
        score += 6
        flags.append("MARGIN_DECLINE_3D")

    # 大戶 / 散戶轉移
    lh = proxy.large_holder_chg_pct
    if lh is not None:
        if lh >= 0.5:
            score += 12
            flags.append("LARGE_HOLDER_ACCUM_PRIME")
        elif lh > 0:
            score += 8
            flags.append("LARGE_HOLDER_ACCUM")
        elif lh < 0:
            score -= 10
            flags.append("LARGE_HOLDER_EXIT")

    rh = proxy.retail_holder_chg_pct
    if rh is not None:
        if rh <= -0.5:
            score += 12
            flags.append("RETAIL_EXIT_PRIME")
        elif rh < 0:
            score += 8
            flags.append("RETAIL_EXIT")
        elif rh > 0:
            score -= 8
            flags.append("RETAIL_INCREASE")

    slh = proxy.super_large_holder_chg_pct
    if slh is not None and slh > 0:
        score += 5
        flags.append("SUPER_LARGE_ACCUM")

    weeks = int(proxy.holder_count_decline_weeks or 0)
    if weeks >= 2:
        score += 7
        flags.append("HOLDER_COUNT_DECLINE_2W")
    elif weeks >= 1:
        score += 4
        flags.append("HOLDER_COUNT_DECLINE_1W")

    # 風險扣分
    if proxy.short_balance_increased:
        score -= 5
        flags.append("SHORT_BALANCE_RISING")

    if float(proxy.sbl_ratio or 0) >= 0.12:
        score -= 5
        flags.append("SBL_HIGH")

    if proxy.is_disposal or proxy.is_trading_halt:
        score -= 30
        flags.append("TRADING_RESTRICTION")

    return round(clamp(score), 1), flags


def final_phase(refined, chip):
    if chip is None:
        if refined >= 78:
            return "A級：型態強但籌碼未確認"
        if refined >= 68:
            return "B級：觀察"
        return "C級：暫不碰"

    final = refined * 0.72 + chip * 0.28

    # A+ 必須型態跟籌碼一起過
    if refined >= 78 and chip >= 58 and final >= 78:
        phase = "A+級：型態＋籌碼確認"
    elif refined >= 72 and chip >= 48 and final >= 70:
        phase = "A級：潛伏"
    elif final >= 60:
        phase = "B級：觀察"
    else:
        phase = "C級：暫不碰"

    return phase


def main():
    if not WATCHLIST.exists():
        raise RuntimeError("electronic_watchlist.json 不存在")

    with WATCHLIST.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    scan_date = date.fromisoformat(payload["scan_date"])
    candidates = (payload.get("stocks") or [])[:40]

    fetcher = ChipProxyFetcher()
    results = []

    for i, row in enumerate(candidates, 1):
        symbol = row["symbol"]
        volume = int(float(row.get("volume") or 0))

        try:
            proxy = fetcher.fetch(
                symbol,
                scan_date,
                today_volume=volume,
            )
            cscore, cflags = chip_score(proxy)

            refined = float(row.get("refined_score") or 0)
            if cscore is None:
                final_score = refined
            else:
                final_score = refined * 0.72 + cscore * 0.28

            enriched = {
                **row,
                "chip_score": cscore,
                "chip_flags": cflags,
                "chip_available": bool(proxy.is_available),
                "foreign_net_buy": int(proxy.foreign_net_buy or 0),
                "trust_net_buy": int(proxy.trust_net_buy or 0),
                "dealer_net_buy": int(proxy.dealer_net_buy or 0),
                "foreign_consecutive_buy_days": int(proxy.foreign_consecutive_buy_days or 0),
                "trust_consecutive_buy_days": int(proxy.trust_consecutive_buy_days or 0),
                "margin_decline_streak": int(proxy.margin_decline_streak or 0),
                "large_holder_chg_pct": proxy.large_holder_chg_pct,
                "retail_holder_chg_pct": proxy.retail_holder_chg_pct,
                "super_large_holder_chg_pct": proxy.super_large_holder_chg_pct,
                "holder_count_decline_weeks": int(proxy.holder_count_decline_weeks or 0),
                "cumul_foreign_20d": int(proxy.cumul_foreign_20d or 0),
                "cumul_trust_20d": int(proxy.cumul_trust_20d or 0),
                "inst_flow_accel": float(proxy.inst_flow_accel or 0),
                "final_score": round(final_score, 1),
                "final_phase": final_phase(refined, cscore),
            }
            results.append(enriched)

            print(
                f"[{i:02d}/{len(candidates)}] {symbol} {row.get('name','')} "
                f"refined={refined:.1f} chip={cscore} "
                f"final={enriched['final_score']:.1f} {enriched['final_phase']}"
            )
        except Exception as e:
            print(f"{symbol} CHIP ERROR: {e}")
            results.append({
                **row,
                "chip_score": None,
                "chip_flags": [f"CHIP_ERROR:{type(e).__name__}"],
                "chip_available": False,
                "final_score": float(row.get("refined_score") or 0),
                "final_phase": final_phase(float(row.get("refined_score") or 0), None),
            })

    results.sort(key=lambda x: x.get("final_score", 0), reverse=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "scan_date": payload.get("scan_date"),
                "count": len(results),
                "stocks": results,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    print("\n=== 型態＋籌碼 最終 TOP 20 ===")
    for i, r in enumerate(results[:20], 1):
        print(
            f"{i:02d}. {r['symbol']} {r['name']} | "
            f"refined={r.get('refined_score',0):.1f} | "
            f"chip={r.get('chip_score')} | "
            f"final={r.get('final_score',0):.1f} | "
            f"{r.get('final_phase')}"
        )


if __name__ == "__main__":
    main()
