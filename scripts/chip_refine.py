import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from taiwan_stock_agent.infrastructure.twse_client import ChipProxyFetcher  # noqa: E402

WATCHLIST = Path("data/electronic_watchlist.json")
OUT = Path("data/final_signal_report.json")
CACHE_DIR = Path("data/chip_cache")


def safe_num(v, default=0.0):
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def chip_score(proxy):
    if not getattr(proxy, "is_available", False):
        return 0.0, ["CHIP_DATA_UNAVAILABLE"]

    pts = 0.0
    flags = []

    foreign = safe_num(getattr(proxy, "foreign_net_buy", 0))
    trust = safe_num(getattr(proxy, "trust_net_buy", 0))
    dealer = safe_num(getattr(proxy, "dealer_net_buy", 0))

    foreign_days = int(getattr(proxy, "foreign_consecutive_buy_days", 0) or 0)
    trust_days = int(getattr(proxy, "trust_consecutive_buy_days", 0) or 0)
    dealer_days = int(getattr(proxy, "dealer_consecutive_buy_days", 0) or 0)

    if foreign > 0:
        pts += 4
        flags.append("FOREIGN_BUY")
    if trust > 0:
        pts += 4
        flags.append("TRUST_BUY")
    if dealer > 0:
        pts += 1

    if foreign > 0 and trust > 0:
        pts += 6
        flags.append("FOREIGN_TRUST_BOTH_BUY")

    if getattr(proxy, "institution_buy_2_of_3", False):
        pts += 4
        flags.append("INST_2_OF_3")

    if foreign_days >= 5:
        pts += 7
        flags.append("FOREIGN_CONTINUE_5D")
    elif foreign_days >= 3:
        pts += 5
        flags.append("FOREIGN_CONTINUE_3D")
    elif foreign_days >= 2:
        pts += 2

    if trust_days >= 3:
        pts += 6
        flags.append("TRUST_CONTINUE_3D")
    elif trust_days >= 2:
        pts += 3

    if dealer_days >= 3:
        pts += 1

    inst_buy_pct = getattr(proxy, "inst_buy_pct", None)
    if inst_buy_pct is not None:
        inst_buy_pct = safe_num(inst_buy_pct)
        if inst_buy_pct >= 0.08:
            pts += 7
            flags.append("INST_BUY_INTENSE")
        elif inst_buy_pct >= 0.04:
            pts += 5
            flags.append("INST_BUY_STRONG")
        elif inst_buy_pct >= 0.015:
            pts += 2

    cf20 = safe_num(getattr(proxy, "cumul_foreign_20d", 0))
    ct20 = safe_num(getattr(proxy, "cumul_trust_20d", 0))
    if cf20 > 0:
        pts += 3
        flags.append("FOREIGN_20D_POS")
    if ct20 > 0:
        pts += 3
        flags.append("TRUST_20D_POS")
    if cf20 > 0 and ct20 > 0:
        pts += 3
        flags.append("DUAL_INST_20D")

    buy_days_ratio = safe_num(getattr(proxy, "inst_buy_days_ratio", 0))
    if buy_days_ratio >= 0.65:
        pts += 5
        flags.append("INST_BUY_DAYS_PRIME")
    elif buy_days_ratio >= 0.5:
        pts += 3

    accel = safe_num(getattr(proxy, "inst_flow_accel", 0))
    if accel > 0:
        pts += 3
        flags.append("INST_FLOW_ACCEL")

    accel3 = safe_num(getattr(proxy, "inst_accel_3d_10d", 0))
    if accel3 >= 1.5:
        pts += 4
        flags.append("INST_3D_ACCEL")
    elif accel3 > 1:
        pts += 2

    margin_chg = safe_num(getattr(proxy, "margin_balance_change", 0))
    margin_streak = int(getattr(proxy, "margin_decline_streak", 0) or 0)
    if margin_chg < 0:
        pts += 5
        flags.append("MARGIN_DECLINE")
    elif margin_chg > 0 and foreign + trust <= 0:
        pts -= 4
        flags.append("MARGIN_RETAIL_CHASE")

    if margin_streak >= 5:
        pts += 5
        flags.append("MARGIN_DECLINE_5D")
    elif margin_streak >= 3:
        pts += 3
        flags.append("MARGIN_DECLINE_3D")

    large = safe_num(getattr(proxy, "large_holder_chg_pct", 0))
    retail = safe_num(getattr(proxy, "retail_holder_chg_pct", 0))
    super_large = safe_num(getattr(proxy, "super_large_holder_chg_pct", 0))
    large2w = safe_num(getattr(proxy, "large_holder_2w_trend", 0))

    if large > 0 and retail < 0:
        pts += 10
        flags.append("LARGE_UP_RETAIL_DOWN")
    elif large > 0:
        pts += 5
        flags.append("LARGE_HOLDER_UP")
    elif large < 0 and retail > 0:
        pts -= 8
        flags.append("LARGE_DOWN_RETAIL_UP")

    if super_large > 0:
        pts += 4
        flags.append("SUPER_LARGE_UP")
    elif super_large < 0:
        pts -= 3

    if large2w > 0:
        pts += 4
        flags.append("LARGE_2W_UP")
    elif large2w < 0:
        pts -= 4

    holder_count_chg = safe_num(getattr(proxy, "holder_count_chg_weekly", 0))
    holder_decline_weeks = int(getattr(proxy, "holder_count_decline_weeks", 0) or 0)
    if holder_count_chg < 0:
        pts += 3
        flags.append("HOLDER_COUNT_DOWN")
    if holder_decline_weeks >= 2:
        pts += 3
        flags.append("HOLDER_COUNT_DOWN_2W")

    margin_util = getattr(proxy, "margin_utilization_rate", None)
    if margin_util is not None:
        margin_util = safe_num(margin_util)
        if 0 < margin_util < 0.20:
            pts += 3
            flags.append("MARGIN_UTIL_LOW")
        elif margin_util > 0.70:
            pts -= 4
            flags.append("MARGIN_UTIL_HIGH")

    daytrade = getattr(proxy, "daytrade_ratio", None)
    if daytrade is not None:
        daytrade = safe_num(daytrade)
        if daytrade > 0.45:
            pts -= 8
            flags.append("DAYTRADE_OVERHEAT")
        elif daytrade > 0.35:
            pts -= 4

    sbl = safe_num(getattr(proxy, "sbl_ratio", 0))
    if sbl > 0.10:
        pts -= 6
        flags.append("SBL_HIGH")
    elif sbl > 0.05:
        pts -= 3

    short_cover = safe_num(getattr(proxy, "short_cover_rate", 0))
    if short_cover >= 0.15:
        pts += 4
        flags.append("SHORT_COVER_STRONG")
    elif short_cover >= 0.08:
        pts += 2

    return round(max(-20.0, min(100.0, pts)), 1), flags


