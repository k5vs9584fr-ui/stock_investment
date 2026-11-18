"""Append reproducible EOD watchlists and evaluate close-to-close forward returns.

This is a signal *research* journal, not an executed trade backtest.
No simulated fill, stops, fees, or win-rate claims based on intraday prices.
Trading-session progression comes from successive official reports (not calendar days).
"""
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "official_eod_radar.json"
DEST = ROOT / "data" / "eod_signal_journal.json"
HORIZONS = (1, 2, 5)


def advance(journal, daily):
    if daily.get("data_status") != "OFFICIAL_EOD_WATCH_ONLY":
        raise ValueError("STALE_OR_NON_OFFICIAL_EOD")
    date_key = date.fromisoformat(daily["scan_date"]).isoformat()
    sources = daily.get("market_dates") or {}
    if sources.get("TWSE") != date_key or sources.get("TPEx") != date_key:
        raise ValueError("MISMATCHED_MARKET_DATES")
    records = daily.get("all_scanned") or []
    if len(records) < 1500 or "risk_first_v2" not in daily:
        raise ValueError("INCOMPLETE_SCAN_OR_NO_V2_RANKING")
    price_map = {str(x["symbol"]): float(x["close"]) for x in records
                 if x.get("symbol") and float(x.get("close") or 0) > 0}
    if len(price_map) < 1500:
        raise ValueError("INCOMPLETE_PRICE_MAP")
    sessions = journal.setdefault("sessions", [])
    signals = journal.setdefault("signals", [])
    if sessions and date_key < sessions[-1]:
        raise ValueError("OUT_OF_ORDER_MARKET_DATE")
    if date_key in sessions:
        return journal  # Retry/idempotency: no fabricated extra sessions.
    sessions.append(date_key)
    index = len(sessions) - 1
    for item in signals:
        age = index - item["session_index"]
        if age in HORIZONS and str(age) not in item["forward_close_returns_pct"]:
            current = price_map.get(item["symbol"])
            item["forward_close_returns_pct"][str(age)] = (
                round((current / item["reference_close"] - 1) * 100, 4)
                if current is not None else None
            )
    radar = daily["risk_first_v2"]
    mapping = (
        ("top_risk_first", "PANIC_REVERSAL_WATCH"),
        ("top_early_strength", "EARLY_STRENGTH_WATCH"),
        ("top_chase_risk", "EXTENDED_OR_BREAKOUT_WATCH"),
    )
    for field, style in mapping:
        for rank, row in enumerate(radar.get(field, []), 1):
            if row.get("entry_confirmed") is not False:
                raise ValueError("ONLY_WATCH_SIGNALS_ALLOWED")
            symbol = str(row["symbol"])
            reference = float(row["reference_close"])
            if symbol not in price_map or reference <= 0:
                continue
            if abs(reference - price_map[symbol]) > max(0.01, 0.0001 * reference):
                raise ValueError("SIGNAL_REFERENCE_PRICE_MISMATCH")
            signals.append({
                "date": date_key, "session_index": index, "symbol": symbol,
                "style": style, "rank": rank, "reference_close": reference,
                "forward_close_returns_pct": {},
            })
    journal["schema_version"] = 1
    journal["data_source"] = "TWSE_TPEX_OFFICIAL_EOD"
    journal["metric_note"] = (
        "Future close vs signal-day close, NOT achievable execution return. "
        "No entry fill, fees, slippage, or intraday stop simulated."
    )
    journal["last_date"] = date_key
    return journal


def main():
    daily = json.loads(SOURCE.read_text(encoding="utf-8"))
    journal = json.loads(DEST.read_text(encoding="utf-8")) if DEST.exists() else {}
    journal = advance(journal, daily)
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps(journal, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Journal sessions:", len(journal["sessions"]),
          "signals:", len(journal["signals"]), "as of", journal["last_date"])


if __name__ == "__main__":
    main()
