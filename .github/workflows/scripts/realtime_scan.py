import json
import os
import urllib.request

API_KEY = os.environ["FUGLE_API_KEY"].strip()

# 第一版先掃我們常看的台股，確認整套流程穩定
SYMBOLS = [
    "2313",  # 華通
    "3044",  # 健鼎
    "6191",  # 精成科
    "6239",  # 力成
    "8150",  # 南茂
    "5347",  # 世界
    "5425",  # 台半
    "2344",  # 華邦電
    "2421",  # 建準
    "6285",  # 啟碁
    "2492",  # 華新科
    "6213",  # 聯茂
    "8086",  # 宏捷科
    "2368",  # 金像電
    "6274",  # 台燿
]

BASE_URL = "https://api.fugle.tw/marketdata/v1.0/stock/intraday/quote/"


def fetch_quote(symbol):
    req = urllib.request.Request(
        BASE_URL + symbol,
        headers={"X-API-KEY": API_KEY},
    )

    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp)


def safe_num(value, default=0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def score_stock(data):
    close_price = safe_num(data.get("closePrice"))
    reference_price = safe_num(data.get("referencePrice"))
    high_price = safe_num(data.get("highPrice"))
    low_price = safe_num(data.get("lowPrice"))
    total_volume = safe_num(data.get("total", {}).get("tradeVolume"))

    if close_price <= 0 or reference_price <= 0:
        return 0, {}

    change_pct = (close_price - reference_price) / reference_price * 100

    range_pct = 0
    close_strength = 0

    if low_price > 0 and high_price > low_price:
        range_pct = (high_price - low_price) / low_price * 100
        close_strength = (close_price - low_price) / (high_price - low_price)

    score = 50

    # 價格強度
    if change_pct >= 5:
        score += 18
    elif change_pct >= 3:
        score += 14
    elif change_pct >= 1.5:
        score += 10
    elif change_pct >= 0:
        score += 5
    else:
        score -= 8

    # 收盤/現價靠近當日高點
    if close_strength >= 0.9:
        score += 15
    elif close_strength >= 0.75:
        score += 10
    elif close_strength >= 0.6:
        score += 5
    elif close_strength < 0.3:
        score -= 8

    # 有波動但避免過度失控
    if 1 <= range_pct <= 6:
        score += 5
    elif range_pct > 9:
        score -= 5

    # 基本成交量檢查
    if total_volume >= 10000:
        score += 8
    elif total_volume >= 5000:
        score += 5
    elif total_volume >= 1000:
        score += 2

    details = {
        "change_pct": change_pct,
        "close_strength": close_strength,
        "range_pct": range_pct,
        "volume": total_volume,
    }

    return round(score, 1), details


def classify(score):
    if score >= 85:
        return "S級：可能已發動"
    if score >= 75:
        return "A級：準備發動"
    if score >= 65:
        return "B級：觀察"
    return "C級：暫不碰"


def main():
    results = []

    for symbol in SYMBOLS:
        try:
            data = fetch_quote(symbol)
            score, details = score_stock(data)

            price = safe_num(data.get("closePrice"))
            high = safe_num(data.get("highPrice"))
            low = safe_num(data.get("lowPrice"))
            name = data.get("name") or symbol

            results.append({
                "symbol": symbol,
                "name": name,
                "price": price,
                "high": high,
                "low": low,
                "score": score,
                "class": classify(score),
                **details,
            })

        except Exception as e:
            print(f"{symbol} ERROR: {e}")

    results.sort(key=lambda x: x["score"], reverse=True)

    print("\n=== REALTIME STOCK SCAN TOP 20 ===\n")

    for i, r in enumerate(results[:20], start=1):
        print(
            f"{i:02d}. {r['symbol']} {r['name']} | "
            f"價格 {r['price']:.2f} | "
            f"漲跌 {r['change_pct']:+.2f}% | "
            f"分數 {r['score']} | "
            f"{r['class']}"
        )

        # 第一版 A/B/C 點，用當日高低與現價推估
        a_point = max(r["low"], r["price"] * 0.985)
        b_point = max(r["high"], r["price"] * 1.015)
        c_point = min(r["low"], r["price"] * 0.97)

        print(
            f"    A點 {a_point:.2f} | "
            f"B點 {b_point:.2f} | "
            f"C點 {c_point:.2f}"
        )


if __name__ == "__main__":
    main()
