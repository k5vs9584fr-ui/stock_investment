from __future__ import annotations

from taiwan_stock_agent.domain.explosive_lifecycle import classify_explosive_lifecycle


def explosive_failure_adjustment(row: dict, phase_minutes: int = 15) -> dict:
    """Evaluate whether an explosive setup is failing after the open.

    Fresh ignition and early-main-move setups must prove persistence:
    - 15m: hold VWAP, keep positive momentum, preserve volume participation.
    - 30m: hold near the session high and avoid momentum/volume fade.
    """
    lifecycle = classify_explosive_lifecycle(row)
    m = row.get("dt_metrics") or {}
    base_phase = str(lifecycle.get("phase") or "")
    reasons: list[str] = []

    if not m or base_phase not in {"FRESH_IGNITION", "EARLY_MAIN_MOVE", "ACCELERATING"}:
        return {
            "failed": False,
            "severity": "NONE",
            "penalty": 0.0,
            "action": lifecycle.get("action"),
            "reasons": reasons,
        }

    vwap_gap = float(m.get("vwap_gap_pct") or 0.0)
    ret15 = float(m.get("return_15m_pct") or 0.0)
    ret30 = float(m.get("return_30m_pct") or ret15)
    vol = float(m.get("volume_accel_5m") or 1.0)
    near_high = float(m.get("near_intraday_high") or 0.0)

    penalty = 0.0
    severity = "NONE"

    if phase_minutes >= 15:
        if vwap_gap < -0.4:
            penalty -= 8.0
            reasons.append("EXPLOSIVE_FAIL_BELOW_VWAP")
        if ret15 < 0.0:
            penalty -= 6.0
            reasons.append("EXPLOSIVE_FAIL_NO_15M_FOLLOWTHROUGH")
        if vol < 0.8:
            penalty -= 5.0
            reasons.append("EXPLOSIVE_FAIL_VOLUME_FADE")

    if phase_minutes >= 30:
        if ret30 < 0.2:
            penalty -= 7.0
            reasons.append("EXPLOSIVE_FAIL_30M_MOMENTUM")
        if near_high < 0.955:
            penalty -= 8.0
            reasons.append("EXPLOSIVE_FAIL_LOST_HIGH_ZONE")
        if vol < 0.75:
            penalty -= 4.0
            reasons.append("EXPLOSIVE_FAIL_30M_VOLUME_FADE")

    if penalty <= -16.0:
        severity = "HARD_FAIL"
        action = "DROP_FROM_ATTACK"
    elif penalty <= -8.0:
        severity = "SOFT_FAIL"
        action = "WATCH_ONLY"
    else:
        action = lifecycle.get("action")

    return {
        "failed": severity != "NONE",
        "severity": severity,
        "penalty": penalty,
        "action": action,
        "reasons": reasons,
    }
