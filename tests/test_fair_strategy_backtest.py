"""Offline test: honest same-panel, next-session fills and time split."""
import csv
import tempfile
import unittest
from pathlib import Path

from scripts.fair_strategy_backtest import read_panel, replay, signal_for


def bar(day, symbol, close, prev, move=None):
    change = (close / prev - 1) * 100
    if change < -1:
        low, high = close * .99, close * 1.00667
    else:
        low, high = close * .98, close * 1.01
    return {
        "date": day, "symbol": symbol, "open": close * 1.001,
        "high": max(high, close*1.001), "low": low,
        "close": close, "volume": 10_000_000,
        "trade_value": 1_000_000_000,
    }


def mock_panel():
    from datetime import date, timedelta
    dates = [(date(2026, 2, 2) + timedelta(days=i)).isoformat()
             for i in range(19)]
    panel = {}
    for symbol in ("1001", "1002"):
        price = 100
        for i, day in enumerate(dates):
            # Alternating down and rebound sessions (both strategies arise).
            nextprice = price * (.95 if (i + (symbol == "1002")) % 2 else 1.07)
            row = bar(day, symbol, nextprice, price)
            panel[(day, symbol)] = row
            price = nextprice
    return panel, dates


class ReplayTests(unittest.TestCase):
    def test_same_future_data_cannot_change_signal(self):
        panel, dates = mock_panel()
        d = dates[3]
        row, prev = panel[(d, "1001")], panel[(dates[2], "1001")]
        before = signal_for(row, prev)
        panel[(dates[4], "1001")]["close"] *= 1.2
        after = signal_for(row, prev)
        self.assertEqual(before, after)

    def test_replay_common_entry_date_and_no_forward_training(self):
        panel, dates = mock_panel()
        result = replay(panel, dates, minimum_symbols=2,
                        minimum_signal_dates=1, minimum_trades_per_style=1)
        self.assertGreater(result["trade_count"], 0)
        self.assertEqual(result["data_status"], "HISTORICAL_RESEARCH_ONLY")
        self.assertTrue(any(s["sufficient_matched_dates"]
                            for s in result["paired_same_date_comparisons"]))
        self.assertTrue(any(s["strategy"] == "EXTENDED_OR_BREAKOUT_WATCH"
                            and s["completed_trades"] > 0
                            for s in result["comparisons"]))

    def test_invalid_rows_duplicate_and_outlier_rejected(self):
        panel, dates = mock_panel()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "panel.csv"
            with path.open("w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["date", "symbol", "open", "high",
                                        "low", "close", "volume", "trade_value"])
                writer.writeheader()
                writer.writerow(panel[(dates[0], "1001")])
                writer.writerow(panel[(dates[0], "1001")])
            with self.assertRaisesRegex(ValueError, "DUPLICATE"):
                read_panel(path)
        broken = dict(panel)
        broken[(dates[0], "1001")] = dict(panel[(dates[0], "1001")], open=-10)
        with self.assertRaisesRegex(ValueError, "INSUFFICIENT_UNIVERSE_COVERAGE"):
            replay(broken, dates, minimum_symbols=3)


if __name__ == "__main__":
    unittest.main()
