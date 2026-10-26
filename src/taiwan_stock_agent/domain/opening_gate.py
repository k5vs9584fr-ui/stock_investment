from __future__ import annotations

from taiwan_stock_agent.domain.opening_reorder import opening_reorder_score


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


def opening_confirmation_score(row: dict, phase_minutes: int = 15) -> tuple[float, list[str]]:
    """Compatibility wrapper around the phase-aware opening reorder model."""
    score, reasons = opening_reorder_score(row, phase_minutes=phase_minutes)
    if not (row.get("dt_metrics") or {}):
        return score, ["OPEN_CONFIRMATION_PENDING"]
    return score, reasons


def _sector_key(row: dict) -> str:
    return str(row.get("industry_code") or row.get("industry") or "").strip()


def promote_opening_candidates(
    rows: list[dict],
    target_n: int = 3,
    phase_minutes: int = 15,
    max_per_sector: int = 2,
) -> tuple[list[dict], list[dict]]:
    """Select live candidates using confirmation quality and concentration caps.

    A strong sector can still contribute two names, but a third same-sector name
    is skipped when a comparably ranked alternative exists. This reduces the
    chance of the portfolio being three versions of the same trade.
    """
    annotated: list[dict] = []
    rejected: list[dict] = []

    for row in rows:
        r = dict(row)
        ok, reasons = opening_eligibility(r)
        r["opening_eligible"] = ok
        r["opening_gate_reasons"] = reasons

        confirmation_score, confirmation_reasons = opening_confirmation_score(
            r, phase_minutes=phase_minutes
        )
        r["opening_confirmation_score"] = confirmation_score
        r["opening_confirmation_reasons"] = confirmation_reasons
        r["opening_phase_minutes"] = phase_minutes

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

    selected: list[dict] = []
    deferred: list[dict] = []
    sector_counts: dict[str, int] = {}

    for r in annotated:
        sector = _sector_key(r)
        if sector and max_per_sector > 0 and sector_counts.get(sector, 0) >= max_per_sector:
            x = dict(r)
            x["opening_gate_reasons"] = list(x.get("opening_gate_reasons") or []) + [
                "OPEN_SECTOR_CONCENTRATION_CAP"
            ]
            deferred.append(x)
            continue

        selected.append(r)
        if sector:
            sector_counts[sector] = sector_counts.get(sector, 0) + 1
        if len(selected) >= target_n:
            break

    # Only use capped same-sector names if diversification leaves too few names.
    if len(selected) < target_n:
        for r in deferred:
            selected.append(r)
            if len(selected) >= target_n:
                break

    for i, row in enumerate(selected, 1):
        row["opening_live_rank"] = i
        row["opening_live_tier"] = "LIVE_TOP3"

    return selected, rejected
