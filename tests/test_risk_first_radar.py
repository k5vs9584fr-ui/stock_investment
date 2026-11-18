"""No-network validation for risk-first EOD candidate selection."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from risk_first_radar import build_risk_radar, evaluate


def sample(symbol="1234", close=90, high=100, low=80,
           change_pct=-5, strength=.5, value=500_000_000):
    return dict(symbol=symbol, name="test", close=close, high=high,
                low=low, change_pct=change_pct, close_strength=strength,
                value=value)


class RiskFirstTests(unittest.TestCase):
    def test_reversal_watch_requires_realistic_rr(self):
        row = sample(close=94, low=80, strength=.7)
        d = evaluate(row)
        self.assertEqual(d["style"], "PANIC_REVERSAL_WATCH")
        self.assertIsNotNone(d["scenario_rr"])
        self.assertFalse(d["entry_confirmed"])
        self.assertIsNone(d["fundamental_score"])
        self.assertLessEqual(d["technical_score_out_of_85"], 85)

    def test_breakout_never_auto_buy(self):
        d = evaluate(sample(close=100, high=100, low=90,
                            change_pct=9.5, strength=1))
        self.assertEqual(d["style"], "EXTENDED_OR_BREAKOUT_WATCH")
        self.assertFalse(d["watch_eligible"])
        self.assertIsNone(d["scenario_rr"])
        self.assertIn("CHASE_RISK_CHECK_REQUIRED", d["reasons"])

    def test_invalid_and_excluded(self):
        self.assertIsNone(evaluate(sample(symbol="2344")))
        self.assertIsNone(evaluate(sample(high=80, low=90)))
        self.assertIsNone(evaluate(sample(close=float("nan"))))

    def test_sorted_lists_do_not_promote_breakouts(self):
        reversal = sample(symbol="1234", close=96, high=110, low=90,
                          change_pct=-6, strength=.65)
        breakout = sample(symbol="5678", close=105, high=105, low=100,
                          change_pct=7, strength=1)
        results = build_risk_radar([reversal, breakout])
        self.assertEqual(results["data_status"], "EOD_WATCH_ONLY_NOT_ACTIONABLE")
        self.assertEqual(results["top_chase_risk"][0]["symbol"], "5678")
        self.assertEqual(results["top_risk_first"][0]["symbol"], "1234")

    def test_weak_rr_excluded_from_priority_list(self):
        row = sample(close=94, high=100, low=90, change_pct=-1, strength=.6)
        d = evaluate(row)
        self.assertLess(d["scenario_rr"], 1.5)
        self.assertFalse(d["watch_eligible"])


if __name__ == "__main__":
    unittest.main()
