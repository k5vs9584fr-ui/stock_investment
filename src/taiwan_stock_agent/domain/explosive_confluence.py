from __future__ import annotations

from taiwan_stock_agent.domain.explosive_lifecycle import classify_explosive_lifecycle


def explosive_confluence_adjustment(row: dict) -> tuple[float, list[str]]:
    """Cross-check explosive phase, fresh catalyst and institutional direction.

    The preferred setup is not merely fast price action. It is an early explosive
    phase with a fresh catalyst and institutional buying aligned in the same
    direction. Price strength with institutional reversal is penalized.
    """
    lifecycle = classify_explosive_lifecycle(row)
    phase = str(lifecycle.get("phase") or "")
    flags: list[str] = []
    score = 0.0

    catalyst_type = str(row.get("catalyst_type") or "").lower()
    catalyst_strength = float(row.get("catalyst_strength") or 0.0)
    catalyst_age = int(row.get("catalyst_age_days") or 99)
    catalyst_fresh = bool(catalyst_type) and catalyst_strength >= 50 and catalyst_age <= 3

    chips = row.get("chip_metrics") or {}
    foreign = float(
        chips.get("foreign_5d")
        or ((chips.get("latest") or {}).get("foreign"))
        or 0.0
    )
    trust = float(
        chips.get("trust_5d")
        or ((chips.get("latest") or {}).get("trust"))
        or 0.0
    )
    inst = float(
        chips.get("inst_total_5d")
        or chips.get("inst_cumul_5d")
        or ((chips.get("latest") or {}).get("inst"))
        or 0.0
    )
    foreign_days = int(
        chips.get("foreign_buy_days")
        or chips.get("foreign_consecutive_buy_days")
        or 0
    )
    trust_days = int(
        chips.get("trust_buy_days")
        or chips.get("trust_consecutive_buy_days")
        or 0
    )
    inst_days = int(chips.get("inst_buy_days") or 0)

    early_explosive = phase in {"FRESH_IGNITION", "EARLY_MAIN_MOVE", "ACCELERATING"}
    institutional_positive = inst > 0 or foreign > 0 or trust > 0
    institutional_persistent = (
        (foreign > 0 and foreign_days >= 2)
        or (trust > 0 and trust_days >= 2)
        or (inst > 0 and inst_days >= 2)
    )
    institutional_negative = inst < 0 and foreign < 0

    if early_explosive and catalyst_fresh:
        score += 3.0
        flags.append("CONFLUENCE_EXPLOSIVE_CATALYST")

    if early_explosive and institutional_persistent:
        score += 4.0
        flags.append("CONFLUENCE_EXPLOSIVE_SMART_MONEY")

    if early_explosive and catalyst_fresh and institutional_persistent:
        score += 4.0
        flags.append("CONFLUENCE_TRIPLE_CONFIRM")

    if catalyst_fresh and institutional_positive and phase == "PRE_IGNITION":
        score += 2.0
        flags.append("CONFLUENCE_PREIGNITION_CATALYST_CHIPS")

    # Important anti-false-positive rule: a pretty ignition pattern should lose
    # priority when institutions reverse against it.
    if early_explosive and institutional_negative:
        score -= 8.0
        flags.append("CONFLUENCE_INSTITUTIONAL_REVERSAL")

    if early_explosive and foreign < 0 and foreign_days <= 1:
        score -= 3.0
        flags.append("CONFLUENCE_FOREIGN_SELL_PRESSURE")

    return round(max(-12.0, min(12.0, score)), 1), flags
