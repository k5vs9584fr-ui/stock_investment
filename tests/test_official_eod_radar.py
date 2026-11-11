"""Offline tests for official full-market end-of-day radar."""
import sys
import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import official_eod_radar as radar


class OfficialEODTests(unittest.TestCase):
    def test_expected_date_preopen(self):
        moment = datetime(2026, 11, 12, 7, 45, tzinfo=ZoneInfo("Asia/Taipei"))
        self.assertEqual(radar.expected_market_date(moment), date(2026, 11, 11))
        monday = datetime(2026, 11, 16, 7, 45, tzinfo=ZoneInfo("Asia/Taipei"))
        self.assertEqual(radar.expected_market_date(monday), date(2026, 11, 13))

    def test_roc_date_and_quote_fields(self):
        self.assertEqual(radar.roc_date("1151111"), date(2026, 11, 11))
        row = dict(Date="1151111", Code="2337", Name="旺宏",
                   ClosingPrice="110", Change="+10", HighestPrice="110",
                   LowestPrice="100", TradeValue="1,250,000,000",
                   TradeVolume="10,000,000")
        r = radar.parse_row(row, "TWSE")
        self.assertEqual(r["change_pct"], 10.0)
        self.assertEqual(r["close_strength"], 1.0)

    def test_tpex_mapping(self):
        row = dict(Date="1151111", SecuritiesCompanyCode="5425", CompanyName="台半",
                   Close="105", Change="+5", High="106", Low="100",
                   TransactionAmount="450,000,000", TradingShares="4,500,000")
        r = radar.parse_row(row, "TPEx")
        self.assertEqual(r["change_pct"], 5.0)
        self.assertEqual(r["symbol"], "5425")

    def test_old_daily_quote_rejected(self):
        rows = [{"Date": "1151110", "Code": "2337", "Name": "旺宏",
                 "ClosingPrice": "110", "Change": "+10",
                 "TradeValue": "1000000000", "TradeVolume": "10000000"}]
        with self.assertRaisesRegex(RuntimeError, "STALE_EOD_MARKET_DATE"):
            radar.build({"TWSE": rows}, {"2337"}, date(2026, 11, 11))

    def test_undefined_change_not_faked(self):
        r = radar.parse_row(dict(Code="2337", Name="旺宏", ClosingPrice="100",
                                 Change="--", TradeValue="100000000",
                                 TradeVolume="1000000"), "TWSE")
        self.assertIsNone(r)


if __name__ == "__main__":
    unittest.main()
