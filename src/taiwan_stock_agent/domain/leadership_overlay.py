from __future__ import annotations


def leadership_overlay(row: dict) -> tuple[float, list[str]]:
    """Reward stocks that are leaders rather than merely popular.

    Uses optional row-level context populated by market-wide / surge scans.
    Missing context is neutral.
    """
    bonus = 0.0
    flags: list[str] = []

    industry_rank = row.get("industry_rank_pct")
    if industry_rank is not None:
        r = float(industry_rank)
        if r >= 85:
            bonus += 4.0
            flags.append("INDUSTRY_LEADER")
        elif r >= 70:
            bonus += 2.0
            flags.append("INDUSTRY_STRONG")
        elif r <= 20:
            bonus -= 3.0
            flags.append("INDUSTRY_LAGGARD")

    hot_concepts = row.get("hot_concepts") or []
    if hot_concepts:
        bonus += min(3.0, float(len(hot_concepts)))
        flags.append("HOT_CONCEPT_LEADER")

    rel = row.get("relative_strength_pct")
    if rel is None:
        rel = (row.get("rs_metrics") or {}).get("relative_5d_pct")
    if rel is not None:
        rel = float(rel)
        if rel >= 5:
            bonus += 4.0
            flags.append("MARKET_RS_LEADER")
        elif rel >= 2:
            bonus += 2.0
            flags.append("MARKET_RS_STRONG")
        elif rel <= -3:
            bonus -= 3.0
            flags.append("MARKET_RS_LAGGARD")

    return round(bonus, 1), flags
