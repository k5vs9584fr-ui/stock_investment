from __future__ import annotations


def portfolio_exposure_guard(
    *,
    holding_weights: dict[str, float],
    symbol_sectors: dict[str, str],
    max_total_exposure: float = 0.90,
    max_sector_exposure: float = 0.50,
) -> dict:
    """Summarize current portfolio exposure and remaining capacity."""
    total = 0.0
    sectors: dict[str, float] = {}

    for symbol, raw_weight in (holding_weights or {}).items():
        weight = max(0.0, min(1.0, float(raw_weight)))
        total += weight
        sector = str(symbol_sectors.get(str(symbol), "UNKNOWN"))
        sectors[sector] = sectors.get(sector, 0.0) + weight

    total = min(1.0, total)
    return {
        "total_exposure": round(total, 4),
        "remaining_total_capacity": round(max(0.0, max_total_exposure - total), 4),
        "sector_exposure": {k: round(v, 4) for k, v in sectors.items()},
        "max_total_exposure": round(max_total_exposure, 4),
        "max_sector_exposure": round(max_sector_exposure, 4),
    }


def rotation_exposure_capacity(
    *,
    held_symbol: str,
    challenger_symbol: str,
    sell_weight: float,
    holding_weights: dict[str, float],
    symbol_sectors: dict[str, str],
    max_total_exposure: float = 0.90,
    max_sector_exposure: float = 0.50,
) -> dict:
    """Return max buy capacity after accounting for sale proceeds and sector limits."""
    guard = portfolio_exposure_guard(
        holding_weights=holding_weights,
        symbol_sectors=symbol_sectors,
        max_total_exposure=max_total_exposure,
        max_sector_exposure=max_sector_exposure,
    )

    held_weight = max(0.0, float(holding_weights.get(str(held_symbol), 0.0)))
    challenger_weight = max(0.0, float(holding_weights.get(str(challenger_symbol), 0.0)))
    sell_weight = max(0.0, min(held_weight, float(sell_weight)))

    total_after_sale = max(0.0, guard["total_exposure"] - sell_weight)
    total_capacity = max(0.0, max_total_exposure - total_after_sale)

    challenger_sector = str(symbol_sectors.get(str(challenger_symbol), "UNKNOWN"))
    held_sector = str(symbol_sectors.get(str(held_symbol), "UNKNOWN"))
    sector_now = float(guard["sector_exposure"].get(challenger_sector, 0.0))
    if challenger_sector == held_sector:
        sector_after_sale = max(0.0, sector_now - sell_weight)
    else:
        sector_after_sale = sector_now
    sector_capacity = max(0.0, max_sector_exposure - sector_after_sale)

    capacity = min(total_capacity, sector_capacity)
    return {
        "challenger_symbol": challenger_symbol,
        "challenger_sector": challenger_sector,
        "challenger_existing_weight": round(challenger_weight, 4),
        "total_capacity": round(total_capacity, 4),
        "sector_capacity": round(sector_capacity, 4),
        "max_buy_capacity": round(capacity, 4),
        "total_after_sale": round(total_after_sale, 4),
        "sector_after_sale": round(sector_after_sale, 4),
    }
