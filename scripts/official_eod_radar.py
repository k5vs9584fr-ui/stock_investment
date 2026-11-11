"""Keyless official TWSE/TPEx after-close market radar. Not an intraday feed."""
import json
import re
import html
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "official_eod_radar.json"
UNIVERSE = ROOT / "data" / "stock_universe.json"
URLS = {
    "TWSE": "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL",
    "TPEx": "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes",
}


def num(value):
    s = str(value if value is not None else "").replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def roc_date(raw):
    s = str(raw or "").strip().replace("/", "").replace("-", "")
    if len(s) == 7 and s.isdigit():
        return date(int(s[:3]) + 1911, int(s[3:5]), int(s[5:]))
    if len(s) == 8 and s.isdigit():
        return date(int(s[:4]), int(s[4:6]), int(s[6:]))
    raise ValueError(f"Bad exchange date: {raw!r}")


def parse_row(r, market):
    if market == "TWSE":
        code = str(r.get("Code") or "").strip()
        name = str(r.get("Name") or "").strip()
        price, delta = num(r.get("ClosingPrice")), num(r.get("Change"))
        high, low = num(r.get("HighestPrice")), num(r.get("LowestPrice"))
        value, volume = num(r.get("TradeValue")), num(r.get("TradeVolume"))
    else:
        code = str(r.get("SecuritiesCompanyCode") or "").strip()
        name = str(r.get("CompanyName") or "").strip()
        price, delta = num(r.get("Close")), num(r.get("Change"))
        high, low = num(r.get("High")), num(r.get("Low"))
        value, volume = num(r.get("TransactionAmount")), num(r.get("TradingShares"))
    if not re.fullmatch(r"\d{4}", code) or None in (price, delta, value, volume):
        return None
    prev = price - delta
    if price <= 0 or prev <= 0 or value <= 0 or volume <= 0:
        return None
    change_pct = 100 * delta / prev
    strength = ((price - low) / (high - low)) if high is not None and low is not None and high > low else None
    return dict(symbol=code, name=name, market=market, close=price,
                change_pct=round(change_pct, 2), change=delta,
                high=high, low=low, value=value, volume=volume,
                close_strength=round(max(0, min(strength, 1)), 3) if strength is not None else None)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=35) as response:
        data = json.load(response)
    if not isinstance(data, list) or not data:
        raise RuntimeError("Official exchange feed returned empty or non-list data")
    return data



def twse_dated_rows(target):
    """Fallback to the dated TWSE report when OpenAPI daily snapshot lags."""
    url = ("https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?"
           f"date={target.strftime('%Y%m%d')}&type=ALLBUT0999&response=json")
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0", "Accept": "application/json"
    })
    with urllib.request.urlopen(req, timeout=35) as response:
        data = json.load(response)
    if data.get("stat") != "OK":
        raise RuntimeError(f"TWSE_DATED_REPORT_NOT_READY: {data.get('stat')}")
    candidates = []
    for table in data.get("tables") or []:
        fields = [str(x).strip() for x in table.get("fields") or []]
        required = {"證券代號", "證券名稱", "成交股數", "成交金額",
                    "最高價", "最低價", "收盤價", "漲跌價差"}
        if not required.issubset(fields):
            continue
        positions = {x: i for i, x in enumerate(fields)}
        for raw in table.get("data") or []:
            if len(raw) < len(fields):
                continue
            r = {k: raw[i] for k, i in positions.items()}
            diff = num(r.get("漲跌價差"))
            if diff is None:
                continue
            sign_field = html.unescape(re.sub(r"<[^>]+>", "", str(r.get("漲跌(+/-)") or ""))).strip()
            if sign_field == "-":
                diff = -abs(diff)
            elif sign_field == "+":
                diff = abs(diff)
            elif sign_field not in ("", " ", "X"):
                continue
            candidates.append({
                "Date": f"{target.year - 1911:03d}{target.month:02d}{target.day:02d}",
                "Code": str(r["證券代號"]).strip(),
                "Name": str(r["證券名稱"]).strip(),
                "ClosingPrice": r["收盤價"],
                "Change": str(diff),
                "HighestPrice": r["最高價"],
                "LowestPrice": r["最低價"],
                "TradeValue": r["成交金額"],
                "TradeVolume": r["成交股數"],
            })
    if len(candidates) < 700:
        raise RuntimeError(f"TWSE_DATED_REPORT_INCOMPLETE: {len(candidates)}")
    return candidates


def fetch_market_dates(target):
    twse = fetch(URLS["TWSE"])
    dates = {roc_date(row.get("Date")) for row in twse if row.get("Date")}
    if dates != {target}:
        print(f"TWSE OpenAPI delayed: {dates}; using verified dated market report", flush=True)
        twse = twse_dated_rows(target)
    tpex = fetch(URLS["TPEx"])
    return {"TWSE": twse, "TPEx": tpex}


