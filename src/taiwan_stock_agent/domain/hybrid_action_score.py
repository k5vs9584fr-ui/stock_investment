from __future__ import annotations


def hybrid_action_score(final_score: float, top3_quality_score: float) -> float:
    """Blend structural/model quality with practical action quality.

    50/50 is the current research default based on historical proxy walk-forward
    results. Keep the components visible so the blend remains auditable.
    """
    score = 0.50 * float(final_score) + 0.50 * float(top3_quality_score)
    return round(max(0.0, min(100.0, score)), 1)
