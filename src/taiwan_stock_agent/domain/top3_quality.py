from __future__ import annotations


def top3_quality(row: dict) -> tuple[float, list[str]]:
    p = float(row.get("practical_score") or 0.0)
    flags = set(row.get("practical_flags") or [])
    score = p
    reasons: list[str] = []

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

    danger = {
        "OVEREXTENDED_PENALTY",
        "MODEL_ONLY_STAGNATION_PENALTY",
        "FAILED_BREAKOUT_WEAK_CLOSE",
        "DARVAS_FAILED_BREAKOUT",
        "BEARISH_VOLUME_PRICE_DIVERGENCE",
        "DISTRIBUTION_RISK",
    }
    hits = danger.intersection(flags)
    if hits:
        score -= 12.0 + 3.0 * (len(hits) - 1)
        reasons.extend(sorted(hits))

    return round(max(0.0, min(100.0, score)), 1), reasons
