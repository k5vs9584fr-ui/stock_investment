from __future__ import annotations


def chip_persistence_overlay(row: dict) -> tuple[float, list[str]]:
    m = row.get("chip_metrics") or {}
    flags: list[str] = []
    bonus = 0.0

    # Support both legacy 5-day aggregate schema and the current chip-refine schema.
    legacy_days = int(m.get("days") or 0)
    available = bool(m.get("available", legacy_days > 0))
    if not available:
        return 0.0, ["CHIP_DATA_THIN"]

    foreign_days = int(
        m.get("foreign_buy_days")
        or m.get("foreign_consecutive_buy_days")
        or 0
    )
    trust_days = int(
        m.get("trust_buy_days")
        or m.get("trust_consecutive_buy_days")
        or 0
    )
    inst_days = int(
        m.get("inst_buy_days")
        or (2 if "INST_BUY_2_OF_3" in set(row.get("chip_flags") or []) else 0)
        or 0
    )

    foreign_sum = float(
        m.get("foreign_5d")
        or ((m.get("latest") or {}).get("foreign"))
        or 0.0
    )
    trust_sum = float(
        m.get("trust_5d")
        or ((m.get("latest") or {}).get("trust"))
        or 0.0
    )
    inst_sum = float(
        m.get("inst_total_5d")
        or m.get("inst_cumul_5d")
        or ((m.get("latest") or {}).get("inst"))
        or 0.0
    )

    margin_chg = m.get("margin_change_pct")
    if margin_chg is None:
        raw_margin = m.get("margin_change")
        margin_chg = float(raw_margin) if raw_margin is not None else 0.0
        # Current schema may store raw share change, not percent. Use direction only.
        margin_pct_known = False
    else:
        margin_chg = float(margin_chg)
        margin_pct_known = True

    if foreign_days >= 4 and foreign_sum > 0:
        bonus += 4.0
        flags.append("FOREIGN_PERSISTENT")
    elif foreign_days >= 2 and foreign_sum > 0:
        bonus += 2.0
        flags.append("FOREIGN_PERSISTENT_SHORT")
    elif foreign_days <= 1 and foreign_sum < 0:
        bonus -= 4.0
        flags.append("FOREIGN_PERSISTENT_SELL")

    if trust_days >= 4 and trust_sum > 0:
        bonus += 5.0
        flags.append("TRUST_PERSISTENT")
    elif trust_days >= 2 and trust_sum > 0:
        bonus += 2.0
        flags.append("TRUST_PERSISTENT_SHORT")
    elif trust_days == 0 and trust_sum < 0:
        bonus -= 4.0
        flags.append("TRUST_PERSISTENT_SELL")

    if legacy_days >= 3:
        if inst_days >= 4 and inst_sum > 0:
            bonus += 4.0
            flags.append("INST_PERSISTENT_CONSENSUS")
        elif inst_days <= 1 and inst_sum < 0:
            bonus -= 4.0
            flags.append("INST_PERSISTENT_SELL")
    else:
        chip_flags = set(row.get("chip_flags") or [])
        if "INST_CONSEC_2D" in chip_flags and inst_sum > 0:
            bonus += 3.0
            flags.append("INST_PERSISTENT_CONSENSUS_SHORT")

    if inst_sum > 0 and margin_chg < 0:
        bonus += 3.0
        flags.append("SMART_MONEY_WITH_MARGIN_CLEANUP")
    elif inst_sum < 0 and margin_chg > 0:
        # Only apply the stronger version when percent magnitude is known.
        bonus -= 5.0 if (margin_pct_known and margin_chg >= 2.0) else 3.0
        flags.append("BAD_CHIP_COMBINATION")

    return round(bonus, 1), flags
