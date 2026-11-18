# Fair same-panel strategy replay (V3)

This engine **does not validate new low-entry alpha until actual history is loaded**. Historical `data/surge_backtest.csv` is a SURGE-selected sample and is NOT eligible input because it lacks the underlying full-market daily OHLCV panel.

## Input

Supply a real historical CSV with columns:

```csv
date,symbol,open,high,low,close,volume,trade_value
2026-10-01,2337,50.0,51.0,49.0,50.2,1000000,50200000
```

The example shows *schema only*, not a real quote. Need source metadata, consistent adjustments and an intact market/universe history to interpret results. Source should be archived and independently checked. **Do not generate historical rows from synthetic fixtures or unrelated score CSVs.**

```bash
python -m unittest discover -s tests -p 'test_fair_strategy_backtest.py' -v
python scripts/fair_strategy_backtest.py --panel PATH_TO_VALIDATED_HISTORY.csv --output data/fair_backtest_report.json --min-symbols 100 --min-dates 10 --min-trades 30
```

Default rules:

- Single unified daily panel, complete-date coverage gate of 100 securities.
- Generate each signal from its own current OHLCV and previous session close only. Never use later prices or after-close revisions for the signal.
- Explicitly classify V2 panic-reversal eligible setups and extended/breakout setups. Other setups remain watch-only; the engine does not use future outcomes in selection.
- Both strategies get the same entry rule: next session **open**. Simulated exits: after **one night** (D+2 close) and **two nights** (D+3 close) following a D+1 open entry. Never use entry-day close as an overnight exit. Buying at next open is an idealized fill, not guaranteed.
- Use one common calendar of dates from the supplied data; missing ticker next-open or exit prices skip that observation and are counted.
- Gross = exit close / entry open - 1; illustrative roundtrip cost defaults to **0.585%** (two full-rate 0.1425% commissions plus 0.3% sell tax). Brokerage discounts, minimum fees, day-trade tax, and execution frictions may differ. This is a simplified cost scenario, not a broker settlement.
- Record path min low vs next open. **Do not simulate stop fills or intraday sequencing from daily OHLCV**, particularly in gaps.
- Date-ordered train/test split. Additional paired comparison uses ONLY signal dates with both strategies, equal-weighting each style within date before differencing. If fewer than ten matched days it withholds the comparison. No thresholds tuned with held-out dates. Check missing, universe coverage, and report data sufficiency per strategy and holding horizon.

## Obtain history (optional manual GitHub Actions run)

Use the **Historical Fair Strategy Research** workflow (Actions → Run workflow), which uses the *explicit TWSE/TPEx market field* in current stock universe and reproducible symbol-hash sampling. It downloads raw unadjusted daily bars from yfinance (not an official full-market archive), exports a normalized panel, then runs this replay. Default sample 250 stocks; at least 100 symbols must be present for the replay to proceed. The provider can fail or limit requests; the job will report the issue rather than fabricate results. Output metadata explicitly states that trade value is **close × volume proxy** and lists missing symbols. Results go to a GitHub Actions artifact; the workflow does not commit large vendor datasets to the repository. This is a *biased research sample* due to current-universe survivorship and price-adjustment limitations, not full-market evidence.

## Interpretation caveats

This is an engineering-ready **replay harness**, not a fair empirical conclusion until quality historical data spanning many sessions and meaningful market regimes is provided. Same-date observations are dependent; delistings, survivorship, adjusted-vs-raw events and price limits require separate scrutiny. A future robust version should add dated constituent membership, transaction-level fillability and at least several independent market regimes.

The existing Fugle HTTP 403 affects intraday functionality; the replay engine does not rely on that provider.
