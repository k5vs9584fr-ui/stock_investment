from __future__ import annotations


def build_execution_plan(
    *,
    top_candidates: list[dict],
    capital_plan: dict,
    holding_weights: dict[str, float],
    selected_rotations: list[dict],
    defensive_reduction_plan: dict,
) -> dict:
    """Merge fresh buys, rotations and defensive reductions into one order list."""
    orders: list[dict] = []

    # 1) Defensive sells
    sell_by_symbol: dict[str, dict] = {}
    for action in defensive_reduction_plan.get("actions") or []:
        symbol = str(action.get("symbol") or "")
        if not symbol:
            continue
        sell_by_symbol[symbol] = {
            "symbol": symbol,
            "side": "SELL",
            "source": "DEFENSIVE_REDUCTION",
            "weight": float(action.get("reduce_weight") or 0.0),
            "shares": action.get("reduce_shares"),
            "reason": action.get("reason"),
        }

    # 2) Rotation sells + buys. If same held symbol already has a defensive sell,
    # keep the larger sell weight to avoid duplicate orders.
    rotation_buy_symbols: set[str] = set()
    for rot in selected_rotations:
        plan = rot.get("position_plan") or {}
        held = str(rot.get("held_symbol") or "")
        challenger = str(rot.get("challenger_symbol") or "")
        sell_weight = float(plan.get("sell_weight") or 0.0)
        buy_weight = float(plan.get("buy_weight") or 0.0)

        if held and sell_weight > 0:
            prior = sell_by_symbol.get(held)
            if prior is None or sell_weight > float(prior.get("weight") or 0.0):
                sell_by_symbol[held] = {
                    "symbol": held,
                    "side": "SELL",
                    "source": "ROTATION",
                    "weight": sell_weight,
                    "shares": None,
                    "reason": rot.get("action"),
                }

        if challenger and buy_weight > 0:
            rotation_buy_symbols.add(challenger)
            orders.append({
                "symbol": challenger,
                "side": "BUY",
                "source": "ROTATION",
                "weight": buy_weight,
                "shares": None,
                "reason": rot.get("action"),
                "trigger": next(
                    (
                        x.get("entry_trigger")
                        for x in top_candidates
                        if str(x.get("symbol") or "") == challenger
                    ),
                    None,
                ),
            })

    orders.extend(sell_by_symbol.values())

    # 3) Fresh buys only for unused Top3 targets and only for remaining target gap.
    target_weights = {
        str(x.get("symbol") or ""): float(x.get("final_weight") or 0.0)
        for x in capital_plan.get("positions") or []
    }
    for candidate in top_candidates:
        symbol = str(candidate.get("symbol") or "")
        if not symbol or symbol in rotation_buy_symbols:
            continue
        target = float(target_weights.get(symbol, 0.0))
        existing = float((holding_weights or {}).get(symbol, 0.0))
        gap = max(0.0, target - existing)
        if gap <= 1e-9:
            continue
        orders.append({
            "symbol": symbol,
            "side": "BUY",
            "source": "FRESH_TOP3",
            "weight": round(gap, 4),
            "shares": None,
            "reason": candidate.get("explosive_label") or candidate.get("entry_mode"),
            "trigger": candidate.get("entry_trigger"),
        })

    priority = {
        ("SELL", "DEFENSIVE_REDUCTION"): 4,
        ("SELL", "ROTATION"): 3,
        ("BUY", "ROTATION"): 2,
        ("BUY", "FRESH_TOP3"): 1,
    }
    orders.sort(
        key=lambda x: (
            priority.get((str(x.get("side")), str(x.get("source"))), 0),
            float(x.get("weight") or 0.0),
        ),
        reverse=True,
    )

    return {
        "orders": orders,
        "sell_count": sum(1 for x in orders if x.get("side") == "SELL"),
        "buy_count": sum(1 for x in orders if x.get("side") == "BUY"),
        "total_sell_weight": round(sum(float(x.get("weight") or 0.0) for x in orders if x.get("side") == "SELL"), 4),
        "total_buy_weight": round(sum(float(x.get("weight") or 0.0) for x in orders if x.get("side") == "BUY"), 4),
    }
