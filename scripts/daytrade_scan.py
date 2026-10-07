import json
import math
import time
import urllib.parse
from pathlib import Path

from realtime_scan import API_KEY, FUGLE_BASE, get_json, get_quote, score_stock, calc_abc

OUT = Path("data/daytrade_results.json")
MARKET_RESULTS = Path("data/market_scan_results.json")
FINAL_SIGNAL = Path("data/final_signal_report.json")
ELECTRONIC_WATCHLIST = Path("data/electronic_watchlist.json")

HEADERS = {
    "X-API-KEY": API_KEY,
    "User-Agent": "Mozilla/5.0",
}


def api_get(path, params=None):
    url = f"{FUGLE_BASE}/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    return get_json(url, headers=HEADERS)


def close_strength(row):
    high = float(row.get("highPrice") or row.get("high") or 0)
    low = float(row.get("lowPrice") or row.get("low") or 0)
    close = float(row.get("closePrice") or row.get("price") or 0)
    if high <= low or close <= 0:
        return 0.0
    return max(0.0, min(1.0, (close - low) / (high - low)))


def snapshot_candidates():
    rows = []
    for market in ("TSE", "OTC"):
        body = api_get(
            f"snapshot/quotes/{market}",
            {"type": "COMMONSTOCK"},
        )
        for x in body.get("data") or []:
            symbol = str(x.get("symbol") or "").strip()
            if len(symbol) != 4 or not symbol.isdigit():
                continue

            price = float(x.get("closePrice") or x.get("lastPrice") or 0)
            change = float(x.get("changePercent") or 0)
            value = float(x.get("tradeValue") or 0)
            volume = float(x.get("tradeVolume") or 0)
            high = float(x.get("highPrice") or 0)
            low = float(x.get("lowPrice") or 0)

            if price <= 0 or high <= 0 or low <= 0:
                continue
            if value < 100_000_000:
                continue
            if volume < 1000:
                continue
            if not (-1.5 <= change <= 7.5):
                continue

            cs = close_strength(x)
            if cs < 0.55:
                continue

            pre = 0.0
            if value >= 1_000_000_000:
                pre += 24
            elif value >= 500_000_000:
                pre += 18
            elif value >= 200_000_000:
                pre += 12
            else:
                pre += 6

            if 0.8 <= change <= 4.5:
                pre += 24
            elif 4.5 < change <= 6.5:
                pre += 13
            elif -0.5 <= change < 0.8:
                pre += 8
            elif change > 6.5:
                pre -= 8

            if cs >= 0.88:
                pre += 22
            elif cs >= 0.75:
                pre += 14
            else:
                pre += 6

            day_range = (high - low) / price * 100 if price else 0
            if 1.2 <= day_range <= 5.5:
                pre += 10
            elif day_range > 8:
                pre -= 8

            rows.append({
                "symbol": symbol,
                "name": x.get("name", ""),
                "market": market,
                "price": price,
                "change_pct": change,
                "volume": volume,
                "value": value,
                "high": high,
                "low": low,
                "close_strength": cs,
                "pre_score": round(pre, 1),
                "source": "snapshot",
            })

    rows.sort(key=lambda r: (r["pre_score"], r["value"]), reverse=True)
    return rows[:40]


def fallback_candidates():
    rows = []

    if MARKET_RESULTS.exists():
        try:
            data = json.loads(MARKET_RESULTS.read_text(encoding="utf-8"))
            for x in (data.get("stocks") or {}).values():
                symbol = str(x.get("symbol") or "")
                value = float(x.get("value") or 0)
                change = float(x.get("change_pct") or 0)
                cs = float(x.get("close_strength") or 0)
                price = float(x.get("price") or 0)

                if (
                    len(symbol) == 4
                    and symbol.isdigit()
                    and value >= 100_000_000
                    and -1.5 <= change <= 7.5
                    and cs >= 0.55
                    and price > 0
                ):
                    rows.append({
                        "symbol": symbol,
                        "name": x.get("name", ""),
                        "market": x.get("market", ""),
                        "price": price,
                        "change_pct": change,
                        "volume": float(x.get("volume") or 0),
                        "value": value,
                        "high": float(x.get("high") or 0),
                        "low": float(x.get("low") or 0),
                        "close_strength": cs,
                        "pre_score": float(x.get("latent_score") or 0)
                            + float(x.get("score") or 0) * 0.25,
                        "source": "market_scan_fallback",
                    })
        except Exception as e:
            print(f"market fallback error: {e}")

    if not rows and ELECTRONIC_WATCHLIST.exists():
        try:
            data = json.loads(ELECTRONIC_WATCHLIST.read_text(encoding="utf-8"))
            for x in data.get("stocks") or []:
                rows.append({
                    "symbol": str(x.get("symbol") or ""),
                    "name": x.get("name", ""),
                    "market": x.get("market", ""),
                    "price": float(x.get("price") or 0),
                    "change_pct": float(x.get("change_pct") or 0),
                    "volume": float(x.get("volume") or 0),
                    "value": float(x.get("value") or 0),
                    "high": 0,
                    "low": 0,
                    "close_strength": float(x.get("close_strength") or 0),
                    "pre_score": float(x.get("final_score") or x.get("refined_score") or 0),
                    "source": "watchlist_fallback",
                })
        except Exception as e:
            print(f"watchlist fallback error: {e}")

    rows.sort(key=lambda r: (r["pre_score"], r["value"]), reverse=True)
    return rows[:40]


