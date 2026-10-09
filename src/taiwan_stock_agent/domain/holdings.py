from __future__ import annotations

import json
from pathlib import Path

from taiwan_stock_agent.domain.position_decision import position_decision


def load_holdings(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = data.get("holdings") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        return []
    out = []
    for row in rows:
        symbol = str((row or {}).get("symbol") or "").strip()
        if not symbol:
            continue
        out.append({
            "symbol": symbol,
            "name": (row or {}).get("name") or "",
            "cost": (row or {}).get("cost"),
            "shares": (row or {}).get("shares"),
        })
    return out


def enrich_holdings(holdings: list[dict], ranked_rows: list[dict]) -> list[dict]:
    by_symbol = {str(r.get("symbol") or ""): r for r in ranked_rows}
    out: list[dict] = []

    for holding in holdings:
        symbol = str(holding.get("symbol") or "")
        current = by_symbol.get(symbol)
        if not current:
            out.append({
                **holding,
                "matched": False,
                "position_decision": {
                    "mode": "EXISTING_POSITION",
                    "action": "NO_CURRENT_SIGNAL",
                },
            })
            continue

        merged = dict(current)
        merged["held"] = True
        merged["cost"] = holding.get("cost")
        merged["shares"] = holding.get("shares")
        merged["matched"] = True
        merged["position_decision"] = position_decision(
            merged,
            held=True,
            cost=holding.get("cost"),
        )
        out.append(merged)

    return out
