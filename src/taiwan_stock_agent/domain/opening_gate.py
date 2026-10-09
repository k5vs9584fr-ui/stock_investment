from __future__ import annotations


def opening_eligibility(row: dict) -> tuple[bool, list[str]]:
    """Hard opening gate for premarket candidates.

    Missing intraday metrics are neutral: keep the candidate eligible until
    enough opening data exists.
    """
    m = row.get("dt_metrics") or {}
    if not m:
        return True, ["OPEN_DATA_PENDING"]

    reasons: list[str] = []
    eligible = True

    vwap_gap = float(m.get("vwap_gap_pct") or 0.0)
    ret15 = float(m.get("return_15m_pct") or 0.0)
    vol_accel = float(m.get("volume_accel_5m") or 1.0)
    near_high = float(m.get("near_intraday_high") or 0.0)
    support = float(m.get("recent_support") or 0.0)
    price = float(row.get("price") or 0.0)

    if vwap_gap < -0.8:
        eligible = False
        reasons.append("OPEN_FAIL_BELOW_VWAP")
    if ret15 < -1.2:
        eligible = False
        reasons.append("OPEN_FAIL_MOMENTUM")
    if vol_accel < 0.55 and ret15 <= 0:
        eligible = False
        reasons.append("OPEN_FAIL_VOLUME")
    if near_high < 0.94 and ret15 < 0:
        eligible = False
        reasons.append("OPEN_FAIL_RELATIVE_WEAKNESS")
    if support > 0 and price > 0 and price < support * 0.995:
        eligible = False
        reasons.append("OPEN_FAIL_SUPPORT_BREAK")

    if eligible:
        reasons.append("OPEN_ELIGIBLE")
    return eligible, reasons


def opening_confirmation_score(row: dict) -> tuple[float, list[str]]:
    """Re-rank eligible names using first-15-minute confirmation quality.

    The premarket/hybrid score remains the anchor. Opening data can promote a
    candidate that confirms with VWAP + momentum + volume, or demote one that is
    already too extended / losing the high.
    """
    base = float(row.get("opening_reorder_score") or row.get("hybrid_action_score") or 0.0)
    m = row.get("dt_metrics") or {}
    if not m:
        return round(base, 1), ["OPEN_CONFIRMATION_PENDING"]

    score = base
    reasons: list[str] = []

    vwap_gap = float(m.get("vwap_gap_pct") or 0.0)
    ret15 = float(m.get("return_15m_pct") or 0.0)
    vol_accel = float(m.get("volume_accel_5m") or 1.0)
    near_high = float(m.get("near_intraday_high") or 0.0)

    if 0.15 <= vwap_gap <= 2.5:
        score += 3.0
        reasons.append("OPEN_ABOVE_VWAP")
    elif vwap_gap > 4.0:
        score -= 6.0
        reasons.append("OPEN_CHASE_RISK")

    if 0.25 <= ret15 <= 3.0:
        score += 3.0
        reasons.append("OPEN_POSITIVE_MOMENTUM")
    elif ret15 > 5.0:
        score -= 6.0
        reasons.append("OPEN_MOMENTUM_OVEREXTENDED")

    if vol_accel >= 1.4:
        score += 4.0
        reasons.append("OPEN_VOLUME_CONFIRMATION")
    elif vol_accel < 0.8 and ret15 > 0:
        score -= 3.0
        reasons.append("OPEN_THIN_VOLUME")

    if near_high >= 0.985:
        score += 3.0
        reasons.append("OPEN_HOLDING_HIGH")
    elif near_high < 0.96:
        score -= 4.0
        reasons.append("OPEN_REJECTED_FROM_HIGH")

    return round(max(0.0, min(100.0, score)), 1), reasons


def promote_opening_candidates(rows: list[dict], target_n: int = 3) -> tuple[list[dict], list[dict]]:
    """Select the best eligible opening candidates and log rejected names.

    Ranking uses opening confirmation quality first, then premarket Hybrid and
    opportunity-cost score as tie-breakers.
    """
    annotated = []
    rejected = []

    for row in rows:
        r = dict(row)
        ok, reasons = opening_eligibility(r)
        r["opening_eligible"] = ok
        r["opening_gate_reasons"] = reasons

        confirmation_score, confirmation_reasons = opening_confirmation_score(r)
        r["opening_confirmation_score"] = confirmation_score
        r["opening_confirmation_reasons"] = confirmation_reasons

        if ok:
            annotated.append(r)
        else:
            rejected.append(r)

    annotated.sort(
        key=lambda r: (
            float(r.get("opening_confirmation_score") or 0.0),
            float(r.get("hybrid_action_score") or 0.0),
            float(r.get("opportunity_cost_score") or 0.0),
        ),
        reverse=True,
    )

    selected = annotated[:target_n]
    for i, row in enumerate(selected, 1):
        row["opening_live_rank"] = i
        row["opening_live_tier"] = "LIVE_TOP3"

    return selected, rejected