def get_ticker(symbol):
    return api_get(f"intraday/ticker/{symbol}")


def get_5m(symbol):
    body = api_get(
        f"intraday/candles/{symbol}",
        {"timeframe": "5", "sort": "asc"},
    )
    return body.get("data") or []


def avg(xs):
    return sum(xs) / len(xs) if xs else 0.0


def score_daytrade(base, ticker, bars):
    flags = []
    metrics = {}

    can_day = bool(ticker.get("canDayTrade"))
    can_buy = bool(ticker.get("canBuyDayTrade"))

    if not can_day or not can_buy:
        return 0.0, "不可先買現沖", flags, metrics

    if len(bars) < 6:
        return 0.0, "5分K資料不足", flags, metrics

    closes = [float(x.get("close") or 0) for x in bars]
    highs = [float(x.get("high") or 0) for x in bars]
    lows = [float(x.get("low") or 0) for x in bars]
    vols = [float(x.get("volume") or 0) for x in bars]
    avgs = [float(x.get("average") or 0) for x in bars]

    last = closes[-1]
    if last <= 0:
        return 0.0, "資料異常", flags, metrics

    vwap = avgs[-1] if avgs[-1] > 0 else avg(closes[-5:])
    day_high = max(highs)
    day_low = min(lows)
    value = float(base.get("value") or 0)
    change = float(base.get("change_pct") or 0)

    score = 0.0

    if value >= 1_000_000_000:
        score += 22
        flags.append("LIQUIDITY_PRIME")
    elif value >= 500_000_000:
        score += 18
        flags.append("LIQUIDITY_STRONG")
    elif value >= 200_000_000:
        score += 13
    elif value >= 100_000_000:
        score += 8
    else:
        score -= 10
        flags.append("LIQUIDITY_WEAK")

    vwap_gap = (last / vwap - 1) * 100 if vwap > 0 else 0
    if 0.2 <= vwap_gap <= 2.0:
        score += 17
        flags.append("ABOVE_VWAP_HEALTHY")
    elif 0 <= vwap_gap < 0.2:
        score += 9
        flags.append("HOLDING_VWAP")
    elif vwap_gap > 3.5:
        score -= 8
        flags.append("TOO_FAR_ABOVE_VWAP")
    else:
        score -= 12
        flags.append("BELOW_VWAP")

    near_high = last / day_high if day_high > 0 else 0
    if near_high >= 0.99:
        score += 12
        flags.append("NEAR_INTRADAY_HIGH")
    elif near_high >= 0.975:
        score += 7

    last3 = closes[-3:]
    last3_lows = lows[-3:]
    higher_closes = last3[0] <= last3[1] <= last3[2]
    higher_lows = last3_lows[0] <= last3_lows[1] <= last3_lows[2]

    if higher_closes:
        score += 10
        flags.append("5M_HIGHER_CLOSES")
    if higher_lows:
        score += 8
        flags.append("5M_HIGHER_LOWS")

    prior_high = max(highs[-4:-1])
    breakout = last > prior_high
    if breakout:
        score += 14
        flags.append("5M_BREAKOUT")

    recent_vol = avg(vols[-2:])
    prior_vol = avg(vols[-6:-2])
    vol_accel = recent_vol / prior_vol if prior_vol > 0 else 1.0
    if vol_accel >= 1.6:
        score += 13
        flags.append("5M_VOLUME_ACCEL_PRIME")
    elif vol_accel >= 1.25:
        score += 7
        flags.append("5M_VOLUME_ACCEL")
    elif vol_accel < 0.65:
        score -= 4
        flags.append("5M_VOLUME_FADE")

    ret15 = (last / closes[-4] - 1) * 100 if closes[-4] > 0 else 0
    if 0.3 <= ret15 <= 2.5:
        score += 9
        flags.append("15M_MOMENTUM_HEALTHY")
    elif ret15 > 3.5:
        score -= 7
        flags.append("15M_TOO_HOT")
    elif ret15 < -0.5:
        score -= 6

    if 0.5 <= change <= 4.5:
        score += 10
        flags.append("DAILY_MOVE_HEALTHY")
    elif 4.5 < change <= 6.5:
        score += 4
    elif change > 7:
        score -= 10
        flags.append("DAILY_TOO_EXTENDED")
    elif change < -1:
        score -= 8

    day_range = (day_high - day_low) / last * 100 if last > 0 else 0
    if 1.5 <= day_range <= 5.5:
        score += 5
    elif day_range > 8:
        score -= 7
        flags.append("INTRADAY_RANGE_TOO_WIDE")

    score = round(max(0.0, min(100.0, score)), 1)

    if score >= 78:
        phase = "DT-A+：當沖強候選"
    elif score >= 66:
        phase = "DT-A：可當沖"
    elif score >= 56:
        phase = "DT-B：觀察"
    else:
        phase = "DT-C：不做"

    recent_support = min(lows[-3:])
    stop = max(recent_support, vwap * 0.995) if vwap > 0 else recent_support

    metrics = {
        "can_day_trade": can_day,
        "can_buy_day_trade": can_buy,
        "vwap": round(vwap, 2),
        "vwap_gap_pct": round(vwap_gap, 2),
        "near_intraday_high": round(near_high, 3),
        "volume_accel_5m": round(vol_accel, 2),
        "return_15m_pct": round(ret15, 2),
        "breakout_price": round(prior_high, 2),
        "recent_support": round(recent_support, 2),
        "suggested_stop": round(stop, 2),
        "day_range_pct": round(day_range, 2),
    }
    return score, phase, flags, metrics


