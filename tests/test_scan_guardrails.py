"""Offline guardrails for scanner, API failures and independent momentum radar."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

os.environ.setdefault("FUGLE_API_KEY", "test-placeholder")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import realtime_scan
import daytrade_scan


class ScanGuardrailTests(unittest.TestCase):
    def test_unauthorized_is_fail_fast(self):
        err = HTTPError("https://api.fugle.tw/test", 401, "Unauthorized", {}, None)
        with patch.object(realtime_scan.urllib.request, "urlopen", side_effect=err) as fetch:
            with patch.object(realtime_scan.time, "sleep") as sleep:
                with self.assertRaisesRegex(RuntimeError, "MARKET_DATA_AUTH_FAILED"):
                    realtime_scan.get_bytes("https://api.fugle.tw/test", retries=4)
        self.assertEqual(fetch.call_count, 1)
        sleep.assert_not_called()

    def test_missing_snapshot_writes_non_actionable_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "results.json"
            with patch.object(daytrade_scan, "OUT", output), patch.object(
                daytrade_scan, "snapshot_candidates", side_effect=RuntimeError("MARKET_DATA_AUTH_FAILED")
            ):
                with self.assertRaisesRegex(RuntimeError, "no validated live snapshot"):
                    daytrade_scan.main()
            state = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(state["data_status"], "ERROR_NO_LIVE_MARKET_DATA")
            self.assertEqual(state["strong_count"], 0)
            self.assertEqual(state["stocks"], [])
            self.assertEqual(state["early_momentum_watch"], [])

    def test_high_momentum_is_watched_without_auto_buy_and_excludes_2344(self):
        def stock(symbol):
            return {
                "symbol": symbol, "name": symbol, "market": "TSE",
                "price": 100.0, "change_pct": 9.8, "volume": 100000,
                "value": 900000000, "close_strength": 0.95, "pre_score": 80.0,
            }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "results.json"
            with patch.object(daytrade_scan, "OUT", output), patch.object(
                daytrade_scan, "snapshot_candidates", return_value=[stock("2337"), stock("2344")]
            ), patch.object(daytrade_scan, "get_quote", return_value={}), patch.object(
                daytrade_scan, "score_stock", return_value=None
            ), patch.object(daytrade_scan, "get_ticker", return_value={}), patch.object(
                daytrade_scan, "get_5m", return_value=[]
            ), patch.object(daytrade_scan, "score_daytrade", return_value=(0, "5分K資料不足", [], {})
            ), patch.object(daytrade_scan.time, "sleep", return_value=None):
                daytrade_scan.main()
            state = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(state["data_status"], "LIVE_CONFIRMED")
            self.assertEqual([row["symbol"] for row in state["early_momentum_watch"]], ["2337"])
            self.assertEqual([row["symbol"] for row in state["stocks"]], ["2337"])
            self.assertEqual(state["strong_count"], 0)
            self.assertEqual(state["early_momentum_watch"][0]["phase"], "MOMENTUM_WATCH_ONLY")


if __name__ == "__main__":
    unittest.main()
