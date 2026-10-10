from __future__ import annotations


_STATUS_SCORE = {
    "DROPPED": 0,
    "DOWNGRADE": 1,
    "HOLD": 2,
    "NEW": 3,
    "UPGRADE": 4,
}


def _candidate_map(snapshot: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for idx, row in enumerate(snapshot.get("top_candidates") or [], 1):
        symbol = str(row.get("symbol") or "")
        if not symbol:
            continue
        rank = row.get("rank")
        try:
            rank_num = int(rank) if rank is not None else idx
        except (TypeError, ValueError):
            rank_num = idx
        out[symbol] = {
            "symbol": symbol,
            "name": row.get("name") or symbol,
            "rank": rank_num,
            "opening_score": float(row.get("opening_score") or 0.0),
            "explosive_phase": row.get("explosive_phase"),
            "entry_mode": row.get("entry_mode"),
        }
    return out


def compare_snapshots(previous: dict, current: dict) -> list[dict]:
    """Compare candidate progression between two intraday snapshots."""
    prev = _candidate_map(previous)
    cur = _candidate_map(current)
    symbols = sorted(set(prev) | set(cur))
    rows: list[dict] = []

    for symbol in symbols:
        p = prev.get(symbol)
        c = cur.get(symbol)

        if p is None and c is not None:
            status = "NEW"
            rank_change = None
        elif p is not None and c is None:
            status = "DROPPED"
            rank_change = None
        else:
            assert p is not None and c is not None
            rank_change = int(p["rank"]) - int(c["rank"])
            score_change = float(c["opening_score"]) - float(p["opening_score"])
            if rank_change > 0 or score_change >= 4.0:
                status = "UPGRADE"
            elif rank_change < 0 or score_change <= -4.0:
                status = "DOWNGRADE"
            else:
                status = "HOLD"

        rows.append({
            "symbol": symbol,
            "name": (c or p or {}).get("name") or symbol,
            "status": status,
            "previous_rank": p.get("rank") if p else None,
            "current_rank": c.get("rank") if c else None,
            "rank_change": rank_change,
            "previous_opening_score": p.get("opening_score") if p else None,
            "current_opening_score": c.get("opening_score") if c else None,
            "previous_phase": p.get("explosive_phase") if p else None,
            "current_phase": c.get("explosive_phase") if c else None,
            "current_entry_mode": c.get("entry_mode") if c else None,
        })

    rows.sort(
        key=lambda x: (
            _STATUS_SCORE.get(str(x.get("status")), 0),
            -(int(x.get("current_rank") or 999)),
        ),
        reverse=True,
    )
    return rows


def build_opening_progression(snapshots: list[tuple[int, dict]]) -> dict:
    """Build 5→15→30 minute progression and identify persistent leaders/failures."""
    snapshots = sorted(snapshots, key=lambda x: x[0])
    comparisons: list[dict] = []

    for i in range(1, len(snapshots)):
        prev_phase, prev = snapshots[i - 1]
        cur_phase, cur = snapshots[i]
        comparisons.append({
            "from_phase": prev_phase,
            "to_phase": cur_phase,
            "changes": compare_snapshots(prev, cur),
        })

    history: dict[str, list[str]] = {}
    for comp in comparisons:
        for row in comp["changes"]:
            history.setdefault(str(row["symbol"]), []).append(str(row["status"]))

    persistent_leaders = []
    fake_breakouts = []
    for symbol, statuses in history.items():
        if statuses and all(s in {"HOLD", "UPGRADE", "NEW"} for s in statuses) and "DROPPED" not in statuses:
            persistent_leaders.append(symbol)
        if "DROPPED" in statuses or ("UPGRADE" in statuses and "DOWNGRADE" in statuses):
            fake_breakouts.append(symbol)

    return {
        "phases": [phase for phase, _ in snapshots],
        "comparisons": comparisons,
        "persistent_leaders": sorted(set(persistent_leaders)),
        "fake_breakouts": sorted(set(fake_breakouts)),
    }
