from __future__ import annotations

from taiwan_stock_agent.domain.explosive_failure import explosive_failure_adjustment


def _clip(value: float) -> float:
    return max(0.0, min(100.0, value))


def missed_entry_penalty(row: dict) -> tuple[float, list[str]]:
    """Penalize names that are still strong but no longer offer a clean entry.

    Strong stocks should not stay at the top of the actionable list forever.
    When the live price stretches too far from VWAP / planned entry, the system
    keeps the name visible but downgrades its deployability.
    """
    m = row.get("dt_metrics") or {}
    if not m:
        return 0.0, []

    vwap_gap = float(m.get("vwap_gap_pct") or 0.0)
    planned_gap = float(m.get("planned_entry_gap_pct") or 0.0)
    ret15 = float(m.get("return_15m_pct") or 0.0)
    near_high = float(m.get("near_intraday_high") or 0.0)

    penalty = 0.0
    flags: list[str] = []

    if vwap_gap >= 3.0:
        penalty -= 5.0
        flags.append("ENTRY_STRETCHED_FROM_VWAP")
    if planned_gap >= 2.5:
        penalty -= 6.0
        flags.append("MISSED_PLANNED_ENTRY")
    if ret15 >= 4.5:
        penalty -= 5.0
        flags.append("ENTRY_MOMENTUM_CHASE_RISK")
    if near_high >= 0.995 and vwap_gap >= 2.5:
        penalty -= 3.0
        flags.append("ENTRY_NEAR_HIGH_CHASE_RISK")

    return penalty, flags


def opening_reorder_score(row: dict, phase_minutes: int = 15) -> tuple[float, list[str]]:
    """Re-rank candidates after the open using phase-aware confirmation.

    5m favors early participation and volume ignition.
    15m is the balanced default.
    30m favors persistence and punishes failed early spikes more heavily.
    """
    base = float(row.get("hybrid_action_score") or 0.0)
    m = row.get("dt_metrics") or {}
    flags: list[str] = []
    score = base

    if not m:
        return round(base, 1), []

    vol_accel = float(m.get("volume_accel_5m") or 1.0)
    ret5 = float(m.get("return_5m_pct") or 0.0)
    ret15 = float(m.get("return_15m_pct") or 0.0)
    ret30 = float(m.get("return_30m_pct") or ret15)
    vwap_gap = float(m.get("vwap_gap_pct") or 0.0)
    near_high = float(m.get("near_intraday_high") or 0.0)

    if phase_minutes <= 5:
        if vol_accel >= 1.8:
            score += 7
            flags.append("OPEN5_VOL_IGNITION")
        elif vol_accel >= 1.3:
            score += 3
            flags.append("OPEN5_VOL_CONFIRM")

        if 0.1 <= ret5 <= 1.8:
            score += 5
            flags.append("OPEN5_MOMENTUM_HEALTHY")
        elif ret5 > 2.8:
            score -= 4
            flags.append("OPEN5_TOO_HOT")
        elif ret5 < -0.6:
            score -= 5
            flags.append("OPEN5_WEAK")

    elif phase_minutes >= 30:
        if vol_accel >= 1.25:
            score += 4
            flags.append("OPEN30_VOLUME_PERSISTENCE")
        elif vol_accel < 0.75 and ret30 > 0:
            score -= 4
            flags.append("OPEN30_VOLUME_FADE")

        if 0.4 <= ret30 <= 3.5:
            score += 7
            flags.append("OPEN30_TREND_PERSISTENCE")
        elif ret30 < -0.8:
            score -= 8
            flags.append("OPEN30_TREND_FAILURE")
        elif ret30 > 5.0:
            score -= 6
            flags.append("OPEN30_TOO_EXTENDED")

        if near_high >= 0.985:
            score += 5
            flags.append("OPEN30_HOLDING_HIGH")
        elif near_high < 0.95 and ret30 <= 0:
            # A 30-minute failure to reclaim the early high is materially worse
            # than a normal pullback: by this point the candidate has had enough
            # time to prove persistence. Keep the penalty strong enough to push
            # a borderline 75-point setup out of the actionable tier.
            score -= 7
            flags.append("OPEN30_FAILED_SPIKE")

    else:
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
    elif vwap_gap > 4.0:
        score -= 5
        flags.append("OPEN_VWAP_CHASE_RISK")

    if near_high >= 0.99:
        score += 4
        flags.append("OPEN_NEAR_HIGH")

    penalty, penalty_flags = missed_entry_penalty(row)
    score += penalty
    flags.extend(penalty_flags)

    failure = explosive_failure_adjustment(row, phase_minutes=phase_minutes)
    score += float(failure.get("penalty") or 0.0)
    flags.extend(failure.get("reasons") or [])
    if failure.get("severity") == "HARD_FAIL":
        score = min(score, 59.0)
        flags.append("EXPLOSIVE_HARD_FAIL_DROP")
    elif failure.get("severity") == "SOFT_FAIL":
        score = min(score, 71.0)
        flags.append("EXPLOSIVE_SOFT_FAIL_WATCH_ONLY")

    return round(_clip(score), 1), flags
