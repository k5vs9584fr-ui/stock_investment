from __future__ import annotations


def score_confidence(row: dict) -> dict:
    final_score = float(row.get("final_score") or 0.0)
    practical = float(row.get("practical_score") or 0.0)
    quality = float(row.get("top3_quality_score") or practical)

    spread = max(final_score, practical, quality) - min(final_score, practical, quality)

    if spread <= 8:
        level = "HIGH"
        multiplier = 1.00
    elif spread <= 15:
        level = "MEDIUM"
        multiplier = 0.85
    elif spread <= 25:
        level = "LOW"
        multiplier = 0.65
    else:
        level = "CONFLICT"
        multiplier = 0.45

    return {
        "level": level,
        "spread": round(spread, 1),
        "position_multiplier": multiplier,
    }
