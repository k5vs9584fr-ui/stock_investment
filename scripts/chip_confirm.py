# workflow-trigger: chip-layer-v2-light
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


def fetch_light_chip(fetcher, ticker, trade_date):
    """Fast confirmation layer.

    Only fetch the high-value signals needed for pre-breakout confirmation:
    today's foreign/trust flow, today's margin change, and weekly TDCC
    large/retail holder transfer. Heavy 20-day institutional/SBL/daytrade
    history is deliberately excluded from this fast pass.
    """
    flags = []

    foreign, trust, dealer = fetcher._fetch_t86_data(
        ticker, trade_date, flags
    )
    margin_change = fetcher._fetch_margin_balance_change(
        ticker, trade_date, flags
    )

    (
        large_chg,
        retail_chg,
        super_large_chg,
        super_large_count_chg,
        large_2w_trend,
        holder_count_chg,
        holder_decline_weeks,
    ) = fetcher._fetch_tdcc_ownership(ticker, trade_date)

    available = any(
        x is not None
        for x in [
            foreign,
            trust,
            dealer,
            margin_change,
            large_chg,
            retail_chg,
        ]
    )

    return {
        "available": available,
        "foreign_net_buy": int(foreign or 0),
        "trust_net_buy": int(trust or 0),
        "dealer_net_buy": int(dealer or 0),
        "margin_balance_change": int(margin_change or 0),
        "large_holder_chg_pct": large_chg,
        "retail_holder_chg_pct": retail_chg,
        "super_large_holder_chg_pct": super_large_chg,
        "super_large_holder_count_chg": super_large_count_chg,
        "large_holder_2w_trend": large_2w_trend,
        "holder_count_chg_weekly": holder_count_chg,
        "holder_count_decline_weeks": int(holder_decline_weeks or 0),
        "data_quality_flags": flags,
    }


def chip_score(chip):
    if not chip or not chip.get("available"):
        return None, ["CHIP_DATA_UNAVAILABLE"]

    score = 45.0
    flags = []

    foreign = chip.get("foreign_net_buy", 0)
    trust = chip.get("trust_net_buy", 0)
    margin_change = chip.get("margin_balance_change", 0)

    # Today institutional flow: confirmation, not the main setup driver.
    if foreign > 0:
        score += 8
        flags.append("FOREIGN_BUY")
    elif foreign < 0:
        score -= 6
        flags.append("FOREIGN_SELL")

    if trust > 0:
        score += 10
        flags.append("TRUST_BUY")
    elif trust < 0:
        score -= 7
        flags.append("TRUST_SELL")

    if foreign > 0 and trust > 0:
        score += 8
        flags.append("FOREIGN_TRUST_BOTH_BUY")

    # Margin decreasing while price structure holds = cleaner chips.
    if margin_change < 0:
        score += 8
        flags.append("MARGIN_DECREASE")
    elif margin_change > 0:
        score -= 5
        flags.append("MARGIN_INCREASE")

    # Core preference: large holders accumulating + retail leaving.
    large = chip.get("large_holder_chg_pct")
    if large is not None:
        if large >= 1.0:
            score += 18
            flags.append("LARGE_HOLDER_ACCUM_PRIME")
        elif large >= 0.5:
            score += 14
            flags.append("LARGE_HOLDER_ACCUM_STRONG")
        elif large > 0:
            score += 9
            flags.append("LARGE_HOLDER_ACCUM")
        elif large < 0:
            score -= 12
            flags.append("LARGE_HOLDER_EXIT")

    retail = chip.get("retail_holder_chg_pct")
    if retail is not None:
        if retail <= -1.0:
            score += 18
            flags.append("RETAIL_EXIT_PRIME")
        elif retail <= -0.5:
            score += 14
            flags.append("RETAIL_EXIT_STRONG")
        elif retail < 0:
            score += 9
            flags.append("RETAIL_EXIT")
        elif retail > 0:
            score -= 10
            flags.append("RETAIL_INCREASE")

    super_large = chip.get("super_large_holder_chg_pct")
    if super_large is not None and super_large > 0:
        score += 6
        flags.append("SUPER_LARGE_ACCUM")

    large_2w = chip.get("large_holder_2w_trend")
    if large_2w is not None:
        if large_2w > 0:
            score += 5
            flags.append("LARGE_HOLDER_2W_UP")
        elif large_2w < 0:
            score -= 4
            flags.append("LARGE_HOLDER_2W_DOWN")

    weeks = int(chip.get("holder_count_decline_weeks") or 0)
    if weeks >= 2:
        score += 7
        flags.append("HOLDER_COUNT_DECLINE_2W")
    elif weeks >= 1:
        score += 4
        flags.append("HOLDER_COUNT_DECLINE_1W")

    return round(clamp(score), 1), flags


