import csv
import io
import json
import os
import time
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo


API_KEY = os.environ["FUGLE_API_KEY"].strip()

TWSE_LIST_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
TPEX_CSV_URL = "https://mopsfin.twse.com.tw/opendata/t187ap03_O.csv"

FUGLE_BASE = "https://api.fugle.tw/marketdata/v1.0/stock"

BATCH_SIZE = 50

RESULT_FILE = "data/market_scan_results.json"


# =========================================================
# 基本工具
# =========================================================

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

    return json.loads(
        raw.decode("utf-8")
    )


def safe_num(value):
    try:
        if value is None:
            return 0

        return float(value)

    except (TypeError, ValueError):
        return 0


def today_taipei():
    return datetime.now(
        ZoneInfo("Asia/Taipei")
    ).strftime("%Y-%m-%d")


# =========================================================
# TWSE 上市清單
# =========================================================

def get_twse_symbols():
    data = get_json(TWSE_LIST_URL)

    stocks = []

    for item in data:
        symbol = str(
            item.get("公司代號", "")
        ).strip()

        name = str(
            item.get("公司簡稱", "")
        ).strip()

        if (
            len(symbol) == 4
            and symbol.isdigit()
        ):
            stocks.append(
                {
                    "symbol": symbol,
                    "name": name,
                    "market": "TWSE",
                }
            )

    print(
        f"TWSE 上市股票數："
        f"{len(stocks)}"
    )

    return stocks


# =========================================================
# TPEx 上櫃清單
# =========================================================

def decode_csv_bytes(raw):
    encodings = [
        "utf-8-sig",
        "utf-8",
        "cp950",
        "big5",
    ]

    for encoding in encodings:
        try:
            return raw.decode(encoding)

        except UnicodeDecodeError:
            pass

    return raw.decode(
        "utf-8",
        errors="ignore",
    )


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

    stocks = []
    seen = set()

    for row in reader:
        symbol = str(
            row.get("公司代號", "")
        ).strip()

        name = str(
            row.get("公司簡稱", "")
        ).strip()

        if (
            len(symbol) == 4
            and symbol.isdigit()
            and symbol not in seen
        ):
            seen.add(symbol)

            stocks.append(
                {
                    "symbol": symbol,
                    "name": name,
                    "market": "TPEx",
                }
            )

    print(
        f"TPEx 上櫃股票數："
        f"{len(stocks)}"
    )

    return stocks


# =========================================================
# Fugle 行情
# =========================================================

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


# =========================================================
# 評分模型
# =========================================================

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

    if (
        price <= 0
        or reference <= 0
    ):
        return None

    change_pct = (
        (price - reference)
        / reference
        * 100
    )

    score = 50

    # -------------------------
    # 價格動能
    # -------------------------

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


    # -------------------------
    # 收盤 / 現價靠近高點
    # -------------------------

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


    # -------------------------
    # 成交量
    # -------------------------

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


    # -------------------------
    # 成交金額
    # -------------------------

    if value >= 500_000_000:
        score += 8

    elif value >= 200_000_000:
        score += 5

    elif value >= 100_000_000:
        score += 3


    # -------------------------
    # 過熱扣分
    # -------------------------

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


# =========================================================
# A / B / C 點
# =========================================================

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


# =========================================================
# 累積結果
# =========================================================

def load_saved_results():
    if not os.path.exists(RESULT_FILE):
        return {
            "scan_date": today_taipei(),
            "stocks": {},
            "completed_batches": [],
        }

    try:
        with open(
            RESULT_FILE,
            "r",
            encoding="utf-8",
        ) as f:
            data = json.load(f)

    except Exception:
        data = {
            "scan_date": today_taipei(),
            "stocks": {},
            "completed_batches": [],
        }

    # 換交易日就清空舊資料
    if (
        data.get("scan_date")
        != today_taipei()
    ):
        print(
            "偵測到新日期，"
            "重新開始全市場掃描。"
        )

        return {
            "scan_date": today_taipei(),
            "stocks": {},
            "completed_batches": [],
        }

    return data


def save_results(data):
    os.makedirs(
        os.path.dirname(RESULT_FILE),
        exist_ok=True,
    )

    with open(
        RESULT_FILE,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2,
        )


# =========================================================
# Top 20 顯示
# =========================================================

