from __future__ import annotations


def chip_persistence_overlay(row: dict) -> tuple[float, list[str]]:
    m = row.get("chip_metrics") or {}
    flags: list[str] = []
    bonus = 0.0

    days = int(m.get("days") or 0)
    if days < 3:
        return 0.0, ["CHIP_DATA_THIN"] if days else []

    foreign_days = int(m.get("foreign_buy_days") or 0)
    trust_days = int(m.get("trust_buy_days") or 0)
    inst_days = int(m.get("inst_buy_days") or 0)
    foreign_sum = float(m.get("foreign_5d") or 0.0)
    trust_sum = float(m.get("trust_5d") or 0.0)
    inst_sum = float(m.get("inst_total_5d") or 0.0)
    margin_chg = float(m.get("margin_change_pct") or 0.0)

    if foreign_days >= 4 and foreign_sum > 0:
        bonus += 4.0
        flags.append("FOREIGN_PERSISTENT")
    elif foreign_days <= 1 and foreign_sum < 0:
        bonus -= 4.0
        flags.append("FOREIGN_PERSISTENT_SELL")

    if trust_days >= 4 and trust_sum > 0:
        bonus += 5.0
        flags.append("TRUST_PERSISTENT")
    elif trust_days == 0 and trust_sum < 0:
        bonus -= 4.0
        flags.append("TRUST_PERSISTENT_SELL")

    if inst_days >= 4 and inst_sum > 0:
        bonus += 4.0
        flags.append("INST_PERSISTENT_CONSENSUS")
    elif inst_days <= 1 and inst_sum < 0:
        bonus -= 4.0
        flags.append("INST_PERSISTENT_SELL")

    if inst_sum > 0 and margin_chg < 0:
        bonus += 3.0
        flags.append("SMART_MONEY_WITH_MARGIN_CLEANUP")
    elif inst_sum < 0 and margin_chg >= 2.0:
        bonus -= 5.0
        flags.append("BAD_CHIP_COMBINATION")

    return round(bonus, 1), flags
