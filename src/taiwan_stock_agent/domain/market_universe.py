from __future__ import annotations


def score_hot_universe(row: dict) -> tuple[float, list[str]]:
    """Broad market pre-score.

    This is intentionally permissive: it decides who gets to enter the deeper
    scan, not who is a buy. Hybrid/Practical layers remain the final judge.
    """
    price = float(row.get("price") or 0.0)
    change = float(row.get("change_pct") or 0.0)
    value = float(row.get("value") or 0.0)
    volume = float(row.get("volume") or 0.0)
    close_strength = float(row.get("close_strength") or 0.0)
    high = float(row.get("high") or 0.0)
    low = float(row.get("low") or 0.0)

    if price <= 0 or value < 30_000_000 or volume < 300:
        return 0.0, ["UNIVERSE_TOO_ILLIQUID"]

    score = 0.0
    flags: list[str] = []

    # Liquidity / attention
    if value >= 2_000_000_000:
        score += 30
        flags.append("VALUE_TOP")
    elif value >= 1_000_000_000:
        score += 25
        flags.append("VALUE_PRIME")
    elif value >= 500_000_000:
        score += 20
    elif value >= 200_000_000:
        score += 14
    elif value >= 100_000_000:
        score += 9
    else:
        score += 4

    # Movement: allow strong/weak reversals into the universe. Do not pre-delete.
    if 1.0 <= change <= 6.5:
        score += 22
        flags.append("ACTIVE_UP")
    elif 6.5 < change <= 9.8:
        score += 15
        flags.append("HOT_UP")
    elif 0 <= change < 1.0:
        score += 8
    elif -3.0 <= change < 0:
        score += 5
        flags.append("RED_WATCH")
    elif change < -3.0:
        score -= 4
    elif change > 9.8:
        score -= 5
        flags.append("LIMIT_LIKE")

    # Closing quality is useful but no longer a hard gate.
    if close_strength >= 0.85:
        score += 18
        flags.append("CLOSE_PRIME")
    elif close_strength >= 0.65:
        score += 12
    elif close_strength >= 0.45:
        score += 6
    else:
        score -= 4

    day_range = ((high - low) / price * 100.0) if high > low and price > 0 else 0.0
    if 1.5 <= day_range <= 7.0:
        score += 8
    elif day_range > 10:
        score -= 5
        flags.append("WIDE_RANGE")

    return round(max(0.0, min(100.0, score)), 1), flags


def merge_universes(*universes: list[dict], limit: int = 120) -> list[dict]:
    """Merge market-wide and legacy candidate pools without duplicate tickers."""
    by_symbol: dict[str, dict] = {}

    for universe in universes:
        for row in universe or []:
            symbol = str(row.get("symbol") or "")
            if not symbol:
                continue
            current = by_symbol.get(symbol)
            incoming = dict(row)
            if current is None:
                by_symbol[symbol] = incoming
                continue

            # Preserve richer fields and the best broad-universe score.
            merged = {**current, **{k: v for k, v in incoming.items() if v not in (None, "", [])}}
            merged["universe_score"] = max(
                float(current.get("universe_score") or 0.0),
                float(incoming.get("universe_score") or 0.0),
            )
            sources = set(current.get("universe_sources") or [])
            sources.update(incoming.get("universe_sources") or [])
            if current.get("source"):
                sources.add(str(current["source"]))
            if incoming.get("source"):
                sources.add(str(incoming["source"]))
            merged["universe_sources"] = sorted(sources)
            by_symbol[symbol] = merged

    rows = list(by_symbol.values())
    rows.sort(
        key=lambda r: (
            float(r.get("universe_score") or r.get("pre_score") or 0.0),
            float(r.get("value") or 0.0),
        ),
        reverse=True,
    )
    return rows[:limit]
