"""Offline research journal tests: idempotence and actual trading sessions."""
import unittest
from scripts.eod_signal_journal import advance


def day(d, price, symbol="1111"):
    rows = [{"symbol": str(i), "close": 50} for i in range(2000, 3600)]
    rows.append({"symbol": symbol, "close": price})
    return {
        "data_status": "OFFICIAL_EOD_WATCH_ONLY",
        "scan_date": d,
        "market_dates": {"TWSE": d, "TPEx": d},
        "all_scanned": rows,
        "risk_first_v2": {
            "top_risk_first": [{"symbol": symbol, "reference_close": price,
                                 "entry_confirmed": False}],
            "top_early_strength": [], "top_chase_risk": [],
        },
    }


class JournalTests(unittest.TestCase):
    def test_idempotent_and_session_based(self):
        j = advance({}, day("2026-11-13", 100))
        self.assertEqual(len(j["signals"]), 1)
        j = advance(j, day("2026-11-13", 100))
        self.assertEqual(len(j["signals"]), 1)
        j = advance(j, day("2026-11-16", 110))
        self.assertEqual(j["signals"][0]["forward_close_returns_pct"]["1"], 10)
        j = advance(j, day("2026-11-17", 105))
        self.assertEqual(j["signals"][0]["forward_close_returns_pct"]["2"], 5)

    def test_missing_history_and_stale_feed_fail(self):
        j = advance({}, day("2026-11-16", 100))
        with self.assertRaisesRegex(ValueError, "OUT_OF_ORDER"):
            advance(j, day("2026-11-13", 99))
        bad = day("2026-11-17", 90)
        bad["market_dates"]["TWSE"] = "2026-11-16"
        with self.assertRaisesRegex(ValueError, "MISMATCHED"):
            advance(j, bad)

    def test_watch_only_restriction(self):
        bad = day("2026-11-16", 90)
        bad["risk_first_v2"]["top_risk_first"][0]["entry_confirmed"] = True
        with self.assertRaisesRegex(ValueError, "ONLY_WATCH"):
            advance({}, bad)


if __name__ == "__main__":
    unittest.main()
