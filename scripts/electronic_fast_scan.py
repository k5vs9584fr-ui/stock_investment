import json
import time
from pathlib import Path

from realtime_scan import get_quote, score_stock, calc_abc

WATCHLIST = Path("data/electronic_watchlist.json")
CHIP_RESULTS = Path("data/electronic_chip_results.json")
FINAL_SIGNAL = Path("data/final_signal_report.json")
OUT = Path("data/electronic_fast_results.json")


def main():
    if not WATCHLIST.exists():
        raise RuntimeError(
            "data/electronic_watchlist.json 不存在，請先完成盤後分析"
        )

    with WATCHLIST.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    watchlist = payload.get("stocks") or []

    chip_map = {}
    chip_source = FINAL_SIGNAL if FINAL_SIGNAL.exists() else CHIP_RESULTS
    if chip_source.exists():
        try:
            with chip_source.open("r", encoding="utf-8") as f:
                chip_payload = json.load(f)
            chip_map = {
                x.get("symbol"): x
                for x in (chip_payload.get("stocks") or [])
                if x.get("symbol")
            }
            print(f"chip source: {chip_source}")
        except Exception as e:
            print(f"chip results load error: {e}")

    results = []

    for i, stock in enumerate(watchlist, 1):
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

            chip = chip_map.get(symbol, {})
            base_final = chip.get("final_score")
            if base_final is None:
                base_final = stock.get("refined_score", 0)

            row = {
                "symbol": symbol,
                "name": stock.get("name", ""),
                "market": stock.get("market", ""),
                "refined_score": stock.get("refined_score", 0),
                "refined_phase": stock.get("refined_phase", ""),
                "structure_score": stock.get("structure_score", 0),
                "chip_score": stock.get("chip_score", 50),
                "final_score": stock.get("final_score", stock.get("refined_score", 0)),
                "final_phase": stock.get("final_phase", stock.get("refined_phase", "")),
                "chip_score": chip.get("chip_score"),
                "chip_flags": chip.get("chip_flags", []),
                "chip_available": chip.get("chip_available", False),
                "base_final_score": base_final,
                "base_final_phase": chip.get("final_phase", stock.get("refined_phase", "")),
                "a": a,
                "b": b,
                "c": c,
                **scored,
            }
            results.append(row)

            print(
                f"[{i:02d}/{len(watchlist)}] {symbol} "
                f"{stock.get('name','')} OK"
            )
        except Exception as e:
            print(f"{symbol} ERROR: {e}")

        time.sleep(1.05)

    for row in results:
        row["fast_score"] = round(
            row.get("latent_score", 0) * 0.40
            + float(row.get("base_final_score") or 0) * 0.60,
            1,
        )

    results.sort(
        key=lambda x: x.get("fast_score", 0),
        reverse=True,
    )

    out = {
        "source_scan_date": payload.get("scan_date"),
        "count": len(results),
        "stocks": results,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print("\n=== 電子股快速掃描 TOP 20 ===")
    for i, r in enumerate(results[:20], 1):
        print(
            f"{i:02d}. {r['symbol']} {r['name']} | "
            f"價 {r['price']:.2f} | "
            f"漲跌 {r['change_pct']:+.2f}% | "
            f"latent {r['latent_score']:.1f} | "
            f"final {r.get('final_score', r['refined_score']):.1f} | "
            f"refined {r['refined_score']:.1f} | "
            f"chip {r.get('chip_score')} | "
            f"fast {r.get('fast_score',0):.1f} | "
            f"A {r['a']:.2f} B {r['b']:.2f} C {r['c']:.2f}"
        )


if __name__ == "__main__":
    main()
