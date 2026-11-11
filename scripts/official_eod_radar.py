"""Keyless official TWSE/TPEx after-close market radar. Not an intraday feed."""
import json
import re
import urllib.request
from datetime import date, datetime
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
        "all_scanned": list(mapped.values()),
        "notice": "Daily official closing prices only. Reconfirm next-session quote, VWAP and breakout before entry.",
    }


def main():
    now = datetime.now(ZoneInfo("Asia/Taipei"))
    if now.weekday() >= 5:
        raise RuntimeError("Not a trading weekday")
    universe = json.loads(UNIVERSE.read_text(encoding="utf-8"))
    listed = {x["symbol"] for x in universe["stocks"] if len(x["symbol"]) == 4}
    try:
        payload = build({market: fetch(url) for market, url in URLS.items()}, listed, now.date())
    except Exception as exc:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps({
            "scan_date": now.date().isoformat(), "generated_at": now.isoformat(),
            "source": "TWSE_TPEX_OFFICIAL_EOD",
            "data_status": "ERROR_OFFICIAL_EOD_NOT_AVAILABLE",
            "error": str(exc)[:300], "top_next_day_watch": [], "top_strong_close": [],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        raise
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in payload.items() if k not in ("all_scanned", "top_strong_close", "top_next_day_watch")}, ensure_ascii=False, indent=2))
    print("NEXT-DAY WATCH:", [(r["symbol"], r["name"], r["change_pct"]) for r in payload["top_next_day_watch"][:15]])


if __name__ == "__main__":
    main()
