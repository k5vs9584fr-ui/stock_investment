from __future__ import annotations


def classify_explosive_lifecycle(row: dict) -> dict:
    """Classify a candidate into a practical explosive-move lifecycle.

    Priority is not simply highest surge score. The preferred zone is the first
    ignition or early main move while the setup is still buyable.
    """
    stage = str(row.get("surge_stage") or "")
    metrics = row.get("surge_metrics") or {}
    flags = set(row.get("surge_flags") or [])

    surge_score = float(row.get("surge_score") or 0.0)
    ret3 = float(metrics.get("return3_pct") or 0.0)
    ret5 = float(metrics.get("return5_pct") or 0.0)
    ret10 = float(metrics.get("return10_pct") or 0.0)
    fresh = bool(metrics.get("fresh_ignition"))
    early = bool(metrics.get("early_main_move"))
    accel = bool(metrics.get("trend_accelerator"))
    overextended = bool(metrics.get("overextended"))
    chaseable = bool(metrics.get("chaseable"))
    vol = float(metrics.get("volume3_vs_20") or 0.0)

    if overextended or stage.startswith("X") or "CHASE_OVEREXTENDED" in flags:
        return {
            "phase": "OVERHEATED",
            "label": "過熱禁追",
            "priority": 0,
            "score": 0.0,
            "action": "NO_CHASE",
        }

    lifecycle_score = 0.0
    phase = "PRE_IGNITION"
    label = "預備發動"
    priority = 1
    action = "WATCH"

    if fresh:
        phase = "FRESH_IGNITION"
        label = "首發動"
        priority = 4
        action = "ATTACK_ON_CONFIRMATION"
        lifecycle_score += 18.0
    elif early:
        phase = "EARLY_MAIN_MOVE"
        label = "主升初段"
        priority = 5
        action = "ATTACK_PULLBACK_OR_BREAKOUT"
        lifecycle_score += 20.0
    elif accel and 1.0 <= ret3 <= 5.0:
        phase = "ACCELERATING"
        label = "加速中"
        priority = 3
        action = "ATTACK_ONLY_IF_NOT_STRETCHED"
        lifecycle_score += 12.0
    elif surge_score >= 50 or "BREAKOUT_20D" in flags:
        phase = "PRE_IGNITION"
        label = "蓄勢待發"
        priority = 2
        action = "WATCH_BREAKOUT"
        lifecycle_score += 7.0

    if chaseable:
        lifecycle_score += 5.0
    if "VOLUME_EXPANSION" in flags or vol >= 1.5:
        lifecycle_score += 5.0
    if 1.0 <= ret3 <= 4.5:
        lifecycle_score += 4.0
    if 2.0 <= ret5 <= 8.0:
        lifecycle_score += 4.0

    # Main-move names can still be powerful, but avoid rewarding a move that has
    # already consumed too much of its short-term range.
    if ret10 >= 25.0:
        lifecycle_score -= 5.0
    if ret5 >= 12.0:
        lifecycle_score -= 4.0

    return {
        "phase": phase,
        "label": label,
        "priority": priority,
        "score": round(max(0.0, min(40.0, lifecycle_score)), 1),
        "action": action,
    }
