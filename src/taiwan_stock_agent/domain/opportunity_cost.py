from __future__ import annotations

from taiwan_stock_agent.domain.explosive_lifecycle import classify_explosive_lifecycle


def opportunity_cost_score(row: dict) -> tuple[float, list[str]]:
    """Compare candidates on deployable-capital efficiency.

    This is not a standalone alpha model. It compresses actionability, momentum,
    confidence and risk into a single cross-sectional score used to decide which
    candidate deserves scarce capital first.
    """
    hybrid = float(row.get("hybrid_action_score") or 0.0)
    surge = float(row.get("surge_score") or 0.0)
    practical = float(row.get("practical_score") or 0.0)
    confidence = (row.get("score_confidence") or {}).get("level") or ""
    risk = row.get("risk_policy") or {}
    max_pos = float(risk.get("max_position_pct") or 10.0)
    flags = set(row.get("practical_flags") or [])
    lifecycle = classify_explosive_lifecycle(row)

    # Explosiveness-first capital efficiency: Hybrid remains the anchor, but\n    # surge gets more weight than slow practical quality so scarce capital is\n    # directed toward names with near-term acceleration potential.\n    score = hybrid * 0.50 + practical * 0.15 + surge * 0.30
    score += float(lifecycle.get("score") or 0.0) * 0.20
    flags_out: list[str] = []

    if lifecycle.get("phase") == "OVERHEATED":
        score -= 18.0
        flags_out.append("OC_OVERHEATED_NO_CHASE")
    elif lifecycle.get("phase") in {"FRESH_IGNITION", "EARLY_MAIN_MOVE"}:
        score += 3.0
        flags_out.append("OC_EXPLOSIVE_PHASE_BONUS")

    if confidence == "HIGH":
        score += 4.0
        flags_out.append("OC_HIGH_CONFIDENCE")
    elif confidence == "MEDIUM":
        score += 1.0
    elif confidence == "LOW":
        score -= 5.0
        flags_out.append("OC_LOW_CONFIDENCE")
    elif confidence == "CONFLICT":
        score -= 10.0
        flags_out.append("OC_MODEL_CONFLICT")

    if max_pos >= 20:
        score += 2.0
    elif max_pos <= 10:
        score -= 2.0

    if "OVEREXTENDED_PENALTY" in flags or "MODEL_ONLY_STAGNATION_PENALTY" in flags:
        score -= 8.0
        flags_out.append("OC_POOR_CAPITAL_EFFICIENCY")

    return round(max(0.0, min(100.0, score)), 1), flags_out


def replacement_decision(held_row: dict, challenger_row: dict, min_edge: float = 8.0) -> dict:
    held_score, _ = opportunity_cost_score(held_row)
    challenger_score, _ = opportunity_cost_score(challenger_row)
    edge = challenger_score - held_score

    if edge >= min_edge:
        action = "ROTATE"
    elif edge >= 3:
        action = "WATCH_ROTATION"
    else:
        action = "KEEP_CURRENT"

    return {
        "action": action,
        "held_score": held_score,
        "challenger_score": challenger_score,
        "edge": round(edge, 1),
        "min_edge": min_edge,
    }
