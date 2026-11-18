"""Tests that incomplete historical labels do not generate performance claims."""
import unittest
from scripts.eod_journal_report import summarize


class ReportTests(unittest.TestCase):
    def test_not_enough_samples_are_suppressed(self):
        journal = {"last_date": "2026-11-18", "signals": [
            {"date": "2026-11-17", "style": "PANIC_REVERSAL_WATCH",
             "forward_close_returns_pct": {"1": 1.0}},
        ]}
        result = summarize(journal)
        self.assertFalse(result["groups"][0]["sufficient_sample"])
        self.assertNotIn("positive_close_fraction", result["groups"][0])

    def test_many_tickers_on_one_day_are_not_independent_history(self):
        journal = {"signals": [
            {"date": "2026-11-17", "style": "EARLY_STRENGTH_WATCH",
             "forward_close_returns_pct": {"1": 2.0}} for _ in range(45)
        ]}
        result = summarize(journal)
        self.assertEqual(result["groups"][0]["completed_samples"], 45)
        self.assertEqual(result["groups"][0]["independent_signal_dates"], 1)
        self.assertFalse(result["groups"][0]["sufficient_sample"])
        self.assertNotIn("positive_close_fraction", result["groups"][0])

    def test_matured_only_and_sample_gate(self):
        journal = {"signals": [
            {"date": f"2026-11-{10+i:02d}", "style": "EARLY_STRENGTH_WATCH",
             "forward_close_returns_pct": {"1": value, "2": None}}
            for i, value in enumerate((1.0, -1.0, 2.0))
        ]}
        result = summarize(journal, min_sample=3, min_dates=3)
        self.assertEqual(len(result["groups"]), 1)
        self.assertEqual(result["groups"][0]["positive_close_fraction"], 0.6667)
        self.assertEqual(result["groups"][0]["mean_close_return_pct"], 0.667)


if __name__ == "__main__":
    unittest.main()
