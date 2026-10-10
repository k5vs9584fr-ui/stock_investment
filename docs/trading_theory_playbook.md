# Trading Theory Playbook

This document records trader theories that are allowed to influence the ranking system.
A theory is included only when it can be expressed as a measurable rule and later
validated against Taiwan-stock historical data.

## William O'Neil — CAN SLIM / leadership

Operationalized ideas:
- prefer leaders near/new highs instead of cheap laggards;
- require demand confirmation around breakouts;
- institutional sponsorship matters;
- market direction matters.

Model mapping:
- near_20d_high;
- breakout / near-breakout flags;
- chip_score;
- market-regime overlay (next phase).

## Mark Minervini — Trend Template / VCP

Operationalized ideas:
- contraction before expansion;
- tighter price ranges and drying volume near highs;
- avoid extended entries;
- buy only after confirmation.

Model mapping:
- MA convergence / spread;
- vol5_vs_20 dry-up;
- range20 compression;
- proximity to 20-day high;
- NOT_EXTENDED_10D.

## Jesse Livermore — pivotal points and leadership

Operationalized ideas:
- wait for price to confirm the thesis;
- focus on leaders;
- add only to winners, never average down;
- keep capital out of drifting names.

Model mapping:
- confirmed breakout + strong close + positive short momentum;
- stagnation penalty in Practical Score;
- execution rule: no averaging down.

## Richard Wyckoff — effort versus result

Operationalized ideas:
- unusually high volume without matching price progress can indicate supply;
- genuine strength should show price progress with demand;
- failed breakouts / upthrust behavior should be penalized.

Model mapping:
- volume3_vs_20 vs short-horizon return and close_strength;
- distribution warning.

## Stan Weinstein — Stage Analysis

Operationalized ideas:
- favor Stage 2-style advancing trends;
- avoid late-stage or declining structures.

Model mapping:
- rising MA20;
- bullish moving-average alignment;
- near-high behavior;
- positive 5-day momentum.

## Darvas — box breakout

Planned:
- explicitly identify multi-day boxes with shrinking range;
- require breakout close and volume confirmation;
- reject immediate return into the box.

## Safeguards

No named trader receives a large standalone weight.
Theory overlay is capped in practice by the main Practical Score and must earn
continued use through out-of-sample backtests. Any rule that degrades expectancy,
drawdown, or hit rate will be removed regardless of reputation.
