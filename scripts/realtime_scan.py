import json
import os
import re
import time
import urllib.request

API_KEY = os.environ["FUGLE_API_KEY"].strip()

TWSE_LIST_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
TPEX_LIST_URL = "https://www.tpex.org.tw/zh-tw/mainboard/listed/company.html"
FUGLE_BASE = "https://api.fugle.tw/marketdata/v1.0/stock"

BATCH_SIZE = 50


def get_text(url, headers=None):
    req = urllib.request.Request(
        url,
        headers=headers or {
            "User-Agent": "Mozilla/5.0"
        }
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def get_json(url, headers=None):
    req = urllib.request.Request(
        url,
        headers=headers or {}
    )

    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp)


def get_twse_symbols():
    data = get_json(TWSE_LIST_URL)

    stocks = []

    for item in data:
        symbol = str(item.get("公司代號", "")).strip()
        name = str(item.get("公司簡稱", "")).strip()

        if len(symbol) == 4 and symbol.isdigit():
            stocks.append({
                "symbol": symbol,
                "name": name,
                "market": "TWSE"
            })

    print(f"TWSE 上市股票數：{len(stocks)}")

    return stocks


def get_tpex_symbols():
    html = get_text(TPEX_LIST_URL)

    stocks = []
    seen = set()

    # 抓常見的 4 碼股票代號 + 公司名稱
    pattern = re.compile(
        r'company-detail\.html\?code=(\d{4})[^>]*>([^<]+)<'
    )

    for symbol, name in pattern.findall(html):
        symbol = symbol.strip()
        name = name.strip()

        if symbol not in seen:
            seen.add(symbol)

            stocks.append({
                "symbol": symbol,
                "name": name,
                "market": "TPEx"
            })

    print(f"TPEx 上櫃股票數：{len(stocks)}")

    return stocks


def get_quote(symbol):
    url = f"{FUGLE_BASE}/intraday/quote/{symbol}"

    return get_json(
        url,
        headers={"X-API-KEY": API_KEY},
    )


def safe_num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0


def score_stock(data):
    price = safe_num(data.get("closePrice"))
    reference = safe_num(data.get("referencePrice"))
    high = safe_num(data.get("highPrice"))
    low = safe_num(data.get("lowPrice"))

    total = data.get("total") or {}

    volume = safe_num(total.get("tradeVolume"))
    value = safe_num(total.get("tradeValue"))

    if price <= 0 or reference <= 0:
        return None

    change_pct = (
        (price - reference)
        / reference
        * 100
    )

    score = 50

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

    close_strength = 0

    if high > low > 0:
        close_strength = (
            (price - low)
            / (high - low)
        )

        if close_strength >= 0.92:
            score += 16
        elif close_strength >= 0.80:
            score += 12
        elif close_strength >= 0.65:
            score += 7
        elif close_strength < 0.30:
            score -= 8

    if volume >= 50000:
        score += 12
    elif volume >= 20000:
        score += 9
    elif volume >= 10000:
        score += 7
    elif volume >= 5000:
        score += 4
    elif volume < 1000:
        score -= 4

    if value >= 500_000_000:
        score += 8
    elif value >= 200_000_000:
        score += 5
    elif value >= 100_000_000:
        score += 3

    if change_pct >= 9:
        score -= 5

    return {
        "price": price,
        "reference": reference,
        "high": high,
        "low": low,
        "volume": volume,
        "value": value,
        "change_pct": change_pct,
        "close_strength": close_strength,
        "score": round(score, 1),
    }


def classify(score):
    if score >= 88:
        return "S級：強勢發動"

    if score >= 80:
        return "A+級：高度準備發動"

    if score >= 72:
        return "A級：準備發動"

    if score >= 64:
        return "B級：觀察"

    return "C級：暫不碰"


def calc_abc(price, high, low):
    if price <= 0:
        return 0, 0, 0

    a = price * 0.985
    b = price * 1.015
    c = price * 0.97

    if low > 0:
        a = max(low, a)
        c = min(low, c)

    if high > 0:
        b = max(high, b)

    return (
        round(a, 2),
        round(b, 2),
        round(c, 2),
    )


def main():
    print("===================================")
    print("華安全市場上市 + 上櫃輪掃器")
    print("===================================")

    twse = get_twse_symbols()
    tpex = get_tpex_symbols()

    all_stocks = twse + tpex

    unique = {}

    for item in all_stocks:
        unique[item["symbol"]] = item

    stocks = sorted(
        unique.values(),
        key=lambda x: x["symbol"]
    )

    print(f"全市場股票總數：{len(stocks)}")

    if not stocks:
        raise RuntimeError("抓不到台股股票清單")

    run_number = int(
        os.environ.get(
            "GITHUB_RUN_NUMBER",
            "1"
        )
    )

    total_batches = (
        len(stocks)
        + BATCH_SIZE
        - 1
    ) // BATCH_SIZE

    batch_index = (
        run_number - 1
    ) % total_batches

    start = batch_index * BATCH_SIZE
    end = min(
        start + BATCH_SIZE,
        len(stocks)
    )

    batch = stocks[start:end]

    print(f"GitHub Run #{run_number}")
    print(f"總批次：{total_batches}")
    print(
        f"本次批次："
        f"{batch_index + 1}/"
        f"{total_batches}"
    )
    print(
        f"本次掃描股票位置："
        f"{start + 1} ~ {end}"
    )
    print(
        f"本次掃描："
        f"{len(batch)} 檔"
    )

    results = []

    for i, stock in enumerate(
        batch,
        start=1
    ):
        symbol = stock["symbol"]
        name = stock["name"]
        market = stock["market"]

        try:
            data = get_quote(symbol)

            scored = score_stock(data)

            if scored is None:
                print(
                    f"[{i:02d}/{len(batch)}] "
                    f"{symbol} {name} 無有效報價"
                )
                continue

            a, b, c = calc_abc(
                scored["price"],
                scored["high"],
                scored["low"],
            )

            results.append({
                "symbol": symbol,
                "name": name,
                "market": market,
                "a": a,
                "b": b,
                "c": c,
                **scored,
            })

            print(
                f"[{i:02d}/{len(batch)}] "
                f"{symbol} {name} {market} OK"
            )

        except Exception as e:
            print(
                f"[{i:02d}/{len(batch)}] "
                f"{symbol} ERROR: {e}"
            )

        time.sleep(1.05)

    results.sort(
        key=lambda x: x["score"],
        reverse=True,
    )

    print("")
    print("===================================")
    print("本批 TOP 20")
    print("===================================")

    for rank, r in enumerate(
        results[:20],
        start=1
    ):
        print(
            f"{rank:02d}. "
            f"{r['symbol']} {r['name']} "
            f"[{r['market']}] | "
            f"價格 {r['price']:.2f} | "
            f"漲跌 {r['change_pct']:+.2f}% | "
            f"成交量 {int(r['volume'])} | "
            f"分數 {r['score']} | "
            f"{classify(r['score'])}"
        )

        print(
            f"    A點 {r['a']:.2f} | "
            f"B點 {r['b']:.2f} | "
            f"C點 {r['c']:.2f}"
        )


if __name__ == "__main__":
    main()
