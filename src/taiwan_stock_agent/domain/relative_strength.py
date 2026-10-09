from __future__ import annotations


def relative_strength_overlay(row: dict, market_context: dict | None = None) -> tuple[float, list[str]]:
    surge = row.get("surge_metrics") or {}
    flags: list[str] = []
    bonus = 0.0

    ret5 = float(surge.get("return5_pct") or 0.0)
    ret10 = float(surge.get("return10_pct") or 0.0)
    market5 = float((market_context or {}).get("market_return_5d") or 0.0)
    market10 = float((market_context or {}).get("market_return_10d") or 0.0)

    rs5 = ret5 - market5
    rs10 = ret10 - market10

    if rs5 >= 4.0 and rs10 >= 6.0:
        bonus += 6.0
        flags.append("RELATIVE_STRENGTH_LEADER")
    elif rs5 >= 2.0 and rs10 >= 3.0:
        bonus += 3.0
        flags.append("RELATIVE_STRENGTH_POSITIVE")
    elif rs5 <= -3.0 and rs10 <= -5.0:
        bonus -= 6.0
        flags.append("RELATIVE_STRENGTH_LAGGARD")

    return round(bonus, 1), flags
