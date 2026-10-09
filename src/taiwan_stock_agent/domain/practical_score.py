"""Practical trading score for ranking short-horizon Taiwan stock candidates.

This layer intentionally sits on top of the existing model. It rewards realized
momentum/ignition and penalizes model-only names that are structurally attractive
but not actually moving, plus stocks that are already overextended.

The goal is ranking, not replacing the underlying signal model.
"""
from __future__ import annotations

from taiwan_stock_agent.domain.theory_overlay import calculate_theory_overlay
from taiwan_stock_agent.domain.market_regime import market_regime_adjustment


def _clip(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _momentum_score(ret3: float, ret5: float, ret10: float) -> float:
    """Map short-horizon realized returns to a 0-100 momentum score.

    Sweet spot favors positive but not extreme movement. Overextension is handled
    separately as a penalty, so this component can remain monotonic.
    """
    raw = 50.0 + ret3 * 4.0 + ret5 * 2.0 + ret10 * 0.75
    return _clip(raw)


def calculate_practical_score(row: dict, market_context: dict | None = None) -> tuple[float, list[str]]:
    """Return (score, flags) using only fields already present in scan rows."""
    final_score = float(row.get("final_score") or 0.0)
    chip_score = float(row.get("chip_score") or 50.0)
    surge_score = float(row.get("surge_score") or 0.0)
    close_strength = float(row.get("close_strength") or 0.5)

    metrics = row.get("surge_metrics") or {}
    ret3 = float(metrics.get("return3_pct") or 0.0)
    ret5 = float(metrics.get("return5_pct") or 0.0)
    ret10 = float(metrics.get("return10_pct") or 0.0)
    fresh_ignition = bool(metrics.get("fresh_ignition"))
    early_main_move = bool(metrics.get("early_main_move"))
    overextended = bool(metrics.get("overextended"))
    trend_accelerator = bool(metrics.get("trend_accelerator"))

    flags: list[str] = []

    momentum = _momentum_score(ret3, ret5, ret10)
    score = (
        final_score * 0.30
        + chip_score * 0.15
        + surge_score * 0.25
        + momentum * 0.20
        + _clip(close_strength * 100.0) * 0.10
    )

    surge_flags = set(row.get("surge_flags") or [])

    if fresh_ignition:
        score += 10.0
        flags.append("FRESH_IGNITION_BONUS")
    if early_main_move:
        score += 8.0
        flags.append("EARLY_MAIN_MOVE_BONUS")
    if trend_accelerator:
        score += 5.0
        flags.append("TREND_ACCELERATOR_BONUS")
    if "VOLUME_EXPANSION" in surge_flags:
        score += 4.0
        flags.append("VOLUME_EXPANSION_BONUS")

    theory_bonus, theory_flags = calculate_theory_overlay(row)
    score += theory_bonus
    flags.extend(theory_flags)

    regime_bonus, regime_flags = market_regime_adjustment(market_context)
    score += regime_bonus
    flags.extend(regime_flags)

    # "High education, no work experience": strong base model but little realized movement.
    stagnant = (
        final_score >= 82.0
        and surge_score < 35.0
        and abs(ret3) < 1.0
        and abs(ret5) < 2.0
    )
    if stagnant:
        score -= 18.0
        # A structurally strong but motionless name should never occupy the
        # main action list until price/volume proves otherwise.
        score = min(score, 59.0)
        flags.append("MODEL_ONLY_STAGNATION_PENALTY")

    # Very weak realized movement gets a smaller efficiency penalty even if the
    # base model itself is not A+.
    if surge_score < 20.0 and ret5 <= 1.0 and not fresh_ignition:
        score -= 7.0
        flags.append("LOW_EXPLOSIVENESS_PENALTY")

    if overextended or str(row.get("surge_stage", "")).startswith("X"):
        score -= 25.0
        # Hard gate: an already overextended name can stay on the audit list,
        # but cannot rank as an actionable Practical A/B candidate.
        score = min(score, 59.0)
        flags.append("OVEREXTENDED_PENALTY")

    return round(_clip(score), 1), flags


def practical_phase(score: float) -> str:
    if score >= 82:
        return "P-A+：實戰強候選"
    if score >= 72:
        return "P-A：優先觀察"
    if score >= 62:
        return "P-B：等待確認"
    return "P-C：效率偏低"
