from __future__ import annotations

from collections import defaultdict

from taiwan_stock_agent.domain.explosive_lifecycle import classify_explosive_lifecycle


_HORIZONS = (1, 3, 5)


def _fnum(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _resolved(row: dict, horizon: int) -> bool:
    raw = row.get(f"resolved_t{horizon}")
    if raw is None:
        return row.get(f"t{horizon}_return") is not None
    return str(raw).lower() == "true" or raw is True


def _phase(row: dict) -> str:
    phase = str(row.get("explosive_phase") or "").strip()
    if phase:
        return phase
    return str(classify_explosive_lifecycle(row).get("phase") or "UNKNOWN")


def summarize_explosive_history(rows: list[dict]) -> dict:
    """Aggregate T+1/T+3/T+5 outcomes by explosive lifecycle phase."""
    buckets: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        buckets[_phase(row)].append(row)

    out: dict[str, dict] = {}
    for phase, phase_rows in buckets.items():
        stats: dict[str, object] = {"signals": len(phase_rows)}
        for horizon in _HORIZONS:
            vals = [
                _fnum(r.get(f"t{horizon}_return"))
                for r in phase_rows
                if _resolved(r, horizon)
            ]
            vals = [v for v in vals if v is not None]
            n = len(vals)
            stats[f"t{horizon}_n"] = n
            stats[f"t{horizon}_avg"] = round(sum(vals) / n, 3) if n else None
            stats[f"t{horizon}_win_rate"] = (
                round(sum(v > 0 for v in vals) / n * 100.0, 1) if n else None
            )
            stats[f"t{horizon}_big_win_rate"] = (
                round(sum(v >= 3.0 for v in vals) / n * 100.0, 1) if n else None
            )
        out[phase] = stats
    return out


def explosive_history_adjustment(
    row: dict,
    history_by_phase: dict[str, dict] | None,
    *,
    min_samples: int = 8,
) -> tuple[float, list[str]]:
    """Return a conservative ranking adjustment from historical phase outcomes.

    T+3 is emphasized because the target style is short, explosive continuation.
    Small samples are ignored. Large-win rate matters more than plain >0 win rate.
    """
    phase = _phase(row)
    stats = (history_by_phase or {}).get(phase) or {}
    n = int(stats.get("t3_n") or 0)
    if n < min_samples:
        return 0.0, ["EXPLOSIVE_HISTORY_INSUFFICIENT"] if n else []

    win = _fnum(stats.get("t3_win_rate"))
    big = _fnum(stats.get("t3_big_win_rate"))
    avg = _fnum(stats.get("t3_avg"))
    if win is None or big is None or avg is None:
        return 0.0, []

    # Shrink small samples toward neutral until ~30 observations.
    reliability = min(1.0, n / 30.0)
    raw = 0.0
    raw += (win - 50.0) * 0.10
    raw += (big - 25.0) * 0.08
    raw += avg * 0.8
    adjustment = max(-8.0, min(8.0, raw * reliability))

    flags: list[str] = []
    if adjustment >= 3.0:
        flags.append("EXPLOSIVE_HISTORY_STRONG")
    elif adjustment <= -3.0:
        flags.append("EXPLOSIVE_HISTORY_WEAK")

    return round(adjustment, 2), flags
