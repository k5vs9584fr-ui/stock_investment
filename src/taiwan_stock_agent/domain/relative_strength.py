from __future__ import annotations


def relative_strength_overlay(row: dict, market_context: dict | None = None) -> tuple[float, list[str]]:
    surge = row.get("surge_metrics") or {}
    ctx = market_context or {}
    flags: list[str] = []
    bonus = 0.0

    ret5 = float(surge.get("return5_pct") or 0.0)
    ret10 = float(surge.get("return10_pct") or 0.0)
    market5_raw = ctx.get("market_return_5d")
    market10_raw = ctx.get("market_return_10d")

    if market5_raw is None and market10_raw is None:
        return 0.0, []

    rs5 = None if market5_raw is None else ret5 - float(market5_raw)
    rs10 = None if market10_raw is None else ret10 - float(market10_raw)

    if rs5 is not None and rs10 is not None:
        if rs5 >= 4.0 and rs10 >= 6.0:
            bonus += 6.0
            flags.append("RELATIVE_STRENGTH_LEADER")
        elif rs5 >= 2.0 and rs10 >= 3.0:
            bonus += 3.0
            flags.append("RELATIVE_STRENGTH_POSITIVE")
        elif rs5 <= -3.0 and rs10 <= -5.0:
            bonus -= 6.0
            flags.append("RELATIVE_STRENGTH_LAGGARD")
    elif rs5 is not None:
        if rs5 >= 4.0:
            bonus += 3.0
            flags.append("RELATIVE_STRENGTH_5D_LEADER")
        elif rs5 <= -3.0:
            bonus -= 3.0
            flags.append("RELATIVE_STRENGTH_5D_LAGGARD")

    return round(bonus, 1), flags
