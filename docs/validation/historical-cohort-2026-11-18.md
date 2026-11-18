# Historical SURGE cohort audit — 2026-11-18

Data: `data/surge_backtest.csv` (1,076 SURGE-selected signals; 53 signal dates; 2026-02-09 to 2026-05-07). Script: `scripts/historical_cohort_audit.py`.

## T+5 signal-close → future-close; only matured, nonmissing outcomes

| Signal-day return | Matured N | Matured signal dates | Mean | Median | Positive fraction | 10th percentile | Worst |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0%–<4% | 232 | 48 | +0.60% | -0.68% | 44.83% | -9.80% | -18.44% |
| 4%–<7% | 277 | 48 | +0.63% | -0.38% | 46.93% | -9.71% | -20.56% |
| >=7% | 438 | 48 | +2.77% | -0.28% | 49.09% | -11.95% | -22.62% |

These are **gross close-to-close research observations**, NOT executions. Every cohort's T+5 median is negative. The >=7% mean is higher, while downside tail and worst observation are also worse. Do not equate these means with next-day realized returns. A flat hypothetical 0.6 percentage-point roundtrip cost would reduce respective group means to approximately -0.00%, +0.03%, and +2.17%, but this is not a fill/tax simulation.

## T+10 matured observations

| Signal-day return | Matured N | Mean | Median | Positive fraction | 10th percentile |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0%–<4% | 217 | +0.93% | -1.14% | 40.09% | -11.70% |
| 4%–<7% | 259 | +1.05% | -1.82% | 42.86% | -11.41% |
| >=7% | 405 | +4.29% | +0.70% | 52.35% | -12.62% |

## Constraints

- SURGE-triggered subset only; cannot infer what all TWSE/TPEx stocks did.
- Five negative-day signals across three dates are below the minimum sample. No panic-bounce comparison can be made from this dataset.
- Rows missing T+5/T+10 maturity are **excluded only from that horizon**, never filled with zero. Earlier naive comparisons using zero-filled outcomes are superseded by this audit.
- Underlying historical signal selection and existing CSV label generation have **not** been independently reproduced; source-selection bias and data quality remain possible.
- Same-date picks move together; equal-ticker-weighted samples are not independent days. A per-date average is also in the JSON report to check concentration.
- Excludes executable entry open, limit fills, slippage, tick rounding, real fee/tax schedules, gap-through stops, market benchmark, and out-of-sample confirmation.
- No claim that the V2 risk-first panic model improves real-world performance: there is no complete historical daily OHLCV history in this CSV for that style.

## Action

Do not delete breakout style merely because chasing can be risky. Retain it as conditional; collect a separate all-market historical panel with real OHLCV and build a time-split, transaction-cost-adjusted test of risk-first and breakout strategies **on the same dates**.
