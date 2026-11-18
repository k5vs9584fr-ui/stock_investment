"""Risk-first EOD watchlist classification; never an intraday or execution signal.

Uses only the official *single-day* OHLCV dataset. Fundamental and multi-day
trend confirmation remain UNKNOWN, not imputed. All prices are hypothetical.
"""
from __future__ import annotations

from math import isfinite

WEIGHTS = {"risk_reward": 30, "location": 25, "price_structure": 20,
           "fundamental": 15, "liquidity": 10}


def finite(value):
    try:
        v = float(value)
        return v if isfinite(v) else None
    except (TypeError, ValueError):
        return None


def evaluate(row):
    """Return conservative, reproducible classification without invented prices."""
    p = finite(row.get("close"))
    hi = finite(row.get("high"))
    lo = finite(row.get("low"))
    pct = finite(row.get("change_pct"))
    value = finite(row.get("value"))
    strength = finite(row.get("close_strength"))
    if (None in (p, hi, lo, pct, value, strength) or p <= 0
            or lo <= 0 or hi <= lo or not lo <= p <= hi or value <= 0):
        return None
    if row.get("symbol") == "2344":
        return None

    span = hi - lo
    range_pct = span / p * 100
    # Note: values are observations on the last EOD bar, NOT support levels.
    near_low = (p - lo) / span
    prior_close = p / (1 + pct / 100) if pct > -99.9 else None
    if prior_close is None or prior_close <= 0:
        return None

    # Price location matters; close at day's high is NOT a safe low entry.
    location_score = round(25 * (1 - near_low), 2)
    structure_score = round(20 * strength, 2)
    liquidity_score = min(10, round(10 * value / 1_000_000_000, 2))
    fundamental_score = None  # Not in official daily quotes.
    rr = None
    stop = None
    target = None
    style = "WAIT_ONLY"
    reasons = []

    if -10 <= pct <= -1 and 0.55 <= strength <= 0.9 and value >= 200_000_000:
        # Snapback to yesterday's close is a SCENARIO, not an expected return.
        style = "PANIC_REVERSAL_WATCH"
        stop = round(lo * 0.995, 2)
        target = round(prior_close, 2)
        risk = p - stop
        reward = target - p
        if risk > 0 and reward > 0:
            rr = round(reward / risk, 2)
        else:
            reasons.append("NO_POSITIVE_REWARD")
    elif 0 <= pct < 4 and strength >= 0.75 and range_pct <= 8:
        style = "EARLY_STRENGTH_WATCH"
        reasons.append("NO_MULTIDAY_BREAKOUT_CONFIRMATION")
    elif pct >= 4:
        style = "EXTENDED_OR_BREAKOUT_WATCH"
        reasons.append("CHASE_RISK_CHECK_REQUIRED")
    else:
        reasons.append("NO_CLEAR_SETUP")

    rr_score = min(30, 15 * rr) if rr is not None else 0
    if rr is not None and rr < 1.5:
        reasons.append("RR_BELOW_1_5")
    if range_pct >= 8:
        reasons.append("WIDE_INTRADAY_RANGE")
    if strength >= 0.9 and pct >= 4:
        reasons.append("CLOSE_NEAR_HIGH_NOT_AUTOBUY")

    # Percentages are technical screening points only, not probability.
    points = round(rr_score + location_score + structure_score + liquidity_score, 2)
    eligible = (style == "PANIC_REVERSAL_WATCH" and rr is not None
                and rr >= 1.5 and range_pct < 10 and value >= 200_000_000)
    return {
        "symbol": row["symbol"], "name": row.get("name", ""),
        "style": style, "watch_eligible": eligible, "entry_confirmed": False,
        "technical_score_out_of_85": points,
        "fundamental_score": fundamental_score,
        "weights": WEIGHTS,
        "reference_close": p, "scenario_stop": stop,
        "scenario_target_prior_close": target, "scenario_rr": rr,
        "close_strength": strength, "range_pct": round(range_pct, 2),
        "reasons": reasons,
        "needs": ["LIVE_QUOTE", "LIVE_VWAP", "VOLUME_CONFIRMATION",
                  "MULTIDAY_HISTORY", "FUNDAMENTAL_VERIFICATION"],
        "disclaimer": "EOD-only hypothetical setup, not an executable buy signal.",
    }


def build_risk_radar(rows, limit=30):
    analyzed = [v for row in rows if (v := evaluate(row)) is not None]
    panic = sorted(
        (r for r in analyzed if r["watch_eligible"]),
        key=lambda r: (r["technical_score_out_of_85"], r["scenario_rr"]),
        reverse=True,
    )
    early = sorted(
        (r for r in analyzed if r["style"] == "EARLY_STRENGTH_WATCH"),
        key=lambda r: r["technical_score_out_of_85"], reverse=True,
    )
    chase = sorted(
        (r for r in analyzed if r["style"] == "EXTENDED_OR_BREAKOUT_WATCH"),
        key=lambda r: r["technical_score_out_of_85"], reverse=True,
    )
    return {
        "model": "risk_first_eod_v2",
        "data_status": "EOD_WATCH_ONLY_NOT_ACTIONABLE",
        "risk_first_count": len(panic),
        "early_strength_count": len(early),
        "chase_risk_count": len(chase),
        "top_risk_first": panic[:limit],
        "top_early_strength": early[:limit],
        "top_chase_risk": chase[:limit],
        "scoring_note": "Technical-only /85, fundamental /15 UNKNOWN; no live entry confirmed.",
    }
