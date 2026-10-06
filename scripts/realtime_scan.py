import csv
import io
import json
import os
import time
import urllib.request

API_KEY = os.environ["FUGLE_API_KEY"].strip()

TWSE_LIST_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
TPEX_CSV_URL = "https://mopsfin.twse.com.tw/opendata/t187ap03_O.csv"

FUGLE_BASE = "https://api.fugle.tw/marketdata/v1.0/stock"

BATCH_SIZE = 50


def get_bytes(url, headers=None):
    req = urllib.request.Request(
        url,
        headers=headers or {
            "User-Agent": "Mozilla/5.0"
        }
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def get_json(url, headers=None):
    raw = get_bytes(url, headers=headers)
    return json.loads(raw.decode("utf-8"))


def safe_num(value):
    try:
        if value is None:
            return 0
        return float(value)
    except (TypeError, ValueError):
        return 0


# =========================
# TWSE 上市股票
# =========================

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
                "market": "TWSE",
            })

    print(f"TWSE 上市股票數：{len(stocks)}")

    return stocks


# =========================
# TPEx 上櫃股票 CSV
# =========================

def decode_csv_bytes(raw):
    for encoding in ["utf-8-sig", "utf-8", "cp950", "big5"]:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            pass

    return raw.decode("utf-8", errors="ignore")


def get_tpex_symbols():
    raw = get_bytes(
        TPEX_CSV_URL,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/csv,*/*",
        },
    )

    text = decode_csv_bytes(raw)

    reader = csv.DictReader(
        io.StringIO(text)
    )

    print(
        "TPEx CSV 欄位：",
        reader.fieldnames
    )

    stocks = []
    seen = set()

    for row in reader:
        symbol = str(
            row.get("公司代號", "")
        ).strip()

        name = str(
            row.get("公司簡稱", "")
        ).strip()

        if not symbol:
            symbol = str(
                row.get("證券代號", "")
            ).strip()

        if not name:
            name = str(
                row.get("證券名稱", "")
            ).strip()

        if (
            len(symbol) == 4
            and symbol.isdigit()
            and symbol not in seen
        ):
            seen.add(symbol)

            stocks.append({
                "symbol": symbol,
                "name": name,
                "market": "TPEx",
            })

    print(
        f"TPEx 上櫃股票數："
        f"{len(stocks)}"
    )

    return stocks


# =========================
# Fugle 即時行情
# =========================

def get_quote(symbol):
    url = (
        f"{FUGLE_BASE}"
        f"/intraday/quote/{symbol}"
    )

    return get_json(
        url,
        headers={
            "X-API-KEY": API_KEY,
            "User-Agent": "Mozilla/5.0",
        },
    )


# =========================
# 評分
# =========================

def score_stock(data):
    price = safe_num(
        data.get("closePrice")
    )

    reference = safe_num(
        data.get("referencePrice")
    )

    high = safe_num(
        data.get("highPrice")
    )

    low = safe_num(
        data.get("lowPrice")
    )

    total = data.get("total") or {}

    volume = safe_num(
        total.get("tradeVolume")
    )

    value = safe_num(
        total.get("tradeValue")
    )

    if price <= 0 or reference <= 0:
        return None

    change_pct = (
        (price - reference)
        / reference
        * 100
    )

    score = 50

    # 價格動能
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

    # 收在高檔
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

    # 成交量
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

    # 成交金額
    if value >= 500_000_000:
        score += 8

    elif value >= 200_000_000:
        score += 5

    elif value >= 100_000_000:
        score += 3

    # 過熱扣分
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


# =========================
# A / B / C 點
# =========================

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


# =========================
# 主程式
# =========================

def main():
    print("")
    print("===================================")
    print("華安全市場 TWSE + TPEx 輪掃器")
    print("===================================")
    print("")

    twse = get_twse_symbols()
    tpex = get_tpex_symbols()

    all_stocks = twse + tpex

    unique = {}

    for item in all_stocks:
        symbol = item["symbol"]

        if symbol not in unique:
            unique[symbol] = item

    stocks = sorted(
        unique.values(),
        key=lambda x: x["symbol"],
    )

    print("")
    print(
        f"全市場股票總數："
        f"{len(stocks)}"
    )

    if not stocks:
        raise RuntimeError(
            "完全抓不到股票清單"
        )

    # GitHub Run 自動輪掃
    run_number = int(
        os.environ.get(
            "GITHUB_RUN_NUMBER",
            "1",
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

    start = (
        batch_index
        * BATCH_SIZE
    )

    end = min(
        start + BATCH_SIZE,
        len(stocks),
    )

    batch = stocks[start:end]

    print("")
    print(
        f"GitHub Run #{run_number}"
    )

    print(
        f"總批次：{total_batches}"
    )

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

    print("")

    results = []

    for i, stock in enumerate(
        batch,
        start=1,
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
                    f"{symbol} "
                    f"{name} "
                    f"[{market}] "
                    f"無有效報價"
                )

                time.sleep(1.05)
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
                f"{symbol} "
                f"{name} "
                f"[{market}] "
                f"OK"
            )

        except Exception as e:
            print(
                f"[{i:02d}/{len(batch)}] "
                f"{symbol} "
                f"[{market}] "
                f"ERROR: {e}"
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
    print("")

    for rank, r in enumerate(
        results[:20],
        start=1,
    ):
        print(
            f"{rank:02d}. "
            f"{r['symbol']} "
            f"{r['name']} "
            f"[{r['market']}] | "
            f"價格 {r['price']:.2f} | "
            f"漲跌 "
            f"{r['change_pct']:+.2f}% | "
            f"成交量 "
            f"{int(r['volume'])} | "
            f"分數 "
            f"{r['score']} | "
            f"{classify(r['score'])}"
        )

        print(
            f"    A點 "
            f"{r['a']:.2f} | "
            f"B點 "
            f"{r['b']:.2f} | "
            f"C點 "
            f"{r['c']:.2f}"
        )

    print("")
    print("===================================")
    print(
        f"本批有效股票："
        f"{len(results)}"
    )
    print("===================================")


if __name__ == "__main__":
    main()
