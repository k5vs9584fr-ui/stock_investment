# True overnight replay pilot — 2026-11-18

## Provenance

- GitHub run: https://github.com/k5vs9584fr-ui/stock_investment/actions/runs/44229757985
- Research data provider: yfinance unadjusted daily OHLC, 2026-05-01 through 2026-11-13.
- 160 symbols deterministically sampled from today's TWSE/TPEx stock universe; 159 with valid data; 20,927 OHLCV rows across 133 market dates.
- **Non-official turnover proxy**: close × shares. Includes survivorship, market-data, price adjustment and selection limitations.
- Signal D close using D and D-1 bars only; **entry at D+1 OPEN**, exits at D+2 CLOSE (one overnight) or D+3 CLOSE (two overnights). Never exit on entry day.
- Full-rate illustrative 0.585% commission/tax roundtrip deduction, no fill/limit execution/slippage simulation. All outcomes are hypothetical.
- Chronological 60/40 train/test with purged overlap.

## Held-out test cohort — breakout/extended (daily move >=4%)

| Metric | One overnight | Two overnights |
| --- | ---: | ---: |
| Valid hypothetical trades | 471 | 469 |
| Independent signal dates | 52 | 52 |
| Mean net return | -0.7709% | -1.0733% |
| Median net return | -1.4280% | -1.9803% |
| Net positive fraction | 38.43% | 36.03% |
| 10th percentile net return | -7.5759% | -8.8042% |
| Worst hypothetical trade | -20.9147% | -28.7901% |
| Mean of equal-date-weighted net returns | -0.9482% | -1.2037% |

Train breakout samples: 1032 (one night), 1030 (two); mean net -0.7654% and -0.7876%, respectively.

## Low-buy/panic watch samples

Train: 8 samples on 2 signal days. Held-out test: 4 samples on 2 signal days. Both fail the pre-specified 30-trade / 10-date minimum; **NO valid low-buy efficacy claim and no fair paired-strategy edge comparison**.

## Corrections and limitations

The earlier test run https://github.com/k5vs9584fr-ui/stock_investment/actions/runs/44229323810 computed **same-day next-open-to-close** for one hold and **one-overnight** for two holds. That output is now superseded for the user's overnight strategy. The corrected run has tests verifying entry and exit on distinct dates.

Historical records excluded missing price legs; no fabricated returns. The data do not include order-book fills, bid/ask/slippage, historic security eligibility, dividends or stock splits adjustments. It is a survivorship-biased **159-stock sample**, not all Taiwan stocks. A simple +4% daily change is not a comprehensive breakout strategy, and the results do not prove every breakout tactic fails.

### Implication

Do not auto-buy on +4% day-move signals, especially next-opening with no risk limits. Do **not** assume a panic-reversal strategy outperforms: too few eligible observations. Next work should gather a broader historically faithful universe and separately evaluate clear reversal setup variants using pre-registered criteria, holding out dates untouched.