def build(payloads, universe, today):
    mapped = {}
    day_by_market = {}
    counts = {}
    for market, rows in payloads.items():
        seen_dates = {roc_date(row.get("Date")) for row in rows if row.get("Date")}
        if len(seen_dates) != 1:
            raise RuntimeError(f"{market}: mixed or missing quote dates {sorted(seen_dates)}")
        asof = seen_dates.pop()
        day_by_market[market] = asof.isoformat()
        # No previous-day data can masquerade as today's after-close signal.
        if asof != today:
            raise RuntimeError(f"{market}: STALE_EOD_MARKET_DATE {asof} != {today}")
        valid = 0
        for r in rows:
            obj = parse_row(r, market)
            if not obj or obj["symbol"] not in universe:
                continue
            valid += 1
            if obj["symbol"] == "2344":  # excluded by user's trading preference
                continue
            mapped[obj["symbol"]] = obj
        counts[market] = valid
        if valid < (700 if market == "TWSE" else 400):
            raise RuntimeError(f"{market}: insufficient eligible stocks {valid}")
    if len(mapped) < 1500:
        raise RuntimeError(f"Incomplete whole-market feed: {len(mapped)} stocks")

    liquid = [r for r in mapped.values() if r["value"] >= 100_000_000]
    strong = [r for r in liquid if r["change_pct"] >= 4 and
              r["close_strength"] is not None and r["close_strength"] >= .65]
    strong.sort(key=lambda r: (r["change_pct"], r["value"]), reverse=True)
    actionable_watch = [r for r in strong if r["change_pct"] < 9.0]
    # A separate earlier-stage radar intentionally does not require a 4% daily rally.
    # These are watch-only names: without multi-day structure they are NOT proven bases.
    early_stage = [
        r for r in liquid
        if 1.5 <= r["change_pct"] < 4.0
        and r["close_strength"] is not None
        and r["close_strength"] >= 0.8
        and r["value"] >= 200_000_000
    ]
    early_stage.sort(
        key=lambda r: (r["close_strength"], r["value"]), reverse=True
    )
    # Distinguish a close above the day's low from a verified multi-day reversal.
    reversal_watch = [
        r for r in liquid
        if -5.0 <= r["change_pct"] < -1.0
        and r["close_strength"] is not None
        and r["close_strength"] >= 0.75
        and r["value"] >= 200_000_000
    ]
    reversal_watch.sort(
        key=lambda r: (r["close_strength"], r["value"]), reverse=True
    )
    # Strong closes are research watchlist entries, not confirmed next-day entry prices.
    return {
        "scan_date": today.isoformat(),
        "generated_at": datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),
        "source": "TWSE_TPEX_OFFICIAL_EOD",
        "data_status": "OFFICIAL_EOD_WATCH_ONLY",
        "intraday": False,
        "not_trade_signal": True,
        "market_dates": day_by_market,
        "market_counts": counts,
        "total_stocks": len(mapped),
        "liquid_count": len(liquid),
        "strong_close_count": len(strong),
        "top_strong_close": strong[:30],
        "top_next_day_watch": actionable_watch[:30],
        "early_stage_count": len(early_stage),
        "top_early_stage": early_stage[:30],
        "reversal_watch_count": len(reversal_watch),
        "top_reversal_watch": reversal_watch[:20],
        "all_scanned": list(mapped.values()),
        "notice": "Daily official closing prices only. Reconfirm next-session quote, VWAP and breakout before entry.",
    }


def expected_market_date(now):
    target = now.date() if now.hour >= 14 else now.date() - timedelta(days=1)
    while target.weekday() >= 5:
        target -= timedelta(days=1)
    return target


def main():
    now = datetime.now(ZoneInfo("Asia/Taipei"))
    if now.weekday() >= 5:
        raise RuntimeError("Not a trading weekday")
    universe = json.loads(UNIVERSE.read_text(encoding="utf-8"))
    listed = {x["symbol"] for x in universe["stocks"] if len(x["symbol"]) == 4}
    try:
        target = expected_market_date(now)
        payload = build(fetch_market_dates(target), listed, target)
    except Exception as exc:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps({
            "scan_date": expected_market_date(now).isoformat(), "generated_at": now.isoformat(),
            "source": "TWSE_TPEX_OFFICIAL_EOD",
            "data_status": "ERROR_OFFICIAL_EOD_NOT_AVAILABLE",
            "error": str(exc)[:300], "top_next_day_watch": [], "top_strong_close": [],
            "top_early_stage": [], "top_reversal_watch": [],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        raise
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in payload.items() if k not in ("all_scanned", "top_strong_close", "top_next_day_watch", "top_early_stage", "top_reversal_watch")}, ensure_ascii=False, indent=2))
    print("NEXT-DAY WATCH:", [(r["symbol"], r["name"], r["change_pct"]) for r in payload["top_next_day_watch"][:15]])


if __name__ == "__main__":
    main()
