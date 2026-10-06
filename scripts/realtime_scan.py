import json
import os
import time
import urllib.request

API_KEY = os.environ["FUGLE_API_KEY"].strip()

TWSE_LIST_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
FUGLE_BASE = "https://api.fugle.tw/marketdata/v1.0/stock"

BATCH_SIZE = 50


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
                "name": name
            })

    print(f"上市股票數：{len(stocks)}")
    return stocks


def get_quote(symbol):
    url = f"{FUGLE_BASE}/intraday/quote/{symbol}"

    return get_json(
        url,
        headers={"X-API-KEY": API_KEY}
    )


def safe_num(v):
    try:
        return float(v)
    except:
        return 0


def main():
    stocks = get_twse_symbols()

    if not stocks:
        raise RuntimeError("抓不到上市股票清單")

    # 用 GitHub Actions 的執行次數自動決定掃描批次
run_number = int(os.environ.get("GITHUB_RUN_NUMBER", "1"))

total_batches = (len(stocks) + BATCH_SIZE - 1) // BATCH_SIZE

batch_index = (run_number - 1) % total_batches

start = batch_index * BATCH_SIZE
end = min(start + BATCH_SIZE, len(stocks))

batch = stocks[start:end]

print(f"GitHub Run #{run_number}")
print(f"總批次：{total_batches}")
print(f"本次批次：{batch_index + 1}/{total_batches}")
print(f"本次掃描股票位置：{start + 1} ~ {end}")
print(f"本次掃描：{len(batch)} 檔")

    results = []

    for i, stock in enumerate(batch, 1):
        try:
            data = get_quote(stock["symbol"])

            price = safe_num(data.get("closePrice"))
            ref = safe_num(data.get("referencePrice"))
            high = safe_num(data.get("highPrice"))
            low = safe_num(data.get("lowPrice"))

            if price <= 0 or ref <= 0:
                continue

            change_pct = (price - ref) / ref * 100

            score = 50

            if change_pct >= 5:
                score += 20
            elif change_pct >= 3:
                score += 15
            elif change_pct >= 1:
                score += 8
            elif change_pct < 0:
                score -= 8

            if high > low > 0:
                close_strength = (price - low) / (high - low)

                if close_strength >= 0.85:
                    score += 15
                elif close_strength >= 0.65:
                    score += 8

            a = round(price * 0.985, 2)
            b = round(max(high, price * 1.015), 2)
            c = round(price * 0.97, 2)

            results.append({
                "symbol": stock["symbol"],
                "name": stock["name"],
                "price": price,
                "change": change_pct,
                "score": score,
                "a": a,
                "b": b,
                "c": c,
            })

            print(
                f"[{i:02d}/{len(batch)}] "
                f"{stock['symbol']} {stock['name']} OK"
            )

        except Exception as e:
            print(
                f"[{i:02d}/{len(batch)}] "
                f"{stock['symbol']} ERROR: {e}"
            )

        time.sleep(1.05)

    results.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    print("\n=== TOP 20 ===")

    for rank, r in enumerate(results[:20], 1):
        print(
            f"{rank:02d}. "
            f"{r['symbol']} {r['name']} | "
            f"價格 {r['price']:.2f} | "
            f"漲跌 {r['change']:+.2f}% | "
            f"分數 {r['score']} | "
            f"A {r['a']} | B {r['b']} | C {r['c']}"
        )


if __name__ == "__main__":
    main()
