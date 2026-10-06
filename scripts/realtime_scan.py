import json
import os
import time
import urllib.parse
import urllib.request

API_KEY = os.environ["FUGLE_API_KEY"].strip()

BASE = "https://api.fugle.tw/marketdata/v1.0/stock"

# 免費版先保守控制在 50 檔左右，避免 60 次/分鐘限制
BATCH_SIZE = 50

# 掃描進度檔
STATE_FILE = "data/realtime_scan_state.json"


def api_get(path, params=None):
    url = BASE + path

    if params:
        url += "?" + urllib.parse.urlencode(params)

    req = urllib.request.Request(
        url,
        headers={"X-API-KEY": API_KEY},
    )

    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp)


def safe_num(value, default=0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"offset": 0}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)

    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def fetch_market_symbols(exchange):
    data = api_get(
        "/intraday/tickers",
        {
            "type": "EQUITY",
            "exchange": exchange,
            "market": "TSE" if exchange == "TWSE" else "OTC",
        },
    )

    items = data.get("data", [])

    results = []

    for item in items:
        symbol = str(item.get("symbol", "")).strip()
        name = item.get("name", "")

        # 台股一般股票代碼通常 4 碼
        if len(symbol) == 4 and symbol.isdigit():
            results.append(
                {
                    "symbol": symbol,
                    "name": name,
                    "exchange": exchange,
                }
            )

    return results


def fetch_quote(symbol):
    return api_get(f"/intraday/quote/{symbol}")


def score_stock(data):
    close_price = safe_num(data.get("closePrice"))
    reference_price = safe_num(data.get("referencePrice"))
    high_price = safe_num(data.get("highPrice"))
    low_price = safe_num(data.get("lowPrice"))

    total_info = data.get("total") or {}
    total_volume = safe_num(total_info.get("tradeVolume"))
    total_value = safe_num(total_info.get("tradeValue"))

    if close_price <= 0 or reference_price <= 0:
        return 0, {}

    change_pct = (close_price - reference_price) / reference_price * 100

    close_strength = 0
    range_pct = 0

    if high_price > low_price > 0:
        close_strength = (close_price - low_price) / (high_price - low_price)
        range_pct = (high_price - low_price) / low_price * 100

    score = 50

    # 漲跌幅
    if change_pct >= 7:
        score += 20
    elif change_pct >= 5:
        score += 18
    elif change_pct >= 3:
        score += 14
    elif change_pct >= 1.5:
        score += 10
    elif change_pct >= 0:
        score += 4
    elif change_pct >= -1:
        score -= 3
    else:
        score -= 10

    # 現價靠近高點
    if close_strength >= 0.92:
        score += 16
    elif close_strength >= 0.80:
        score += 12
    elif close_strength >= 0.65:
        score += 7
    elif close_strength < 0.30:
        score -= 8

    # 成交量
    if total_volume >= 50000:
        score += 12
    elif total_volume >= 20000:
        score += 9
    elif total_volume >= 10000:
        score += 7
    elif total_volume >= 5000:
        score += 4
    elif total_volume < 1000:
        score -= 4

    # 成交值，避免太冷門
    if total_value >= 500_000_000:
        score += 8
    elif total_value >= 200_000_000:
        score += 5
    elif total_value >= 100_000_000:
        score += 3

    # 波動
    if 1.0 <= range_pct <= 6.5:
        score += 5
    elif range_pct >= 10:
        score -= 5

    # 過熱扣分
    if change_pct >= 9:
        score -= 5

    details = {
        "change_pct": change_pct,
        "close_strength": close_strength,
        "range_pct": range_pct,
        "volume": total_volume,
        "value": total_value,
    }

    return round(score, 1), details


def classify(score):
    if score >= 88:
        return "S級：強勢發動"
    elif score >= 80:
        return "A+級：高度準備發動"
    elif score >= 72:
        return "A級：準備發動"
    elif score >= 64:
        return "B級：觀察"
    return "C級：暫不碰"


def calc_abc(price, high, low):
    if price <= 0:
        return 0, 0, 0

    a = max(low, price * 0.985) if low > 0 else price * 0.985
    b = max(high, price * 1.015) if high > 0 else price * 1.015
    c = min(low, price * 0.97) if low > 0 else price * 0.97

    return round(a, 2), round(b, 2), round(c, 2)


def main():
    print("取得上市股票清單...")
    twse = fetch_market_symbols("TWSE")

    print("取得上櫃股票清單...")
    tpex = fetch_market_symbols("TPEx")

    universe = twse + tpex

    # 去重
    unique = {}
    for item in universe:
        unique[item["symbol"]] = item

    universe = sorted(unique.values(), key=lambda x: x["symbol"])

    print(f"股票總數：{len(universe)}")

    state = load_state()
    offset = int(state.get("offset", 0))

    if offset >= len(universe):
        offset = 0

    batch = universe[offset : offset + BATCH_SIZE]

    print(
        f"\n本次掃描第 {offset + 1} ~ "
        f"{min(offset + BATCH_SIZE, len(universe))} 檔\n"
    )

    results = []

    for i, item in enumerate(batch, start=1):
        symbol = item["symbol"]

        try:
            data = fetch_quote(symbol)

            score, details = score_stock(data)

            price = safe_num(data.get("closePrice"))
            high = safe_num(data.get("highPrice"))
            low = safe_num(data.get("lowPrice"))

            name = data.get("name") or item["name"] or symbol

            a, b, c = calc_abc(price, high, low)

            results.append(
                {
                    "symbol": symbol,
                    "name": name,
                    "price": price,
                    "high": high,
                    "low": low,
                    "score": score,
                    "class": classify(score),
                    "a": a,
                    "b": b,
                    "c": c,
                    **details,
                }
            )

            print(
                f"[{i:02d}/{len(batch)}] "
                f"{symbol} {name} OK"
            )

        except Exception as e:
            print(f"[{i:02d}/{len(batch)}] {symbol} ERROR: {e}")

        # 稍微降速，降低 API 限流風險
        time.sleep(1.05)

    results.sort(key=lambda x: x["score"], reverse=True)

    print("\n=== 本批 REALTIME STOCK SCAN TOP 20 ===\n")

    for rank, r in enumerate(results[:20], start=1):
        print(
            f"{rank:02d}. "
            f"{r['symbol']} {r['name']} | "
            f"價格 {r['price']:.2f} | "
            f"漲跌 {r['change_pct']:+.2f}% | "
            f"成交量 {int(r['volume'])} | "
            f"分數 {r['score']} | "
            f"{r['class']}"
        )

        print(
            f"    A點 {r['a']:.2f} | "
            f"B點 {r['b']:.2f} | "
            f"C點 {r['c']:.2f}"
        )

    next_offset = offset + BATCH_SIZE

    if next_offset >= len(universe):
        next_offset = 0
        print("\n=== 本輪全市場掃描完成，下次重新從第一批開始 ===")
    else:
        print(f"\n下次將從第 {next_offset + 1} 檔繼續掃描")

    save_state({"offset": next_offset})


if __name__ == "__main__":
    main()
