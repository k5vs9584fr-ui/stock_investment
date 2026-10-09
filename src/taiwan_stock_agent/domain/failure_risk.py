from __future__ import annotations


def failure_risk_overlay(row: dict) -> tuple[float, list[str]]:
    """Penalties calibrated from historical high-score loser diagnostics.

    Current evidence suggests heat/chase conditions are more associated with
    failed T+5 outcomes than breakout itself. Keep penalties moderate until
    larger out-of-sample samples accumulate.
    """
    flags = set(row.get("surge_flags") or row.get("flags") or [])
    bonus = 0.0
    out: list[str] = []

    if any(str(x).startswith("RSI_HOT") for x in flags):
        bonus -= 4.0
        out.append("FAILURE_RISK_RSI_HOT")

    if any(str(x).startswith("VOL_HYPERCHASE") for x in flags):
        bonus -= 5.0
        out.append("FAILURE_RISK_VOL_HYPERCHASE")

    if (
        any(str(x).startswith("RSI_HOT") for x in flags)
        and any(str(x).startswith("VOL_HYPERCHASE") for x in flags)
    ):
        bonus -= 3.0
        out.append("FAILURE_RISK_HEAT_COMBO")

    return round(bonus, 1), out