def print_top20(
    title,
    rows,
):
    print("")
    print("===================================")
    print(title)
    print("===================================")
    print("")

    for rank, r in enumerate(
        rows[:20],
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
            f"分數 {r['score']} | "
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


# =========================================================
# 主程式
# =========================================================

def main():
    print("")
    print("===================================")
    print("華安全市場累積輪掃器")
    print("TWSE + TPEx + Fugle")
    print("===================================")
    print("")

    # -------------------------
    # 股票清單
    # -------------------------

    twse = get_twse_symbols()
    tpex = get_tpex_symbols()

    all_stocks = (
        twse
        + tpex
    )

    unique = {}

    for item in all_stocks:
        symbol = item["symbol"]

        if symbol not in unique:
            unique[symbol] = item

    stocks = sorted(
        unique.values(),
        key=lambda x: x["symbol"],
    )

    total_stock_count = len(stocks)

    print("")
    print(
        f"全市場股票總數："
        f"{total_stock_count}"
    )

    if not stocks:
        raise RuntimeError(
            "完全抓不到股票清單"
        )


    # -------------------------
    # 批次
    # -------------------------

    run_number = int(
        os.environ.get(
            "GITHUB_RUN_NUMBER",
            "1",
        )
    )

    total_batches = (
        total_stock_count
        + BATCH_SIZE
        - 1
    ) // BATCH_SIZE

    batch_index = (
        run_number - 1
    ) % total_batches

    batch_no = (
        batch_index + 1
    )

    start = (
        batch_index
        * BATCH_SIZE
    )

    end = min(
        start + BATCH_SIZE,
        total_stock_count,
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
        f"{batch_no}/"
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


    # -------------------------
    # 掃本批
    # -------------------------

    batch_results = []

    for i, stock in enumerate(
        batch,
        start=1,
    ):
        symbol = stock["symbol"]
        name = stock["name"]
        market = stock["market"]

        try:
            quote = get_quote(symbol)

            scored = score_stock(
                quote
            )

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

            result = {
                "symbol": symbol,
                "name": name,
                "market": market,
                "a": a,
                "b": b,
                "c": c,
                **scored,
            }

            batch_results.append(
                result
            )

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


    # -------------------------
    # 本批排序
    # -------------------------

    batch_results.sort(
        key=lambda x: x["score"],
        reverse=True,
    )

    print_top20(
        "本批 TOP 20",
        batch_results,
    )


    # -------------------------
    # 載入舊累積結果
    # -------------------------

    saved = load_saved_results()

    saved_stocks = (
        saved.get("stocks")
        or {}
    )

    completed_batches = (
        saved.get(
            "completed_batches"
        )
        or []
    )


    # -------------------------
    # 把本批全部加入
    # -------------------------

    for result in batch_results:
        saved_stocks[
            result["symbol"]
        ] = result


    # 記錄完成批次
    if batch_no not in completed_batches:
        completed_batches.append(
            batch_no
        )

    completed_batches = sorted(
        completed_batches
    )


    saved = {
        "scan_date": today_taipei(),
        "total_market_stocks": (
            total_stock_count
        ),
        "total_batches": (
            total_batches
        ),
        "completed_batches": (
            completed_batches
        ),
        "stocks": saved_stocks,
    }

    save_results(saved)


    # -------------------------
    # 全市場暫定排名
    # -------------------------

    accumulated = list(
        saved_stocks.values()
    )

    accumulated.sort(
        key=lambda x: x["score"],
        reverse=True,
    )

    print("")
    print(
        f"目前已累積有效股票："
        f"{len(accumulated)} / "
        f"{total_stock_count}"
    )

    print(
        f"已完成批次："
        f"{len(completed_batches)} / "
        f"{total_batches}"
    )

    print(
        "完成批次編號：",
        completed_batches
    )


    print_top20(
        "全市場暫定 TOP 20",
        accumulated,
    )


    # -------------------------
    # 判斷是否整輪完成
    # -------------------------

    if (
        len(completed_batches)
        >= total_batches
    ):
        print("")
        print(
            "###################################"
        )
        print(
            "✅ 本輪全市場掃描完成"
        )
        print(
            "###################################"
        )

        print_top20(
            "全市場最終 TOP 20",
            accumulated,
        )

    else:
        remaining = (
            total_batches
            - len(completed_batches)
        )

        print("")
        print(
            f"尚剩 {remaining} 批"
            f"尚未完成。"
        )

        print(
            "繼續開新的 "
            "Run workflow 即可。"
        )


if __name__ == "__main__":
    main()
