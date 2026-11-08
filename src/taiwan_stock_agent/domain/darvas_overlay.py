from __future__ import annotations

def darvas_overlay(row: dict) -> tuple[float, list[str]]:
    s = row.get("structure_metrics") or {}
    g = row.get("surge_metrics") or {}
    sf = set(row.get("structure_flags") or [])
    gf = set(row.get("surge_flags") or [])
    close_strength = float(row.get("close_strength") or 0.5)
    range20 = float(s.get("range20_pct") or 99.0)
    near20 = float(s.get("near_20d_high") or 0.0)
    ret3 = float(g.get("return3_pct") or 0.0)

    breakout = "BREAKOUT_20D" in gf or "AT_BREAKOUT" in sf
    tight_box = range20 <= 16.0 and near20 >= 0.94 and "NOT_EXTENDED_10D" in sf

    if tight_box and breakout and close_strength >= 0.75:
        return 5.0, ["DARVAS_BOX_BREAKOUT"]

    if breakout and close_strength < 0.50 and ret3 <= 0.5:
        return -8.0, ["DARVAS_FAILED_BREAKOUT"]

    return 0.0, []
