from __future__ import annotations


def _fnum(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_order_sheet(
    *,
    execution_plan: dict,
    ranked_rows: list[dict],
    holdings: list[dict],
    portfolio_value: float | None = None,
    lot_size: int = 1000,
) -> dict:
    """Convert execution weights into executable Taiwan-stock order rows.

    If portfolio_value is unavailable, keep WEIGHT_ONLY mode instead of inventing
    share counts. BUY sizing uses trigger price first, then current price.
    """
    by_symbol = {
        str(r.get("symbol") or r.get("ticker") or ""): r
        for r in ranked_rows
    }
    holding_by_symbol = {
        str(h.get("symbol") or h.get("ticker") or ""): h
        for h in holdings
    }

    pv = _fnum(portfolio_value)
    if pv is not None and pv <= 0:
        pv = None

    rows: list[dict] = []
    for order in execution_plan.get("orders") or []:
        symbol = str(order.get("symbol") or "")
        side = str(order.get("side") or "")
        source = str(order.get("source") or "")
        weight = max(0.0, _fnum(order.get("weight")) or 0.0)
        ranked = by_symbol.get(symbol) or {}
        holding = holding_by_symbol.get(symbol) or {}

        trigger = _fnum(order.get("trigger"))
        if trigger is None:
            trigger = _fnum((ranked.get("entry_exit_plan") or {}).get("entry_trigger"))
        current_price = _fnum(ranked.get("price"))
        reference_price = trigger or current_price

        hard_stop = _fnum(order.get("hard_stop"))
        if hard_stop is None:
            exit_rules = (ranked.get("entry_exit_plan") or {}).get("exit_rules") or {}
            hard_stop = _fnum(exit_rules.get("hard_stop"))

        shares = order.get("shares")
        try:
            shares = int(shares) if shares is not None else None
        except (TypeError, ValueError):
            shares = None

        est_value = None
        sizing_mode = "WEIGHT_ONLY"
        if side == "BUY" and pv is not None and reference_price and reference_price > 0:
            est_value = pv * weight
            shares = int(est_value // reference_price)
            sizing_mode = "SHARE_CALCULATED"
        elif side == "SELL" and shares is None:
            held_shares = holding.get("shares")
            try:
                held_shares = int(held_shares) if held_shares is not None else None
            except (TypeError, ValueError):
                held_shares = None
            held_weight = _fnum(holding.get("weight"))
            if held_shares is not None and held_weight and held_weight > 0:
                fraction = min(1.0, weight / held_weight)
                shares = int(round(held_shares * fraction))
                sizing_mode = "SHARE_FROM_HOLDING"
            elif held_shares is not None and weight >= 0.999:
                shares = held_shares
                sizing_mode = "SHARE_FROM_HOLDING"

        board_lots = shares // lot_size if shares is not None else None
        odd_lot_shares = shares % lot_size if shares is not None else None

        rows.append({
            "symbol": symbol,
            "name": ranked.get("name") or holding.get("name") or symbol,
            "side": side,
            "source": source,
            "weight": round(weight, 4),
            "sizing_mode": sizing_mode,
            "shares": shares,
            "board_lots": board_lots,
            "odd_lot_shares": odd_lot_shares,
            "trigger_price": round(trigger, 2) if trigger is not None else None,
            "reference_price": round(reference_price, 2) if reference_price is not None else None,
            "hard_stop": round(hard_stop, 2) if hard_stop is not None else None,
            "estimated_value": round(est_value, 0) if est_value is not None else None,
            "reason": order.get("reason"),
        })

    return {
        "portfolio_value": round(pv, 0) if pv is not None else None,
        "lot_size": int(lot_size),
        "orders": rows,
        "ready_order_count": sum(1 for x in rows if x.get("shares") is not None),
        "weight_only_count": sum(1 for x in rows if x.get("shares") is None),
    }
