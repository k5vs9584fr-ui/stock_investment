"""Network-free ingestion checks: explicit listing venue and unbiased selection."""
import unittest
from scripts.fetch_replay_history import eligible_universe, stable_sample


class HistoryIngestTests(unittest.TestCase):
    def test_exchange_suffix_not_inferred_from_ticker(self):
        items = {"stocks": [
            {"symbol": "3333", "market": "TPEx"},
            {"symbol": "8888", "market": "TWSE"},
            {"symbol": "2344", "market": "TWSE"},
            {"symbol": "0000", "market": "UNKNOWN"},
        ]}
        self.assertEqual(eligible_universe(items),
                         {"3333": "TWO", "8888": "TW"})

    def test_sampling_deterministic_and_not_price_sorted(self):
        universe = {str(i): "TW" for i in range(1000, 1200)}
        a = stable_sample(universe, 20)
        b = stable_sample(dict(reversed(list(universe.items()))), 20)
        self.assertEqual(a, b)
        self.assertEqual(len(a), 20)
        self.assertEqual(len(set(a)), 20)

    def test_zero_sample_rejected(self):
        with self.assertRaisesRegex(ValueError, "POSITIVE"):
            stable_sample({"2337": "TW"}, 0)


if __name__ == "__main__":
    unittest.main()
