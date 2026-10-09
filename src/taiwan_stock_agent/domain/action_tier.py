from __future__ import annotations


def action_tier(rank: int, action_score: float) -> str:
    """Execution tier based on the same score used for ranking.

    Hybrid Action Score is the production ranking score. Keeping tier thresholds
    on that same scale avoids contradictory outcomes where a stock ranks Top3
    but is rejected by a different score family.
    """
    if rank <= 3 and action_score >= 72:
        return "PRIMARY_TOP3"
    if rank <= 5 and action_score >= 62:
        return "SECONDARY_TOP5"
    return "WATCH_ONLY"


def allocation_weight(rank: int, action_score: float) -> float:
    tier = action_tier(rank, action_score)
    if tier == "PRIMARY_TOP3":
        return {1: 0.40, 2: 0.33, 3: 0.27}.get(rank, 0.0)
    return 0.0