def classify(score, chip_score, coverage):
    if coverage == "unavailable":
        if score >= 72:
            return "A級：型態強但籌碼未確認"
        if score >= 60:
            return "B級：觀察"
        return "C級：暫不碰"

    if score >= 88 and chip_score >= 35:
        return "S級：高信心預備發動"
    if score >= 78 and chip_score >= 20:
        return "A+級：型態＋籌碼確認"
    if score >= 68:
        return "A級：潛伏"
    if score >= 58:
        return "B級：觀察"
    return "C級：暫不碰"


def proxy_to_dict(proxy):
    fields = [
        "foreign_net_buy",
        "trust_net_buy",
        "dealer_net_buy",
        "foreign_consecutive_buy_days",
        "trust_consecutive_buy_days",
        "dealer_consecutive_buy_days",
        "margin_balance_change",
        "margin_decline_streak",
        "margin_utilization_rate",
        "institution_buy_2_of_3",
        "inst_buy_pct",
        "foreign_and_trust_both_buy",
        "cumul_foreign_20d",
        "cumul_trust_20d",
        "inst_buy_days_ratio",
        "inst_flow_accel",
        "inst_accel_3d_10d",
        "large_holder_chg_pct",
        "retail_holder_chg_pct",
        "super_large_holder_chg_pct",
        "large_holder_2w_trend",
        "holder_count_chg_weekly",
        "holder_count_decline_weeks",
        "daytrade_ratio",
        "sbl_ratio",
        "short_cover_rate",
        "short_margin_ratio",
        "is_available",
        "data_quality_flags",
    ]
    return {k: getattr(proxy, k, None) for k in fields}


