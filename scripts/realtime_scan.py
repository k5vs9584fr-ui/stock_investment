import csv
import io
import json
import os
import time
import urllib.request
import urllib.error
from datetime import datetime
from zoneinfo import ZoneInfo


API_KEY = os.environ["FUGLE_API_KEY"].strip()

TWSE_LIST_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
TPEX_CSV_URL = "https://mopsfin.twse.com.tw/opendata/t187ap03_O.csv"
FUGLE_BASE = "https://api.fugle.tw/marketdata/v1.0/stock"

BATCH_SIZE = 50
RESULT_FILE = "data/market_scan_results.json"
UNIVERSE_FILE = "data/stock_universe.json"
HTTP_RETRIES = 4


def get_bytes(url, headers=None, retries=HTTP_RETRIES):
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(
                url,
                headers=headers or {"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read()
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
            last_error = e
            if attempt >= retries:
                break
            wait = attempt * 2
            print(f"HTTP retry {attempt}/{retries}: {e}; sleep {wait}s")
            time.sleep(wait)
    raise RuntimeError(f"HTTP failed after {retries} attempts: {url} | {last_error}")


def get_json(url, headers=None):
    raw = get_bytes(url, headers=headers)
    return json.loads(raw.decode("utf-8"))


def safe_num(value):
    try:
        return float(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0


def today_taipei():
    return datetime.now(
        ZoneInfo("Asia/Taipei")
    ).strftime("%Y-%m-%d")


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
    reader = csv.DictReader(io.StringIO(text))

    stocks = []
    seen = set()

    for row in reader:
        symbol = str(row.get("公司代號", "")).strip()
        name = str(row.get("公司簡稱", "")).strip()

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

    print(f"TPEx 上櫃股票數：{len(stocks)}")
    return stocks


def build_stock_universe(force_refresh=False):
    if os.path.exists(UNIVERSE_FILE) and not force_refresh:
        try:
            with open(UNIVERSE_FILE, "r", encoding="utf-8") as f:
                cached = json.load(f)
            stocks = cached.get("stocks") or []
            if len(stocks) >= 1500:
                print(f"使用快取股票清單：{len(stocks)} 檔")
                return stocks
        except Exception as e:
            print(f"股票清單快取讀取失敗，重新抓取：{e}")

    twse = get_twse_symbols()
    tpex = get_tpex_symbols()

    unique = {}
    for item in twse + tpex:
        if item["symbol"] not in unique:
            unique[item["symbol"]] = item

    stocks = sorted(unique.values(), key=lambda x: x["symbol"])

    os.makedirs(os.path.dirname(UNIVERSE_FILE), exist_ok=True)
    with open(UNIVERSE_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {"generated_at": today_taipei(), "stocks": stocks},
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(f"股票清單建立完成：{len(stocks)} 檔")
    return stocks


def get_quote(symbol):
    url = f"{FUGLE_BASE}/intraday/quote/{symbol}"

    return get_json(
        url,
        headers={
            "X-API-KEY": API_KEY,
            "User-Agent": "Mozilla/5.0",
        },
    )


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

    change_pct = (price - reference) / reference * 100

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
        close_strength = (price - low) / (high - low)

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

    latent_score, latent_flags, range_pct = calc_latent_score(
        change_pct, close_strength, value, high, low, reference
    )

    return {
        "price": price,
        "reference": reference,
        "high": high,
        "low": low,
        "volume": volume,
        "value": value,
        "change_pct": change_pct,
        "close_strength": close_strength,
        "range_pct": range_pct,
        "score": round(score, 1),
        "latent_score": latent_score,
        "latent_flags": latent_flags,
        "phase": classify_phase(latent_score, change_pct),
    }


def calc_latent_score(change_pct, close_strength, value, high, low, reference):
    score = 0
    flags = []

    if -0.8 <= change_pct <= 1.8:
        score += 30
        flags.append("NOT_EXTENDED")
    elif 1.8 < change_pct <= 3.5:
        score += 16
        flags.append("EARLY_MOVE")
    elif change_pct > 5:
        score -= 18
        flags.append("TOO_EXTENDED")

    if close_strength >= 0.88:
        score += 25
        flags.append("CLOSE_NEAR_HIGH")
    elif close_strength >= 0.72:
        score += 18
        flags.append("CLOSE_STRONG")
    elif close_strength >= 0.55:
        score += 10
    elif close_strength < 0.30:
        score -= 10
        flags.append("CLOSE_WEAK")

    range_pct = 0
    if reference > 0 and high > 0 and low > 0:
        range_pct = (high - low) / reference * 100
        if range_pct <= 2.0:
            score += 15
            flags.append("RANGE_TIGHT")
        elif range_pct <= 3.5:
            score += 9
        elif range_pct >= 7:
            score -= 8
            flags.append("RANGE_HOT")

    if value >= 500_000_000:
        score += 18
    elif value >= 200_000_000:
        score += 14
    elif value >= 100_000_000:
        score += 10
    elif value >= 50_000_000:
        score += 6
    elif value < 8_000_000:
        score -= 20
        flags.append("LOW_LIQUIDITY")

    if -0.5 <= change_pct <= 2.2 and close_strength >= 0.72 and range_pct <= 3.5:
        score += 12
        flags.append("COIL_PROXY")

    return round(max(0, score), 1), flags, round(range_pct, 2)


def classify_phase(latent_score, change_pct):
    if change_pct >= 5:
        return "S級：已發動/不追價"
    if latent_score >= 80:
        return "A+級：預備發動"
    if latent_score >= 65:
        return "A級：潛伏"
    if latent_score >= 50:
        return "B級：觀察"
    return "C級：暫不碰"


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

    return round(a, 2), round(b, 2), round(c, 2)


def load_saved_results():
    if not os.path.exists(RESULT_FILE):
        return {
            "scan_date": today_taipei(),
            "stocks": {},
            "completed_batches": [],
        }

    try:
        with open(RESULT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {
            "scan_date": today_taipei(),
            "stocks": {},
            "completed_batches": [],
        }

    if data.get("scan_date") != today_taipei():
        return {
            "scan_date": today_taipei(),
            "stocks": {},
            "completed_batches": [],
        }

    return data


def save_results(data):
    os.makedirs(os.path.dirname(RESULT_FILE), exist_ok=True)

    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2,
        )


def print_top20(title, rows):
    print("")
    print("=" * 45)
    print(title)
    print("=" * 45)

    for rank, r in enumerate(rows[:20], 1):
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


def main():
    stocks = build_stock_universe(
        force_refresh=os.environ.get("REFRESH_UNIVERSE") == "1"
    )

    total_stock_count = len(stocks)

    print(f"全市場股票總數：{total_stock_count}")

    total_batches = (
        total_stock_count + BATCH_SIZE - 1
    ) // BATCH_SIZE

    # ★ 新增：workflow 可直接指定批次
    forced_batch = os.environ.get("SCAN_BATCH")

    if forced_batch:
        batch_no = int(forced_batch)
    else:
        run_number = int(
            os.environ.get("GITHUB_RUN_NUMBER", "1")
        )
        batch_no = (
            (run_number - 1) % total_batches
        ) + 1

    # 如果 workflow 多跑到超過總批次，直接結束
    if batch_no > total_batches:
        print(
            f"批次 {batch_no} 超過總批次 "
            f"{total_batches}，跳過。"
        )
        return

    batch_index = batch_no - 1

    start = batch_index * BATCH_SIZE
    end = min(
        start + BATCH_SIZE,
        total_stock_count,
    )

    batch = stocks[start:end]

    print("")
    print(f"總批次：{total_batches}")
    print(f"本次批次：{batch_no}/{total_batches}")
    print(f"股票位置：{start + 1} ~ {end}")
    print(f"本批股票：{len(batch)} 檔")

    batch_results = []

    for i, stock in enumerate(batch, 1):
        symbol = stock["symbol"]

        try:
            quote = get_quote(symbol)
            scored = score_stock(quote)

            if scored is None:
                continue

            a, b, c = calc_abc(
                scored["price"],
                scored["high"],
                scored["low"],
            )

            result = {
                "symbol": symbol,
                "name": stock["name"],
                "market": stock["market"],
                "a": a,
                "b": b,
                "c": c,
                **scored,
            }

            batch_results.append(result)

            print(
                f"[{i:02d}/{len(batch)}] "
                f"{symbol} {stock['name']} OK"
            )

        except Exception as e:
            print(
                f"{symbol} ERROR: {e}"
            )

        # Fugle 免費方案限流保護
        time.sleep(1.05)

    batch_results.sort(
        key=lambda x: x["score"],
        reverse=True,
    )

    print_top20(
        f"第 {batch_no} 批 TOP 20",
        batch_results,
    )

    saved = load_saved_results()

    saved_stocks = saved.get("stocks") or {}
    completed_batches = (
        saved.get("completed_batches") or []
    )

    for result in batch_results:
        saved_stocks[result["symbol"]] = result

    if batch_no not in completed_batches:
        completed_batches.append(batch_no)

    completed_batches = sorted(completed_batches)

    saved = {
        "scan_date": today_taipei(),
        "total_market_stocks": total_stock_count,
        "total_batches": total_batches,
        "completed_batches": completed_batches,
        "stocks": saved_stocks,
    }

    save_results(saved)

    accumulated = list(saved_stocks.values())

    accumulated.sort(
        key=lambda x: x["score"],
        reverse=True,
    )

    print("")
    print(
        f"目前累積："
        f"{len(accumulated)} / "
        f"{total_stock_count} 檔"
    )

    print(
        f"完成批次："
        f"{len(completed_batches)} / "
        f"{total_batches}"
    )

    print_top20(
        "全市場暫定 TOP 20",
        accumulated,
    )

    if len(completed_batches) >= total_batches:
        print("")
        print("###################################")
        print("✅ 全市場掃描完成")
        print("###################################")

        print_top20(
            "🔥 全市場最終 TOP 20",
            accumulated,
        )


if __name__ == "__main__":
    main()
