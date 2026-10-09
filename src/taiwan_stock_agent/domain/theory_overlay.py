"""Theory overlay derived from falsifiable rules used by major stock traders.

Only measurable ideas are encoded here. The overlay is deliberately modest:
it should refine ranking, not overwhelm empirical scores.
"""
from __future__ import annotations


def calculate_theory_overlay(row: dict) -> tuple[float, list[str]]:
    bonus = 0.0
    flags: list[str] = []

    structure = row.get("structure_metrics") or {}
    surge = row.get("surge_metrics") or {}
    sflags = set(row.get("structure_flags") or [])
    gflags = set(row.get("surge_flags") or [])
    chip = float(row.get("chip_score") or 50.0)
    close_strength = float(row.get("close_strength") or 0.5)

    ma_spread = float(structure.get("ma_spread_pct") or 99.0)
    vol5_vs20 = float(structure.get("vol5_vs_20") or 1.0)
    near20 = float(structure.get("near_20d_high") or 0.0)
    range20 = float(structure.get("range20_pct") or 99.0)
    ret3 = float(surge.get("return3_pct") or 0.0)
    ret5 = float(surge.get("return5_pct") or 0.0)
    volume3_vs20 = float(surge.get("volume3_vs_20") or 1.0)

    # O'Neil: leaders near/new highs, volume confirmation, institutional support.
    oneil = (
        near20 >= 0.95
        and ("BREAKOUT_20D" in gflags or "NEAR_BREAKOUT" in sflags or "AT_BREAKOUT" in sflags)
        and chip >= 65
    )
    if oneil:
        bonus += 5.0
        flags.append("ONEIL_LEADER_BREAKOUT")

    # Minervini: volatility contraction / tight base near highs with drying volume.
    vcp = (
        ma_spread <= 4.0
        and vol5_vs20 <= 0.85
        and range20 <= 18.0
        and near20 >= 0.90
        and "NOT_EXTENDED_10D" in sflags
    )
    if vcp:
        bonus += 6.0
        flags.append("MINERVINI_VCP_LIKE")

    # Livermore: pivotal point confirmed by trend + breakout; no anticipation.
    pivot = (
        ("BREAKOUT_20D" in gflags or "AT_BREAKOUT" in sflags)
        and close_strength >= 0.75
        and ret3 > 0
    )
    if pivot:
        bonus += 4.0
        flags.append("LIVERMORE_PIVOT_CONFIRM")

    # Weinstein Stage 2 proxy: rising trend, bullish alignment, close near highs.
    stage2 = (
        "MA20_RISING" in sflags
        and ("MA_BULL_STACK" in gflags or ma_spread > 0)
        and near20 >= 0.90
        and ret5 > 0
    )
    if stage2:
        bonus += 3.0
        flags.append("WEINSTEIN_STAGE2_PROXY")

    # Wyckoff effort-vs-result warning: heavy relative volume but little upside.
    effort_no_result = (
        volume3_vs20 >= 1.8
        and ret3 < 1.0
        and close_strength < 0.65
    )
    if effort_no_result:
        bonus -= 7.0
        flags.append("WYCKOFF_EFFORT_NO_RESULT_WARNING")

    # Distribution-like warning: strong recent advance but weak close near resistance.
    distribution_risk = (
        ret5 >= 8.0
        and close_strength < 0.55
        and volume3_vs20 >= 1.3
    )
    if distribution_risk:
        bonus -= 8.0
        flags.append("DISTRIBUTION_RISK")

    return round(bonus, 1), flags
