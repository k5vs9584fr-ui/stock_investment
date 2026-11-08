from __future__ import annotations


def position_decision(row: dict, held: bool = False, cost: float | None = None) -> dict:
    """Separate decisions for existing holdings and fresh entries."""
    action_score = float(row.get("hybrid_action_score") or 0.0)
    price = float(row.get("price") or 0.0)
    practical = float(row.get("practical_score") or 0.0)
    confidence = (row.get("score_confidence") or {}).get("level") or ""
    plan = row.get("entry_exit_plan") or {}

    if not held:
        if action_score >= 82 and confidence not in {"LOW", "CONFLICT"}:
            action = "NEW_BUY_CANDIDATE"
        elif action_score >= 72:
            action = "WAIT_CONFIRMATION"
        else:
            action = "NO_NEW_POSITION"
        return {
            "mode": "NEW_POSITION",
            "action": action,
            "score": round(action_score, 1),
        }

    pnl_pct = None
    if cost and cost > 0 and price > 0:
        pnl_pct = (price / float(cost) - 1.0) * 100.0

    if action_score >= 82 and practical >= 72:
        action = "HOLD_OR_ADD_ON_CONFIRMATION"
    elif action_score >= 68:
        action = "HOLD_NO_ADD"
    elif pnl_pct is not None and pnl_pct > 0:
        action = "REDUCE_INTO_STRENGTH"
    else:
        action = "EXIT_ON_FAILED_REBOUND"

    return {
        "mode": "EXISTING_POSITION",
        "action": action,
        "score": round(action_score, 1),
        "pnl_pct": round(pnl_pct, 2) if pnl_pct is not None else None,
        "reclaim_level": plan.get("entry_trigger"),
        "hard_stop": (plan.get("exit_rules") or {}).get("hard_stop")
            if isinstance(plan.get("exit_rules"), dict)
            else plan.get("hard_stop"),
    }
