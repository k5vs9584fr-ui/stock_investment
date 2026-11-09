# Intraday scanner operations & recovery

## Status definitions

- `ERROR_NO_LIVE_MARKET_DATA`: no usable live snapshot; **never** treat results as current trade signals.
- `LIVE_SNAPSHOT_WATCH_ONLY`: current full-market snapshot available, but no validated DT-A/DT-A+ confirmation.
- `LIVE_CONFIRMED`: current snapshot and at least one qualified DT-A/DT-A+ scan result.
- `early_momentum_watch`: **watch only**; price, market and turnover momentum do not constitute an order recommendation.
- `generated_at` and `scan_date`: scanner execution timestamp, not proof that an exchange quote is fresh; scanner validates snapshot `date` and `time`.

## Fixing Fugle HTTP 401 (required)

The 2026-11-09 workflow verification tested all five routes: quote, TSE snapshot, OTC snapshot, candles and ticker. **All returned HTTP 401.**
The authentication header is correctly named `X-API-KEY` and the API URL matches official documentation.

1. Sign in to the [Fugle market data key management](https://developer.fugle.tw/docs/key/), issue a **market-data API v1.0** key (not the separate trading API key). Do **not** paste the key into chat or commit it into Git.
2. Open GitHub repository **Settings → Secrets and variables → Actions** and replace the secret named exactly `FUGLE_API_KEY`. If an old v0.3 key is configured, replace it with a v1.0 key.
3. Ensure the subscription has developer/advanced entitlement for both `snapshot/quotes/TSE` and `snapshot/quotes/OTC`. Official snapshot documentation states these endpoints are not available to Basic accounts.
4. From **Actions → Verify Fugle Market Data Access → Run workflow**, verify that *all five endpoint checks* report HTTP 200. Codes: 401=key invalid/not authenticated, 403=plan insufficient, 429=rate limited.
5. From **Actions → Day Trade Scan → Run workflow**, confirm `source=snapshot`, `data_status` and `early_momentum_watch` contain today's verified market data.

Fugle docs: https://developer.fugle.tw/docs/data/error_codes/ ; https://developer.fugle.tw/docs/data/http-api/snapshot/quotes/

## Scheduling and limits

Day Trade Scan is scheduled at 10-minute intervals during Taiwan trading sessions (GitHub Actions is *best effort*, not minute-exact).
`MAX_DEEP_CANDIDATES=12` limits intensive quote, ticker and candle queries; the market snapshot radar still covers liquid eligible stocks from both TWSE and TPEx.

**This is not a high-frequency trading system and does not place orders.**
For second-level alerts, use an authorized live WebSocket feed and an always-on alerting server; GitHub Actions cron cannot guarantee sub-minute delivery.

## Verify deployment

```bash
FUGLE_API_KEY=test-placeholder python -m unittest discover -s tests -p test_scan_guardrails.py -v
```

This test is offline and never validates the real credential. A failed live scan is intentionally marked as failed even when the offline tests pass.

## Safety rules

- Never report an unverified `fallback` row as a current quote or confirmed signal.
- Never signal a buy based on trial auction quotes.
- Treat watchlist and DT-A ranks as research candidates, not financial advice or automatic orders.
- Exclude ticker 2344 from user trade recommendations as requested.
- A breakout must still be checked for entry distance, VWAP, liquidity, invalidation level and risk/reward.
