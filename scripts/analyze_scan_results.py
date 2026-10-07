import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

SRC = Path("data/market_scan_results.json")
OUT = Path("data/scan_report.json")
WATCHLIST_OUT = Path("data/electronic_watchlist.json")
API_KEY = os.environ.get("FUGLE_API_KEY", "").strip()
FUGLE_BASE = "https://api.fugle.tw/marketdata/v1.0/stock"

ELECTRONIC_PREFIXES = {
    "23","24","30","31","32","33","34","35","36","37",
    "49","52","53","54","61","62","64","65","66","67",
    "68","69","80","81"
}

# 電信服務商雖然代號落在電子/通信區段，但不符合短線電子股雷達用途
ELECTRONIC_EXCLUDES = {"2412", "3045", "4904"}


def is_electronic(symbol):
    s = str(symbol or "")
    return (
        len(s) >= 2
        and s[:2] in ELECTRONIC_PREFIXES
        and s not in ELECTRONIC_EXCLUDES
    )


def avg(xs):
    return sum(xs) / len(xs) if xs else 0.0


def get_json(url):
    req = urllib.request.Request(
        url,
        headers={
            "X-API-KEY": API_KEY,
            "User-Agent": "Mozilla/5.0",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_history(symbol, scan_date):
    if not API_KEY:
        return []

    end = datetime.strptime(scan_date, "%Y-%m-%d").date()
    start = end - timedelta(days=95)
    params = urllib.parse.urlencode(
        {
            "from": start.isoformat(),
            "to": end.isoformat(),
            "timeframe": "D",
            "adjusted": "true",
            "fields": "open,high,low,close,volume",
            "sort": "asc",
        }
    )
    url = f"{FUGLE_BASE}/historical/candles/{symbol}?{params}"
    data = get_json(url)
    return data.get("data") or []


def structure_score(history):
    if len(history) < 25:
        return 0.0, [], {}

    bars = history[-30:]
    closes = [float(x.get("close") or 0) for x in bars]
    highs = [float(x.get("high") or 0) for x in bars]
    lows = [float(x.get("low") or 0) for x in bars]
    vols = [float(x.get("volume") or 0) for x in bars]

    if not closes or closes[-1] <= 0:
        return 0.0, [], {}

    flags = []
    pts = 0.0

    ma5 = avg(closes[-5:])
    ma10 = avg(closes[-10:])
    ma20 = avg(closes[-20:])
    close = closes[-1]

    spread = (max(ma5, ma10, ma20) - min(ma5, ma10, ma20)) / close * 100
    if spread <= 2.0:
        pts += 18
        flags.append("MA_CONVERGENCE_PRIME")
    elif spread <= 3.5:
        pts += 10
        flags.append("MA_CONVERGENCE")
    elif spread <= 5.0:
        pts += 4

    prev5_lows = lows[-10:-5]
    last5_lows = lows[-5:]
    higher_low = bool(prev5_lows and last5_lows and min(last5_lows) > min(prev5_lows))
    if higher_low:
        pts += 12
        flags.append("HIGHER_LOW")

    v5 = avg(vols[-5:])
    v20 = avg(vols[-20:])
    vol_ratio = v5 / v20 if v20 > 0 else 9.0
    if vol_ratio <= 0.75:
        pts += 15
        flags.append("VOL_DRYUP_PRIME")
    elif vol_ratio <= 0.90:
        pts += 8
        flags.append("VOL_DRYUP")

    high20 = max(highs[-20:])
    near_high = close / high20 if high20 > 0 else 0
    if 0.92 <= near_high < 0.995:
        pts += 12
        flags.append("NEAR_BREAKOUT")
    elif near_high >= 0.995:
        pts += 5
        flags.append("AT_BREAKOUT")

    low20 = min(lows[-20:])
    range20 = (high20 - low20) / close * 100 if close > 0 else 99
    if range20 <= 12:
        pts += 10
        flags.append("RANGE_COMPRESSION_PRIME")
    elif range20 <= 18:
        pts += 5
        flags.append("RANGE_COMPRESSION")

    base10 = closes[-11] if len(closes) >= 11 and closes[-11] > 0 else close
    ret10 = (close / base10 - 1) * 100 if base10 else 0
    if -3 <= ret10 <= 5:
        pts += 10
        flags.append("NOT_EXTENDED_10D")
    elif 5 < ret10 <= 10:
        pts += 3
    elif ret10 > 10:
        pts -= 8
        flags.append("EXTENDED_10D")

    if len(closes) >= 25:
        ma20_prev = avg(closes[-25:-5])
        if ma20 > ma20_prev:
            pts += 5
            flags.append("MA20_RISING")

    up_vols = []
    down_vols = []
    for i in range(1, len(bars[-20:])):
        cur = bars[-20:][i]
        prev = bars[-20:][i - 1]
        v = float(cur.get("volume") or 0)
        if float(cur.get("close") or 0) >= float(prev.get("close") or 0):
            up_vols.append(v)
        else:
            down_vols.append(v)

    asym = avg(up_vols) / avg(down_vols) if down_vols and avg(down_vols) > 0 else 1.0
    if asym >= 1.2:
        pts += 5
        flags.append("UPVOL_DOMINANT")

    metrics = {
        "ma_spread_pct": round(spread, 2),
        "vol5_vs_20": round(vol_ratio, 2),
        "near_20d_high": round(near_high, 3),
        "range20_pct": round(range20, 2),
        "return10_pct": round(ret10, 2),
        "up_down_vol_ratio": round(asym, 2),
        "higher_low": higher_low,
    }
    return round(max(0.0, pts), 1), flags, metrics


def classify_refined(score):
    if score >= 78:
        return "A+級：預備發動"
    if score >= 68:
        return "A級：潛伏"
    if score >= 58:
        return "B級：觀察"
    return "C級：暫不碰"


def slim(r):
    keys = [
        "symbol","name","market","price","change_pct","score","latent_score",
        "phase","close_strength","range_pct","volume","value","a","b","c",
        "latent_flags","is_electronic","structure_score","structure_flags",
        "structure_metrics","refined_score","refined_phase"
    ]
    return {k: r.get(k) for k in keys}


with SRC.open("r", encoding="utf-8") as f:
    data = json.load(f)

stocks = list((data.get("stocks") or {}).values())

for r in stocks:
    r.setdefault("latent_score", 0)
    r.setdefault("score", 0)
    r.setdefault("phase", "")
    r.setdefault("change_pct", 0)
    r.setdefault("value", 0)
    r.setdefault("volume", 0)
    r.setdefault("close_strength", 0)
    r.setdefault("range_pct", 0)
    r["is_electronic"] = is_electronic(r.get("symbol"))

latent = sorted(stocks, key=lambda x: x.get("latent_score", 0), reverse=True)
strength = sorted(stocks, key=lambda x: x.get("score", 0), reverse=True)

# 只深挖前段候選：避免重跑全市場，速度控制在約 1~2 分鐘
candidates = [
    r for r in latent
    if r.get("latent_score", 0) >= 55
    and r.get("change_pct", 0) < 5
    and r.get("is_electronic")
][:60]

for idx, r in enumerate(candidates, 1):
    try:
        history = get_history(r.get("symbol"), data.get("scan_date"))
        s_score, s_flags, s_metrics = structure_score(history)
    except Exception as e:
        s_score, s_flags, s_metrics = 0.0, [f"HISTORY_ERROR:{type(e).__name__}"], {}

    price = float(r.get("price") or 0)
    sector_bonus = 12 if r.get("is_electronic") else -6

    if 0 < price <= 200:
        price_bonus = 8
    elif price <= 300:
        price_bonus = 4
    elif price > 500:
        price_bonus = -10
    else:
        price_bonus = 0

    value = float(r.get("value") or 0)
    volume = float(r.get("volume") or 0)

    if value >= 200_000_000:
        liquidity_bonus = 8
    elif value >= 100_000_000:
        liquidity_bonus = 5
    elif value >= 50_000_000:
        liquidity_bonus = 1
    elif value >= 20_000_000:
        liquidity_bonus = -8
    else:
        liquidity_bonus = -20

    if volume < 300:
        liquidity_bonus -= 8

    refined = (
        float(r.get("latent_score", 0)) * 0.35
        + s_score * 0.52
        + sector_bonus
        + price_bonus
        + liquidity_bonus
    )

    r["structure_score"] = s_score
    r["structure_flags"] = s_flags
    r["structure_metrics"] = s_metrics
    r["refined_score"] = round(max(0, min(100, refined)), 1)
    r["refined_phase"] = classify_refined(r["refined_score"])

    print(
        f"[{idx:03d}/{len(candidates)}] {r.get('symbol')} {r.get('name')} "
        f"latent={r.get('latent_score')} structure={s_score} "
        f"refined={r['refined_score']} {r['refined_phase']}"
    )
    time.sleep(1.05)

refined = sorted(
    candidates,
    key=lambda x: x.get("refined_score", 0),
    reverse=True,
)
refined_electronics = [
    x for x in refined
    if x.get("is_electronic")
]

watchlist_rows = [
    slim(x)
    for x in refined_electronics
    if x.get("refined_score", 0) >= 58
    and float(x.get("value") or 0) >= 50_000_000
][:60]

report = {
    "scan_date": data.get("scan_date"),
    "total_market_stocks": data.get("total_market_stocks"),
    "total_batches": data.get("total_batches"),
    "completed_batches": data.get("completed_batches"),
    "scanned_stocks": len(stocks),
    "phase_counts": {},
    "top_latent": [slim(x) for x in latent[:30]],
    "top_strength": [slim(x) for x in strength[:20]],
    "top_refined": [slim(x) for x in refined[:30]],
    "top_electronics_refined": [slim(x) for x in refined_electronics[:30]],
}

for r in stocks:
    phase = r.get("phase") or "UNKNOWN"
    report["phase_counts"][phase] = report["phase_counts"].get(phase, 0) + 1

OUT.parent.mkdir(parents=True, exist_ok=True)
with OUT.open("w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

with WATCHLIST_OUT.open("w", encoding="utf-8") as f:
    json.dump(
        {
            "scan_date": data.get("scan_date"),
            "count": len(watchlist_rows),
            "stocks": watchlist_rows,
        },
        f,
        ensure_ascii=False,
        indent=2,
    )

print(json.dumps(report, ensure_ascii=False, indent=2))
