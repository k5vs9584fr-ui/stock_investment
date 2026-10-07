import csv
import io
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
TWSE_LIST_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
TPEX_CSV_URL = "https://mopsfin.twse.com.tw/opendata/t187ap03_O.csv"
TWSE_T86_URL = "https://www.twse.com.tw/rwd/zh/fund/T86"
TPEX_T86_URL = "https://www.tpex.org.tw/web/stock/3insti/daily_trade/3itrade_hedge_result.php"
TWSE_MARGIN_URL = "https://openapi.twse.com.tw/v1/marginTrading/MI_MARGN"
TDCC_CACHE = Path("data/_tdcc_cache.json")

# TWSE official industry codes for electronic industries.
ELECTRONIC_INDUSTRY_CODES = {
    "24",  # 半導體
    "25",  # 電腦及週邊設備
    "26",  # 光電
    "27",  # 通信網路
    "28",  # 電子零組件
    "29",  # 電子通路
    "30",  # 資訊服務
    "31",  # 其他電子
}

# Telecom carriers are officially communication-network industry,
# but excluded from the short-term electronic setup radar.
ELECTRONIC_EXCLUDES = {"2412", "3045", "4904"}


def _decode_csv_bytes(raw):
    for enc in ("utf-8-sig", "utf-8", "cp950", "big5"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    return raw.decode("utf-8", errors="ignore")


def load_industry_map():
    industry = {}

    try:
        req = urllib.request.Request(
            TWSE_LIST_URL,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            rows = json.loads(resp.read().decode("utf-8"))
        for item in rows:
            symbol = str(item.get("公司代號", "")).strip()
            code = str(item.get("產業別", "")).strip().zfill(2)
            if symbol:
                industry[symbol] = code
    except Exception as e:
        print(f"TWSE industry map error: {e}")

    try:
        req = urllib.request.Request(
            TPEX_CSV_URL,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "text/csv,*/*",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
        reader = csv.DictReader(io.StringIO(_decode_csv_bytes(raw)))
        for row in reader:
            symbol = str(row.get("公司代號", "")).strip()
            code = str(row.get("產業別", "")).strip().zfill(2)
            if symbol:
                industry[symbol] = code
    except Exception as e:
        print(f"TPEx industry map error: {e}")

    return industry


def is_electronic(symbol, industry_map):
    s = str(symbol or "")
    code = str(industry_map.get(s, "")).strip().zfill(2)
    return (
        code in ELECTRONIC_INDUSTRY_CODES
        and s not in ELECTRONIC_EXCLUDES
    )



def _parse_int(value):
    if value is None:
        return None
    try:
        return int(str(value).replace(",", "").replace("+", "").strip())
    except (TypeError, ValueError):
        return None


def _request_json(url, params=None, timeout=20):
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json,text/plain,*/*",
            "Referer": "https://www.twse.com.tw/",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _field_idx(fields, exact=None, contains=()):
    if exact and exact in fields:
        return fields.index(exact)
    for i, field in enumerate(fields):
        text = str(field)
        if any(token in text for token in contains):
            return i
    return None


def fetch_twse_institution_day(day):
    try:
        body = _request_json(
            TWSE_T86_URL,
            {
                "date": day.strftime("%Y%m%d"),
                "selectType": "ALL",
                "response": "json",
            },
        )
        if body.get("stat") != "OK" or not body.get("data"):
            return {}

        fields = body.get("fields") or []
        code_i = _field_idx(fields, "證券代號", ("證券代號", "股票代號"))
        foreign_i = _field_idx(
            fields,
            "外陸資買賣超股數",
            ("外陸資買賣超股數", "外資及陸資買賣超股數"),
        )
        trust_i = _field_idx(fields, "投信買賣超股數", ("投信買賣超股數",))
        dealer_i = _field_idx(fields, "自營商買賣超股數", ("自營商買賣超股數",))

        if code_i is None or foreign_i is None:
            return {}

        out = {}
        for row in body["data"]:
            try:
                code = str(row[code_i]).strip()
                f = _parse_int(row[foreign_i])
                t = _parse_int(row[trust_i]) if trust_i is not None else None
                d = _parse_int(row[dealer_i]) if dealer_i is not None else None
                out[code] = (f or 0, t or 0, d or 0)
            except (IndexError, TypeError):
                continue
        return out
    except Exception as e:
        print(f"TWSE T86 {day} error: {e}")
        return {}


def fetch_tpex_institution_day(day):
    try:
        body = _request_json(
            TPEX_T86_URL,
            {
                "l": "zh-tw",
                "o": "json",
                "se": "EW",
                "t": "D",
                "d": day.strftime("%Y/%m/%d"),
            },
        )
        tables = body.get("tables") or []
        rows = (
            body.get("aaData")
            or body.get("data")
            or (tables[0].get("data") if tables else [])
            or []
        )
        if not rows:
            return {}

        is_v2 = any(len(r) == 24 for r in rows[:5] if r)
        trust_i = 13 if is_v2 else 10
        dealer_i = 22 if is_v2 else 16

        out = {}
        for row in rows:
            if len(row) < 17:
                continue
            code = str(row[0]).strip()
            f = _parse_int(row[4]) or 0
            t = _parse_int(row[trust_i]) if len(row) > trust_i else 0
            d = _parse_int(row[dealer_i]) if len(row) > dealer_i else 0
            out[code] = (f, t or 0, d or 0)
        return out
    except Exception as e:
        print(f"TPEx T86 {day} error: {e}")
        return {}


def fetch_margin_map():
    try:
        rows = _request_json(TWSE_MARGIN_URL)
        if not isinstance(rows, list):
            return {}

        def find_value(row, prefix, timing):
            for k, v in row.items():
                key = str(k)
                if prefix in key and timing in key and "餘額" in key:
                    return _parse_int(v)
            return None

        out = {}
        for row in rows:
            code = str(row.get("股票代號", "")).strip()
            if not code:
                continue
            today = find_value(row, "融資", "今日")
            prev = find_value(row, "融資", "前日")
            if today is None:
                today = find_value(row, "融資", "本日")
            out[code] = {
                "margin_today": today,
                "margin_prev": prev,
                "margin_change": (
                    today - prev
                    if today is not None and prev is not None
                    else None
                ),
            }
        return out
    except Exception as e:
        print(f"TWSE margin error: {e}")
        return {}


def load_tdcc_recent(scan_date):
    if not TDCC_CACHE.exists():
        return {}
    try:
        raw = json.loads(TDCC_CACHE.read_text(encoding="utf-8"))
    except Exception:
        return {}

    end = datetime.strptime(scan_date, "%Y-%m-%d").date()
    grouped = {}

    for key, vals in raw.items():
        try:
            symbol, week_key = key.split("|", 1)
            year_s, week_s = week_key.split("-", 1)
            week_date = datetime.fromisocalendar(
                int(year_s), int(week_s), 1
            ).date()
            if week_date > end:
                continue
            grouped.setdefault(symbol, []).append((week_date, vals))
        except Exception:
            continue

    out = {}
    for symbol, items in grouped.items():
        items.sort(key=lambda x: x[0], reverse=True)
        if len(items) < 2:
            continue

        latest_date, latest = items[0]
        prev_date, prev = items[1]
        age_days = (end - latest_date).days
        if age_days > 28:
            continue

        try:
            out[symbol] = {
                "large_holder_chg_pct": float(latest[0]) - float(prev[0]),
                "retail_holder_chg_pct": float(latest[1]) - float(prev[1]),
                "super_large_holder_chg_pct": float(latest[2]) - float(prev[2]),
                "tdcc_age_days": age_days,
            }
        except Exception:
            continue
    return out


def fetch_chip_context(scan_date):
    end = datetime.strptime(scan_date, "%Y-%m-%d").date()
    daily = []
    checked = 0

    while len(daily) < 5 and checked < 12:
        day = end - timedelta(days=checked)
        checked += 1
        if day.weekday() >= 5:
            continue

        twse = fetch_twse_institution_day(day)
        tpex = fetch_tpex_institution_day(day)
        merged = dict(twse)
        merged.update(tpex)

        if merged:
            daily.append((day, merged))

        time.sleep(0.25)

    return {
        "institution_days": daily,
        "margin": fetch_margin_map(),
        "tdcc": load_tdcc_recent(scan_date),
    }


def score_chip(symbol, chip_context):
    days = chip_context.get("institution_days") or []
    margin_map = chip_context.get("margin") or {}
    tdcc_map = chip_context.get("tdcc") or {}

    flows = []
    for day, market_map in days:
        if symbol in market_map:
            f, t, d = market_map[symbol]
            flows.append(
                {
                    "date": str(day),
                    "foreign": int(f or 0),
                    "trust": int(t or 0),
                    "dealer": int(d or 0),
                    "inst": int((f or 0) + (t or 0)),
                }
            )

    flags = []
    score = 0.0

    if flows:
        latest = flows[0]
        f = latest["foreign"]
        t = latest["trust"]
        inst = latest["inst"]

        if f > 0 and t > 0:
            score += 7
            flags.append("FOREIGN_TRUST_BOTH_BUY")
        elif inst > 0:
            score += 4
            flags.append("INST_BUY_TODAY")
        else:
            score -= 4
            flags.append("INST_SELL_TODAY")

        def consec(field):
            n = 0
            for row in flows:
                if row[field] > 0:
                    n += 1
                else:
                    break
            return n

        foreign_consec = consec("foreign")
        trust_consec = consec("trust")
        best_consec = max(foreign_consec, trust_consec)

        if best_consec >= 3:
            score += 7
            flags.append(f"INST_CONSEC_{best_consec}D")
        elif best_consec == 2:
            score += 4
            flags.append("INST_CONSEC_2D")

        last3 = flows[:3]
        buy_days_3 = sum(1 for x in last3 if x["inst"] > 0)
        if len(last3) >= 3 and buy_days_3 >= 2:
            score += 5
            flags.append("INST_BUY_2_OF_3")

        cumul5 = sum(x["inst"] for x in flows[:5])
        if cumul5 > 0:
            score += 5
            flags.append("INST_CUMUL_5D_POS")
        elif cumul5 < 0:
            score -= 3
            flags.append("INST_CUMUL_5D_NEG")
    else:
        latest = None
        foreign_consec = 0
        trust_consec = 0
        cumul5 = 0
        flags.append("INST_DATA_UNAVAILABLE")

    margin = margin_map.get(symbol) or {}
    margin_change = margin.get("margin_change")
    if margin_change is not None:
        if margin_change < 0:
            score += 4
            flags.append("MARGIN_DECLINING")
        elif margin_change > 0:
            score -= 2
            flags.append("MARGIN_INCREASING")

    tdcc = tdcc_map.get(symbol) or {}
    large_chg = tdcc.get("large_holder_chg_pct")
    retail_chg = tdcc.get("retail_holder_chg_pct")

    if large_chg is not None and retail_chg is not None:
        if large_chg > 0 and retail_chg < 0:
            score += 5
            flags.append("LARGE_UP_RETAIL_DOWN")
        else:
            if large_chg > 0:
                score += 2
                flags.append("LARGE_HOLDER_UP")
            if retail_chg < 0:
                score += 2
                flags.append("RETAIL_EXIT")
            if large_chg < 0 and retail_chg > 0:
                score -= 3
                flags.append("LARGE_DOWN_RETAIL_UP")

    available = bool(flows) or margin_change is not None or bool(tdcc)

    metrics = {
        "latest": latest,
        "foreign_consecutive_buy_days": foreign_consec,
        "trust_consecutive_buy_days": trust_consec,
        "inst_cumul_5d": cumul5,
        "margin_change": margin_change,
        "large_holder_chg_pct": large_chg,
        "retail_holder_chg_pct": retail_chg,
        "tdcc_age_days": tdcc.get("tdcc_age_days"),
        "available": available,
    }

    return round(max(0.0, min(30.0, score)), 1), flags, metrics


def classify_final(score):
    if score >= 82:
        return "A+級：預備發動"
    if score >= 72:
        return "A級：潛伏"
    if score >= 62:
        return "B級：觀察"
    return "C級：暫不碰"


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
        "latent_flags","industry_code","is_electronic","structure_score","structure_flags",
        "structure_metrics","refined_score","refined_phase",
        "chip_score","chip_flags","chip_metrics","final_score","final_phase"
    ]
    return {k: r.get(k) for k in keys}


with SRC.open("r", encoding="utf-8") as f:
    data = json.load(f)

stocks = list((data.get("stocks") or {}).values())
industry_map = load_industry_map()
chip_context = fetch_chip_context(data.get("scan_date"))

for r in stocks:
    r.setdefault("latent_score", 0)
    r.setdefault("score", 0)
    r.setdefault("phase", "")
    r.setdefault("change_pct", 0)
    r.setdefault("value", 0)
    r.setdefault("volume", 0)
    r.setdefault("close_strength", 0)
    r.setdefault("range_pct", 0)
    r["industry_code"] = industry_map.get(str(r.get("symbol")), "")
    r["is_electronic"] = is_electronic(r.get("symbol"), industry_map)

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

    chip_score, chip_flags, chip_metrics = score_chip(
        str(r.get("symbol")),
        chip_context,
    )
    r["chip_score"] = chip_score
    r["chip_flags"] = chip_flags
    r["chip_metrics"] = chip_metrics

    if chip_metrics.get("available"):
        final_score = (
            r["refined_score"] * 0.82
            + chip_score * 0.60
        )
    else:
        final_score = r["refined_score"] - 4

    r["final_score"] = round(max(0, min(100, final_score)), 1)
    r["final_phase"] = classify_final(r["final_score"])

    print(
        f"[{idx:03d}/{len(candidates)}] {r.get('symbol')} {r.get('name')} "
        f"latent={r.get('latent_score')} structure={s_score} "
        f"refined={r['refined_score']} chip={chip_score} "
        f"final={r['final_score']} {r['final_phase']}"
    )
    time.sleep(1.05)

refined = sorted(
    candidates,
    key=lambda x: x.get("refined_score", 0),
    reverse=True,
)

final_ranked = sorted(
    candidates,
    key=lambda x: x.get("final_score", 0),
    reverse=True,
)
refined_electronics = [
    x for x in refined
    if x.get("is_electronic")
]

watchlist_rows = [
    slim(x)
    for x in final_ranked
    if x.get("is_electronic")
    and x.get("final_score", 0) >= 58
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
    "top_final": [slim(x) for x in final_ranked[:30]],
    "top_electronics_final": [
        slim(x) for x in final_ranked
        if x.get("is_electronic")
    ][:30],
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
