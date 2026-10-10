from __future__ import annotations


def entry_exit_plan(row: dict, market_context: dict | None = None) -> dict:
    dt = row.get("dt_metrics") or {}
    practical = float(row.get("practical_score") or 0.0)
    price = float(row.get("price") or 0.0)
    breakout = float(dt.get("breakout_price") or 0.0)
    support = float(dt.get("recent_support") or 0.0)
    stop = float(dt.get("suggested_stop") or 0.0)
    vwap = float(dt.get("vwap") or 0.0)
    vol_accel = float(dt.get("volume_accel_5m") or 0.0)
    ret15 = float(dt.get("return_15m_pct") or 0.0)

    mode = "WAIT"
    trigger = None

    if practical >= 82 and breakout > 0 and vol_accel >= 1.25 and ret15 >= 0.20:
        mode = "BREAKOUT_CONFIRM"
        trigger = breakout
    elif practical >= 72 and support > 0:
        mode = "PULLBACK_BUY"
        trigger = support
    elif practical >= 72 and vwap > 0:
        mode = "VWAP_RECLAIM"
        trigger = vwap

    exit_rules = {
        "hard_stop": stop if stop > 0 else support,
        "failed_breakout": breakout if breakout > 0 else None,
        "take_profit_style": "SELL_INTO_STRENGTH_OR_BACKSTOP",
        "breakeven_after_progress": True,
        "add_only_above_cost": True,
    }

    return {
        "entry_mode": mode,
        "entry_trigger": round(trigger, 2) if trigger else None,
        "exit_rules": exit_rules,
    }