def final_phase(refined, chip):
    if chip is None:
        if refined >= 78:
            return "A級：型態強但籌碼未確認"
        if refined >= 68:
            return "B級：觀察"
        return "C級：暫不碰"

    final = refined * 0.72 + chip * 0.28

    if refined >= 78 and chip >= 58 and final >= 78:
        return "A+級：型態＋籌碼確認"
    if refined >= 72 and chip >= 48 and final >= 70:
        return "A級：潛伏"
    if final >= 60:
        return "B級：觀察"
    return "C級：暫不碰"


def save_partial(scan_date, results):
    ranked = sorted(
        results,
        key=lambda x: x.get("final_score", 0),
        reverse=True,
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "scan_date": scan_date,
                "count": len(ranked),
                "stocks": ranked,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )


def main():
    if not WATCHLIST.exists():
        raise RuntimeError("electronic_watchlist.json 不存在")

    with WATCHLIST.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    scan_date = date.fromisoformat(payload["scan_date"])
    candidates = (payload.get("stocks") or [])[:12]

    fetcher = ChipProxyFetcher()
    results = []

    for i, row in enumerate(candidates, 1):
        symbol = row["symbol"]

        try:
            chip = fetch_light_chip(fetcher, symbol, scan_date)
            cscore, cflags = chip_score(chip)

            refined = float(row.get("refined_score") or 0)
            final_score = (
                refined
                if cscore is None
                else refined * 0.72 + cscore * 0.28
            )

            enriched = {
                **row,
                **chip,
                "chip_score": cscore,
                "chip_flags": cflags,
                "chip_available": bool(chip.get("available")),
                "final_score": round(final_score, 1),
                "final_phase": final_phase(refined, cscore),
            }
            results.append(enriched)
            save_partial(payload.get("scan_date"), results)

            print(
                f"[{i:02d}/{len(candidates)}] {symbol} {row.get('name','')} "
                f"refined={refined:.1f} chip={cscore} "
                f"final={enriched['final_score']:.1f} "
                f"{enriched['final_phase']}"
            )
        except Exception as e:
            print(f"{symbol} CHIP ERROR: {e}")
            results.append({
                **row,
                "chip_score": None,
                "chip_flags": [f"CHIP_ERROR:{type(e).__name__}"],
                "chip_available": False,
                "final_score": float(row.get("refined_score") or 0),
                "final_phase": final_phase(
                    float(row.get("refined_score") or 0),
                    None,
                ),
            })
            save_partial(payload.get("scan_date"), results)

    results.sort(
        key=lambda x: x.get("final_score", 0),
        reverse=True,
    )
    save_partial(payload.get("scan_date"), results)

    print("\n=== 型態＋籌碼 最終 TOP 12 ===")
    for i, r in enumerate(results, 1):
        print(
            f"{i:02d}. {r['symbol']} {r['name']} | "
            f"refined={r.get('refined_score',0):.1f} | "
            f"chip={r.get('chip_score')} | "
            f"final={r.get('final_score',0):.1f} | "
            f"{r.get('final_phase')}"
        )


if __name__ == "__main__":
    main()
