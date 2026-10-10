from __future__ import annotations


def catalyst_overlay(row: dict) -> tuple[float, list[str]]:
    """Score event catalysts only when price/volume confirms them.

    Expected optional inputs:
      catalyst_type: revenue|earnings|guidance|industry|policy|peer_move|other
      catalyst_strength: 0..100
      catalyst_age_days: 0..10+
    """
    ctype = str(row.get("catalyst_type") or "").lower()
    strength = float(row.get("catalyst_strength") or 0.0)
    age = int(row.get("catalyst_age_days") or 99)
    surge = row.get("surge_metrics") or {}
    ret3 = float(surge.get("return3_pct") or 0.0)
    vol3 = float(surge.get("volume3_vs_20") or 1.0)
    close_strength = float(row.get("close_strength") or 0.5)

    if not ctype or strength <= 0:
        return 0.0, []

    flags: list[str] = []
    bonus = 0.0

    fresh = age <= 3
    confirmed = ret3 > 0.5 and vol3 >= 1.2 and close_strength >= 0.65
    rejected = ret3 < 0 and close_strength < 0.50

    if fresh and strength >= 70 and confirmed:
        bonus += 6.0
        flags.append("CATALYST_CONFIRMED")
    elif fresh and strength >= 50 and confirmed:
        bonus += 3.0
        flags.append("CATALYST_POSITIVE")

    if rejected:
        bonus -= 6.0
        flags.append("CATALYST_REJECTED_BY_PRICE")

    if age > 7:
        bonus *= 0.5
        flags.append("CATALYST_STALE")

    return round(bonus, 1), flags
