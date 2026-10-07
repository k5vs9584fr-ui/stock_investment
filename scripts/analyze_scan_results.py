import json
from pathlib import Path

SRC = Path("data/market_scan_results.json")
OUT = Path("data/scan_report.json")

with SRC.open("r", encoding="utf-8") as f:
    data = json.load(f)

stocks = list((data.get("stocks") or {}).values())

for r in stocks:
    r.setdefault("latent_score", 0)
    r.setdefault("score", 0)
    r.setdefault("phase", "")
    r.setdefault("change_pct", 0)
    r.setdefault("value", 0)
    r.setdefault("volume", 0)
    r.setdefault("close_strength", 0)
    r.setdefault("range_pct", 0)

latent = sorted(stocks, key=lambda x: x.get("latent_score", 0), reverse=True)
strength = sorted(stocks, key=lambda x: x.get("score", 0), reverse=True)

def slim(r):
    return {
        "symbol": r.get("symbol"),
        "name": r.get("name"),
        "market": r.get("market"),
        "price": r.get("price"),
        "change_pct": round(r.get("change_pct", 0), 2),
        "score": r.get("score"),
        "latent_score": r.get("latent_score"),
        "phase": r.get("phase"),
        "close_strength": round(r.get("close_strength", 0), 3),
        "range_pct": r.get("range_pct"),
        "volume": r.get("volume"),
        "value": r.get("value"),
        "a": r.get("a"),
        "b": r.get("b"),
        "c": r.get("c"),
        "latent_flags": r.get("latent_flags", []),
    }

report = {
    "scan_date": data.get("scan_date"),
    "total_market_stocks": data.get("total_market_stocks"),
    "total_batches": data.get("total_batches"),
    "completed_batches": data.get("completed_batches"),
    "scanned_stocks": len(stocks),
    "phase_counts": {},
    "top_latent": [slim(x) for x in latent[:40]],
    "top_strength": [slim(x) for x in strength[:20]],
}

for r in stocks:
    phase = r.get("phase") or "UNKNOWN"
    report["phase_counts"][phase] = report["phase_counts"].get(phase, 0) + 1

OUT.parent.mkdir(parents=True, exist_ok=True)
with OUT.open("w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

print(json.dumps(report, ensure_ascii=False, indent=2))
