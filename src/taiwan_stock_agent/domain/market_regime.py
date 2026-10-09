from __future__ import annotations


def market_regime_adjustment(context: dict | None) -> tuple[float, list[str]]:
    if not context:
        return 0.0, []

    state = str(context.get("market_state") or "mixed")
    breadth = float(context.get("market_breadth") or 50.0)
    flags: list[str] = []
    adj = 0.0

    if state == "broad_rally":
        adj += 6.0
        flags.append("REGIME_BROAD_RALLY")
        if breadth >= 80:
            adj += 2.0
            flags.append("REGIME_BREADTH_STRONG")
    elif state == "narrow_leadership":
        adj -= 3.0
        flags.append("REGIME_NARROW_LEADERSHIP")
    elif state == "broad_selloff":
        adj -= 12.0
        flags.append("REGIME_BROAD_SELLOFF")
        if breadth <= 20:
            adj -= 3.0
            flags.append("REGIME_BREADTH_WEAK")
    else:
        flags.append("REGIME_MIXED")

    return round(adj, 1), flags
