from __future__ import annotations

from taiwan_stock_agent.domain.leadership_overlay import leadership_overlay
from taiwan_stock_agent.domain.explosive_lifecycle import classify_explosive_lifecycle


def top3_quality(row: dict) -> tuple[float, list[str]]:
    """Rank actionable Top3 candidates with an explosiveness-first bias.

    The user's preferred style is short-horizon explosive moves, so fresh/early
    ignition gets priority. Already-overextended names are still hard-demoted:
    the goal is "about to move / just started", not "already ran".
    """
    p = float(row.get("practical_score") or 0.0)
    flags = set(row.get("practical_flags") or [])
    surge_score = float(row.get("surge_score") or 0.0)
    surge_flags = set(row.get("surge_flags") or [])
    metrics = row.get("surge_metrics") or {}

    fresh_ignition = bool(metrics.get("fresh_ignition"))
    early_main_move = bool(metrics.get("early_main_move"))
    trend_accelerator = bool(metrics.get("trend_accelerator"))
    overextended = bool(metrics.get("overextended"))
    volume3_vs_20 = float(metrics.get("volume3_vs_20") or 0.0)
    ret3 = float(metrics.get("return3_pct") or 0.0)
    ret5 = float(metrics.get("return5_pct") or 0.0)

    score = p
    reasons: list[str] = []

    lifecycle = classify_explosive_lifecycle(row)
    score += float(lifecycle.get("score") or 0.0) * 0.35
    reasons.append(f"EXPLOSIVE_PHASE:{lifecycle.get('phase')}")

    # Explosiveness-first overlay. Reward early acceleration much more than
    # slow structural quality, but only while the move remains buyable.
    if not overextended and not str(row.get("surge_stage", "")).startswith("X"):
        if surge_score >= 75:
            score += 7.0
            reasons.append("EXPLOSIVE_SURGE_HIGH")
        elif surge_score >= 55:
            score += 4.0
            reasons.append("EXPLOSIVE_SURGE_RISING")

        if fresh_ignition:
            score += 8.0
            reasons.append("EXPLOSIVE_FRESH_IGNITION")
        if early_main_move:
            score += 7.0
            reasons.append("EXPLOSIVE_EARLY_MAIN_MOVE")
        if trend_accelerator:
            score += 4.0
            reasons.append("EXPLOSIVE_TREND_ACCELERATOR")
        if "VOLUME_EXPANSION" in surge_flags or volume3_vs_20 >= 1.5:
            score += 4.0
            reasons.append("EXPLOSIVE_VOLUME_CONFIRM")

        # Sweet spot: already moving, but not yet vertical.
        if 1.0 <= ret3 <= 4.5 and 2.0 <= ret5 <= 7.5:
            score += 4.0
            reasons.append("EXPLOSIVE_SWEET_SPOT")

    if "RELATIVE_STRENGTH_LEADER" in flags or "RELATIVE_STRENGTH_5D_LEADER" in flags:
        score += 4.0
        reasons.append("RS_LEADER")
    if "LIVERMORE_PIVOT_CONFIRM" in flags:
        score += 3.0
        reasons.append("PIVOT_CONFIRM")
    if "ONEIL_LEADER_BREAKOUT" in flags:
        score += 3.0
        reasons.append("LEADER_BREAKOUT")
    if "DARVAS_BOX_BREAKOUT" in flags:
        score += 2.0
        reasons.append("BOX_BREAKOUT")

    leader_bonus, leader_flags = leadership_overlay(row)
    score += leader_bonus
    reasons.extend(leader_flags)

    danger = {
        "OVEREXTENDED_PENALTY",
        "MODEL_ONLY_STAGNATION_PENALTY",
        "FAILED_BREAKOUT_WEAK_CLOSE",
        "DARVAS_FAILED_BREAKOUT",
        "BEARISH_VOLUME_PRICE_DIVERGENCE",
        "DISTRIBUTION_RISK",
        "FALSE_BREAKOUT_RISK_PENALTY",
        "LATE_REJECTION_PENALTY",
    }
    hits = danger.intersection(flags)
    if hits:
        score -= 12.0 + 3.0 * (len(hits) - 1)
        reasons.extend(sorted(hits))

    # Hard anti-chase guard: explosiveness can raise priority only before the
    # stock is extended. An X-stage/overextended name cannot remain Top3 merely
    # because surge_score is very high.
    if overextended or str(row.get("surge_stage", "")).startswith("X"):
        score -= 18.0
        score = min(score, 59.0)
        reasons.append("EXPLOSIVE_OVEREXTENDED_NO_CHASE")

    return round(max(0.0, min(100.0, score)), 1), reasons
