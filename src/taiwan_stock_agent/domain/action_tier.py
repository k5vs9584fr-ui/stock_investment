from __future__ import annotations


def action_tier(rank: int, practical_score: float) -> str:
    if rank <= 3 and practical_score >= 72:
        return "PRIMARY_TOP3"
    if rank <= 5 and practical_score >= 62:
        return "SECONDARY_TOP5"
    return "WATCH_ONLY"


def allocation_weight(rank: int, practical_score: float) -> float:
    tier = action_tier(rank, practical_score)
    if tier == "PRIMARY_TOP3":
        return {1: 0.40, 2: 0.33, 3: 0.27}.get(rank, 0.0)
    if tier == "SECONDARY_TOP5":
        return 0.0
    return 0.0
