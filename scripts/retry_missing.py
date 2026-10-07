import json
import time
from pathlib import Path

from realtime_scan import get_quote, score_stock, calc_abc

UNIVERSE = Path("data/stock_universe.json")
RESULTS = Path("data/market_scan_results.json")


def main():
    with UNIVERSE.open("r", encoding="utf-8") as f:
        universe = json.load(f).get("stocks") or []

    with RESULTS.open("r", encoding="utf-8") as f:
        data = json.load(f)

    stocks = data.get("stocks") or {}
    missing = [x for x in universe if x.get("symbol") not in stocks]

    print(f"缺少股票：{len(missing)} 檔")

    unresolved = []

    for i, stock in enumerate(missing, 1):
        symbol = stock["symbol"]
        ok = False

        for attempt in range(1, 4):
            try:
                quote = get_quote(symbol)
                scored = score_stock(quote)
                if scored is None:
                    raise RuntimeError("empty/invalid quote")

                a, b, c = calc_abc(
                    scored["price"],
                    scored["high"],
                    scored["low"],
                )

                stocks[symbol] = {
                    "symbol": symbol,
                    "name": stock.get("name", ""),
                    "market": stock.get("market", ""),
                    "a": a,
                    "b": b,
                    "c": c,
                    **scored,
                }
                ok = True
                print(
                    f"[{i:02d}/{len(missing)}] {symbol} "
                    f"補回成功 attempt={attempt}"
                )
                break
            except Exception as e:
                print(
                    f"[{i:02d}/{len(missing)}] {symbol} "
                    f"attempt={attempt} ERROR: {e}"
                )
                time.sleep(2 * attempt)

        if not ok:
            unresolved.append(symbol)

        time.sleep(1.05)

    data["stocks"] = stocks
    data["missing_symbols"] = unresolved
    data["scanned_stocks"] = len(stocks)

    with RESULTS.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"補回後：{len(stocks)} 檔")
    print(f"仍缺：{len(unresolved)} 檔 {unresolved}")


if __name__ == "__main__":
    main()
