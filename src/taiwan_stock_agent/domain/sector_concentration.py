from __future__ import annotations


def apply_sector_concentration(rows: list[dict], max_sector_weight: float = 0.50) -> list[dict]:
    """Cap aggregate Top3 allocation to one industry/sector.

    Uses industry_code first and industry as fallback. Excess allocation is not
    automatically redistributed; leaving cash is safer than forcing exposure.
    """
    used: dict[str, float] = {}
    out: list[dict] = []

    for row in rows:
        r = dict(row)
        sector = str(r.get("industry_code") or r.get("industry") or "UNKNOWN")
        raw = float(r.get("allocation_weight") or 0.0)
        available = max(0.0, max_sector_weight - used.get(sector, 0.0))
        adjusted = min(raw, available)
        used[sector] = used.get(sector, 0.0) + adjusted

        r["sector_key"] = sector
        r["allocation_weight_sector_capped"] = round(adjusted, 4)
        r["sector_cap_applied"] = adjusted + 1e-9 < raw
        out.append(r)

    return out
