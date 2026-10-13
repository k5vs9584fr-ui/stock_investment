from __future__ import annotations


def divergence_overlay(row: dict) -> tuple[float, list[str]]:
    surge = row.get("surge_metrics") or {}
    structure = row.get("structure_metrics") or {}
    flags: list[str] = []
    bonus = 0.0

    ret3 = float(surge.get("return3_pct") or 0.0)
    ret5 = float(surge.get("return5_pct") or 0.0)
    vol3 = float(surge.get("volume3_vs_20") or 1.0)
    close_strength = float(row.get("close_strength") or 0.5)
    near20 = float(structure.get("near_20d_high") or 0.0)

    if vol3 >= 1.8 and ret3 < 0.8 and close_strength < 0.60:
        bonus -= 6.0
        flags.append("BEARISH_VOLUME_PRICE_DIVERGENCE")

    if vol3 <= 0.9 and ret5 > 2.0 and near20 >= 0.90 and close_strength >= 0.70:
        bonus += 3.0
        flags.append("HEALTHY_LOW_VOLUME_ADVANCE")

    breakout = "BREAKOUT_20D" in set(row.get("surge_flags") or [])
    if breakout and close_strength < 0.45:
        bonus -= 8.0
        flags.append("FAILED_BREAKOUT_WEAK_CLOSE")

    return round(bonus, 1), flags