def main():
    source = "snapshot"
    try:
        candidates = snapshot_candidates()
        if not candidates:
            raise RuntimeError("snapshot returned no candidates")
    except Exception as e:
        print(f"snapshot unavailable, fallback: {e}")
        candidates = fallback_candidates()
        source = "fallback"

    print(f"candidate source={source}, count={len(candidates)}")

    # 只深挖前 30 檔，避免 API 呼叫過多。
    candidates = candidates[:30]
    results = []

    for i, base in enumerate(candidates, 1):
        symbol = base["symbol"]
        try:
            quote = get_quote(symbol)
            scored = score_stock(quote)
            if scored:
                base.update(scored)
                a, b, c = calc_abc(
                    scored["price"],
                    scored["high"],
                    scored["low"],
                )
                base["a"] = a
                base["b"] = b
                base["c"] = c

            ticker = get_ticker(symbol)
            time.sleep(1.05)
            bars = get_5m(symbol)

            dt_score, dt_phase, dt_flags, dt_metrics = score_daytrade(
                base,
                ticker,
                bars,
            )

            row = {
                **base,
                "dt_score": dt_score,
                "dt_phase": dt_phase,
                "dt_direction": "偏多",
                "dt_flags": dt_flags,
                "dt_metrics": dt_metrics,
            }
            results.append(row)

            print(
                f"[{i:02d}/{len(candidates)}] {symbol} {base.get('name','')} "
                f"DT={dt_score:.1f} {dt_phase}"
            )
        except Exception as e:
            print(f"{symbol} ERROR: {e}")

        time.sleep(1.05)

    results.sort(
        key=lambda x: (
            x.get("dt_score", 0),
            x.get("value", 0),
        ),
        reverse=True,
    )

    strong = [
        x for x in results
        if x.get("dt_score", 0) >= 66
    ]

    payload = {
        "source": source,
        "candidate_count": len(results),
        "strong_count": len(strong),
        "top_daytrade": results[:20],
        "stocks": results,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\n=== 當沖候選 TOP 15 ===")
    for i, r in enumerate(results[:15], 1):
        m = r.get("dt_metrics") or {}
        print(
            f"{i:02d}. {r['symbol']} {r.get('name','')} | "
            f"{r.get('dt_phase')} {r.get('dt_score',0):.1f} | "
            f"價 {float(r.get('price') or 0):.2f} | "
            f"漲跌 {float(r.get('change_pct') or 0):+.2f}% | "
            f"VWAP {m.get('vwap')} | "
            f"突破 {m.get('breakout_price')} | "
            f"停損參考 {m.get('suggested_stop')}"
        )


if __name__ == "__main__":
    main()

# DAYTRADE_V1_TRIGGER