def main():
    with WATCHLIST.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    scan_date = payload.get("scan_date")
    trade_date = datetime.strptime(scan_date, "%Y-%m-%d").date()

    rows = (payload.get("stocks") or [])[:30]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    fetcher = ChipProxyFetcher(cache_dir=CACHE_DIR)

    output = []

    for i, row in enumerate(rows, 1):
        symbol = row["symbol"]
        volume_lots = safe_num(row.get("volume"), 0)
        today_volume_shares = int(volume_lots * 1000)

        try:
            proxy = fetcher.fetch(
                ticker=symbol,
                trade_date=trade_date,
                today_volume=today_volume_shares,
            )
            c_score, c_flags = chip_score(proxy)
        except Exception as exc:
            proxy = None
            c_score = 0.0
            c_flags = [f"CHIP_FETCH_ERROR:{type(exc).__name__}"]
            print(
                f"[{i:02d}/{len(rows)}] {symbol} "
                f"chip fetch failed: {type(exc).__name__}: {exc}"
            )

        refined = safe_num(row.get("refined_score"), 0)

        chip_data = proxy_to_dict(proxy) if proxy is not None else {}

        if proxy is None or not getattr(proxy, "is_available", False):
            coverage = "unavailable"
            chip_component = 50.0
            final = refined * 0.92
        else:
            has_ownership = (
                chip_data.get("large_holder_chg_pct") is not None
                or chip_data.get("retail_holder_chg_pct") is not None
            )
            coverage = "full" if has_ownership else "institutional_partial"

            # 籌碼原始分不是 0~100 機率，轉成中性 45 起跳的確認分，
            # 避免單日法人買超把整體分數灌太高。
            chip_component = max(0.0, min(100.0, 45.0 + c_score * 0.55))
            final = refined * 0.68 + chip_component * 0.32

        # 最愛條件：大戶增 + 散戶減
        if "LARGE_UP_RETAIL_DOWN" in c_flags:
            final += 3

        # 籌碼極差則限縮上限，避免純技術漂亮硬上榜
        if "LARGE_DOWN_RETAIL_UP" in c_flags:
            final = min(final, 58)

        row2 = dict(row)
        row2.update(
            {
                "chip_score": c_score,
                "chip_component": round(chip_component, 1),
                "chip_flags": c_flags,
                "chip_data": chip_data,
                "chip_coverage": coverage,
                "final_score": round(max(0, min(100, final)), 1),
            }
        )
        row2["final_phase"] = classify(
            row2["final_score"], c_score, coverage
        )
        output.append(row2)

        print(
            f"[{i:02d}/{len(rows)}] {symbol} {row.get('name','')} "
            f"refined={refined:.1f} chip={c_score:+.1f} "
            f"final={row2['final_score']:.1f} {row2['final_phase']}"
        )

    output.sort(key=lambda x: x.get("final_score", 0), reverse=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "scan_date": scan_date,
                "count": len(output),
                "stocks": output,
            },
            f,
            ensure_ascii=False,
            indent=2,
            default=str,
        )

    print("\n=== FINAL TOP 20 ===")
    for i, r in enumerate(output[:20], 1):
        print(
            f"{i:02d}. {r['symbol']} {r['name']} | "
            f"final={r['final_score']:.1f} | "
            f"refined={r.get('refined_score',0):.1f} | "
            f"chip={r.get('chip_score',0):+.1f} | "
            f"{r['final_phase']}"
        )


if __name__ == "__main__":
    main()

# trigger: chip refine validation
