"""Offline tests for cohort audit: no hindsight labels and date clustering."""
import unittest
from scripts.historical_cohort_audit import analyze, bucket, clean_rows


def r(date, symbol, pct, t5, t10, strength=.8):
    return {"signal_date": date, "ticker": symbol, "day_chg_pct": str(pct),
            "close_strength": str(strength), "t5_return_pct": str(t5),
            "t10_return_pct": str(t10)}


class CohortTests(unittest.TestCase):
    def test_disjoint_buckets(self):
        self.assertEqual([bucket(x) for x in (-1, 0, 3.99, 4, 6.99, 7)],
                         ["negative_day", "0_to_4_pct", "0_to_4_pct",
                          "4_to_7_pct", "4_to_7_pct", "7_plus_pct"])

    def test_single_day_many_stocks_not_independent(self):
        rows = [r("2026-02-09", str(2000+i), 8, 2, 3) for i in range(50)]
        cohort = analyze(rows)["cohorts"][-1]
        self.assertEqual(cohort["signal_count"], 50)
        self.assertEqual(cohort["signal_dates"], 1)
        self.assertFalse(cohort["t5"]["eligible_to_report"])

    def test_metrics_and_cost_not_claimed_executable(self):
        rows = [r(f"2026-02-{10+i:02d}", str(2000+i), 8, value, value*2)
                for i, value in enumerate((-10, 2, 6))]
        report = analyze(rows, minimum_rows=3, minimum_dates=3)
        out = report["cohorts"][-1]["t5"]
        self.assertAlmostEqual(out["mean_pct"], -0.6667, places=4)
        self.assertEqual(out["median_pct"], 2)
        self.assertEqual(out["p10_pct"], -10)
        self.assertEqual(out["positive_fraction"], .6667)
        self.assertEqual(report["decision"],
                         "EVIDENCE_NOT_SUFFICIENT_TO_REMOVE_BREAKOUT_STRATEGY")

    def test_unmatured_t10_does_not_enter_t5_sample(self):
        rows = [r(f"2026-02-{10+i:02d}", str(2000+i), 8, 2, 3) for i in range(3)]
        rows[0]["t10_return_pct"] = ""
        report = analyze(rows, minimum_rows=3, minimum_dates=3)
        self.assertEqual(report["cohorts"][-1]["t5"]["completed_samples"], 3)
        self.assertEqual(report["cohorts"][-1]["t10"]["completed_samples"], 2)
        self.assertFalse(report["cohorts"][-1]["t10"]["eligible_to_report"])

    def test_duplicate_and_nonfinite_rejected(self):
        x = r("2026-02-09", "2337", 8, 1, 2)
        with self.assertRaisesRegex(ValueError, "DUPLICATE"):
            clean_rows([x, x])
        x["t5_return_pct"] = "nan"
        with self.assertRaisesRegex(ValueError, "INVALID"):
            clean_rows([x])


if __name__ == "__main__":
    unittest.main()
