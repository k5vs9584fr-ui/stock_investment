import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

WATCHLIST = Path("data/electronic_watchlist.json")
OUT = Path("data/final_rankings.json")

TWSE_INST = "https://www.twse.com.tw/rwd/zh/fund/T86"
TWSE_MARGIN = "https://www.twse.com.tw/exchangeReport/MI_MARGN"
TPEX_INST = "https://www.tpex.org.tw/web/stock/3insti/daily_trade/3itrade_hedge_result.php"
TPEX_MARGIN = "https://www.tpex.org.tw/web/stock/margin_trading/margin_balance/margin_bal_result.php"


def num(v):
    if v is None:
        return 0.0
    s = str(v).replace(",", "").replace("%", "").strip()
    if s in {"", "--", "---", "N/A"}:
        return 0.0
    try:
        return float(s)
    except Exception:
        return 0.0


def fetch_json(url, params):
    q = urllib.parse.urlencode(params)
    req = urllib.request.Request(
        f"{url}?{q}",
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json,text/plain,*/*",
            "X-Requested-With": "XMLHttpRequest",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8-sig"))


def roc_date(d):
    return f"{d.year - 1911}/{d.month:02d}/{d.day:02d}"


def ymd(d):
    return d.strftime("%Y%m%d")


def parse_twse_inst(payload):
    out = {}
    rows = payload.get("data") or []
    for r in rows:
        if len(r) < 19:
            continue
        symbol = str(r[0]).strip()
        if len(symbol) != 4 or not symbol.isdigit():
            continue
        out[symbol] = {
            "foreign": num(r[4]) + num(r[7]),
            "trust": num(r[10]),
            "dealer": num(r[11]),
            "total": num(r[18]),
        }
    return out


def parse_tpex_inst(payload):
    out = {}
    rows = payload.get("aaData") or []
    for r in rows:
        if len(r) < 24:
            continue
        symbol = str(r[0]).strip()
        if len(symbol) != 4 or not symbol.isdigit():
            continue
        out[symbol] = {
            "foreign": num(r[10]),
            "trust": num(r[13]),
            "dealer": num(r[22]),
            "total": num(r[23]),
        }
    return out


def parse_twse_margin(payload):
    rows = []
    if payload.get("data"):
        rows = payload["data"]
    else:
        for t in payload.get("tables") or []:
            if t.get("data"):
                rows.extend(t.get("data") or [])

    out = {}
    for r in rows:
        if len(r) < 8:
            continue
        symbol = str(r[0]).strip()
        if len(symbol) != 4 or not symbol.isdigit():
            continue

        # 官方 open-data 欄位：
        # 代號, 名稱, 融資買進, 融資賣出, 現償, 前日餘額, 今日餘額, 限額, ...
        if len(r) >= 16:
            out[symbol] = {
                "margin_prev": num(r[5]),
                "margin_now": num(r[6]),
                "margin_buy": num(r[2]),
                "margin_sell": num(r[3]),
            }
    return out


def parse_tpex_margin(payload):
    out = {}
    rows = payload.get("aaData") or []
    for r in rows:
        if len(r) < 19:
            continue
        symbol = str(r[0]).strip()
        if len(symbol) != 4 or not symbol.isdigit():
            continue

        # TPEx aaData 對齊：
        # r[2]=前資餘額, r[3]=資買, r[4]=資賣, r[5]=現償, r[6]=資餘額
        out[symbol] = {
            "margin_prev": num(r[2]),
            "margin_now": num(r[6]),
            "margin_buy": num(r[3]),
            "margin_sell": num(r[4]),
        }
    return out


def fetch_day(d):
    result = {"TWSE": {}, "TPEx": {}, "margin_TWSE": {}, "margin_TPEx": {}}

    try:
        p = fetch_json(TWSE_INST, {
            "date": ymd(d),
            "selectType": "ALLBUT0999",
            "response": "json",
        })
        result["TWSE"] = parse_twse_inst(p)
    except Exception as e:
        print(f"TWSE inst {d}: {type(e).__name__}: {e}")

    time.sleep(0.8)

    try:
        p = fetch_json(TPEX_INST, {
            "l": "zh-tw",
            "o": "json",
            "se": "EW",
            "t": "D",
            "d": roc_date(d),
            "s": "0,asc",
        })
        result["TPEx"] = parse_tpex_inst(p)
    except Exception as e:
        print(f"TPEx inst {d}: {type(e).__name__}: {e}")

    time.sleep(0.8)

    try:
        p = fetch_json(TWSE_MARGIN, {
            "response": "json",
            "date": ymd(d),
            "selectType": "ALL",
        })
        result["margin_TWSE"] = parse_twse_margin(p)
    except Exception as e:
        print(f"TWSE margin {d}: {type(e).__name__}: {e}")

    time.sleep(0.8)

    try:
        p = fetch_json(TPEX_MARGIN, {
            "l": "zh-tw",
            "o": "json",
            "d": roc_date(d),
            "s": "0,asc",
        })
        result["margin_TPEx"] = parse_tpex_margin(p)
    except Exception as e:
        print(f"TPEx margin {d}: {type(e).__name__}: {e}")

    return result


def chip_score(inst_days, margin):
    score = 50.0
    flags = []

    foreign = [x.get("foreign", 0) for x in inst_days]
    trust = [x.get("trust", 0) for x in inst_days]
    dealer = [x.get("dealer", 0) for x in inst_days]
    total = [x.get("total", 0) for x in inst_days]

    def pos_days(xs):
        return sum(1 for x in xs if x > 0)

    fsum = sum(foreign)
    tsum = sum(trust)
    dsum = sum(dealer)
    allsum = sum(total)

    fp = pos_days(foreign)
    tp = pos_days(trust)
    ap = pos_days(total)

    if fp >= 4 and fsum > 0:
        score += 16
        flags.append("FOREIGN_CONTINUOUS_BUY")
    elif fp >= 3 and fsum > 0:
        score += 10
        flags.append("FOREIGN_BUY")
    elif fsum < 0 and fp <= 1:
        score -= 10
        flags.append("FOREIGN_SELL")

    if tp >= 3 and tsum > 0:
        score += 18
        flags.append("TRUST_CONTINUOUS_BUY")
    elif tp >= 1 and tsum > 0:
        score += 8
        flags.append("TRUST_BUY")
    elif tsum < 0 and tp == 0:
        score -= 8
        flags.append("TRUST_SELL")

    if dsum > 0:
        score += 5
        flags.append("DEALER_BUY")

    if ap >= 4 and allsum > 0:
        score += 10
        flags.append("INST_CONSENSUS")
    elif allsum < 0 and ap <= 1:
        score -= 8
        flags.append("INST_NET_SELL")

    margin_prev = float((margin or {}).get("margin_prev") or 0)
    margin_now = float((margin or {}).get("margin_now") or 0)
    margin_change_pct = 0.0

    if margin_prev > 0:
        margin_change_pct = (margin_now - margin_prev) / margin_prev * 100

        if margin_change_pct <= -2:
            score += 16
            flags.append("MARGIN_SHARP_DROP")
        elif margin_change_pct <= -0.5:
            score += 10
            flags.append("MARGIN_DROP")
        elif margin_change_pct <= 0:
            score += 4
            flags.append("MARGIN_FLAT_DOWN")
        elif margin_change_pct >= 3:
            score -= 18
            flags.append("MARGIN_CHASING")
        elif margin_change_pct >= 1:
            score -= 9
            flags.append("MARGIN_RISING")

    if allsum > 0 and margin_change_pct < 0:
        score += 8
        flags.append("INST_BUY_MARGIN_DOWN")

    score = max(0.0, min(100.0, score))

    metrics = {
        "days": len(inst_days),
        "foreign_5d": round(fsum, 0),
        "foreign_buy_days": fp,
        "trust_5d": round(tsum, 0),
        "trust_buy_days": tp,
        "dealer_5d": round(dsum, 0),
        "inst_total_5d": round(allsum, 0),
        "inst_buy_days": ap,
        "margin_prev": round(margin_prev, 0),
        "margin_now": round(margin_now, 0),
        "margin_change_pct": round(margin_change_pct, 2),
    }
    return round(score, 1), flags, metrics


def final_phase(score):
    if score >= 82:
        return "A+級：籌碼確認/預備發動"
    if score >= 72:
        return "A級：潛伏"
    if score >= 62:
        return "B級：觀察"
    return "C級：暫不碰"


def main():
    with WATCHLIST.open("r", encoding="utf-8") as f:
        watch = json.load(f)

    scan_date = datetime.strptime(watch["scan_date"], "%Y-%m-%d").date()
    stocks = watch.get("stocks") or []

    target_days = []
    all_daily = {}

    # 往回找最多 14 個曆日，收集最近 5 個「有法人資料」交易日
    d = scan_date
    for _ in range(14):
        daily = fetch_day(d)
        all_daily[d.isoformat()] = daily

        has_market_data = bool(daily["TWSE"] or daily["TPEx"])
        if has_market_data:
            target_days.append(d)

        if len(target_days) >= 5:
            break

        d -= timedelta(days=1)
        time.sleep(0.5)

    target_days = sorted(target_days)
    print("chip trading days:", [x.isoformat() for x in target_days])

    rows = []

    for stock in stocks:
        symbol = str(stock.get("symbol") or "")
        market = stock.get("market")
        inst_days = []

        for d in target_days:
            daily = all_daily[d.isoformat()]
            bucket = daily["TWSE"] if market == "TWSE" else daily["TPEx"]
            if symbol in bucket:
                inst_days.append(bucket[symbol])

        margin = {}
        # 從最新交易日往回找最近可用融資資料
        for d in reversed(target_days):
            daily = all_daily[d.isoformat()]
            bucket = daily["margin_TWSE"] if market == "TWSE" else daily["margin_TPEx"]
            if symbol in bucket:
                margin = bucket[symbol]
                break

        cscore, cflags, cmetrics = chip_score(inst_days, margin)
        refined = float(stock.get("refined_score") or 0)

        completeness = 1.0 if len(inst_days) >= 4 else (0.75 if len(inst_days) >= 2 else 0.5)
        adjusted_chip = 50 + (cscore - 50) * completeness
        final = refined * 0.68 + adjusted_chip * 0.32

        row = dict(stock)
        row["chip_score"] = round(cscore, 1)
        row["chip_flags"] = cflags
        row["chip_metrics"] = cmetrics
        row["chip_data_completeness"] = round(completeness, 2)
        row["final_score"] = round(max(0, min(100, final)), 1)
        row["final_phase"] = final_phase(row["final_score"])
        rows.append(row)

    rows.sort(key=lambda x: x.get("final_score", 0), reverse=True)

    aplus = [x for x in rows if x.get("final_phase", "").startswith("A+")]
    a = [x for x in rows if x.get("final_phase", "").startswith("A級")]
    b = [x for x in rows if x.get("final_phase", "").startswith("B級")]

    out = {
        "scan_date": watch.get("scan_date"),
        "chip_days": [x.isoformat() for x in target_days],
        "count": len(rows),
        "A_plus": aplus[:20],
        "A": a[:20],
        "B": b[:20],
        "all_ranked": rows[:60],
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print("\n=== FINAL TOP 20 ===")
    for i, r in enumerate(rows[:20], 1):
        print(
            f"{i:02d}. {r.get('symbol')} {r.get('name')} | "
            f"refined={r.get('refined_score')} chip={r.get('chip_score')} "
            f"final={r.get('final_score')} {r.get('final_phase')}"
        )


if __name__ == "__main__":
    main()
