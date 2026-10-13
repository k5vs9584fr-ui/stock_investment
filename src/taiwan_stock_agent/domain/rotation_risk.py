from __future__ import annotations


def rotation_risk_adjustment(
    held_row: dict,
    challenger_row: dict,
    base_decision: dict,
    same_sector_penalty: float = 3.0,
    same_theme_penalty: float = 2.0,
    diversification_bonus: float = 2.0,
) -> dict:
    """Adjust a rotation decision for concentration and diversification risk."""

    net_edge = float(
        base_decision.get("net_edge")
        if base_decision.get("net_edge") is not None
        else base_decision.get("edge")
        or 0.0
    )

    held_sector = str(held_row.get("industry_code") or held_row.get("industry") or "")
    challenger_sector = str(
        challenger_row.get("industry_code") or challenger_row.get("industry") or ""
    )

    held_themes = set(held_row.get("hot_concepts") or held_row.get("themes") or [])
    challenger_themes = set(
        challenger_row.get("hot_concepts") or challenger_row.get("themes") or []
    )

    reasons: list[str] = []
    risk_delta = 0.0

    if held_sector and challenger_sector and held_sector == challenger_sector:
        risk_delta -= float(same_sector_penalty)
        reasons.append("ROTATION_SAME_SECTOR")

    overlap = held_themes.intersection(challenger_themes)
    if overlap:
        risk_delta -= float(same_theme_penalty)
        reasons.append("ROTATION_THEME_OVERLAP")

    if held_sector and challenger_sector and held_sector != challenger_sector:
        risk_delta += float(diversification_bonus)
        reasons.append("ROTATION_DIVERSIFICATION_BONUS")

    risk_adjusted_edge = net_edge + risk_delta

    if risk_adjusted_edge >= 8.0:
        action = "ROTATE"
    elif risk_adjusted_edge >= 3.0:
        action = "WATCH_ROTATION"
    else:
        action = "KEEP_CURRENT"

    return {
        **base_decision,
        "risk_adjustment": round(risk_delta, 2),
        "risk_adjusted_edge": round(risk_adjusted_edge, 2),
        "rotation_risk_reasons": reasons,
        "action_after_risk": action,
    }
