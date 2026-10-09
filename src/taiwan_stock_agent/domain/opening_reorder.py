from __future__ import annotations


def opening_reorder_score(row: dict) -> tuple[float, list[str]]:
    """Re-rank candidates after the open using intraday confirmation."""
    base = float(row.get("hybrid_action_score") or 0.0)
    m = row.get("dt_metrics") or {}
    flags: list[str] = []
    score = base

    if not m:
        return round(base, 1), []

    vol_accel = float(m.get("volume_accel_5m") or 1.0)
    ret15 = float(m.get("return_15m_pct") or 0.0)
    vwap_gap = float(m.get("vwap_gap_pct") or 0.0)
    near_high = float(m.get("near_intraday_high") or 0.0)

    if vol_accel >= 1.6:
        score += 8
        flags.append("OPEN_VOL_ACCEL_PRIME")
    elif vol_accel >= 1.25:
        score += 4
        flags.append("OPEN_VOL_ACCEL")

    if 0.3 <= ret15 <= 2.5:
        score += 6
        flags.append("OPEN_MOMENTUM_HEALTHY")
    elif ret15 < -0.5:
        score -= 6
        flags.append("OPEN_MOMENTUM_WEAK")
    elif ret15 > 3.5:
        score -= 4
        flags.append("OPEN_TOO_HOT")

    if 0 <= vwap_gap <= 2:
        score += 5
        flags.append("OPEN_ABOVE_VWAP")
    elif vwap_gap < -0.5:
        score -= 7
        flags.append("OPEN_BELOW_VWAP")

    if near_high >= 0.99:
        score += 4
        flags.append("OPEN_NEAR_HIGH")

    return round(max(0.0, min(100.0, score)), 1), flags
