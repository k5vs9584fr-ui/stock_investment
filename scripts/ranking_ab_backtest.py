from __future__ import annotations

from pathlib import Path
import math
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "ai_backtest.csv"
OUT = ROOT / "data" / "ranking_ab_backtest.csv"
SUMMARY = ROOT / "data" / "ranking_ab_summary.csv"


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def practical_proxy(df: pd.DataFrame) -> pd.Series:
    score = _num(df["score"]).fillna(0)
    close = _num(df["close_strength"]).fillna(0.5)
    vol = _num(df["vol_ratio"]).fillna(1.0)
    chg = _num(df["day_chg_pct"]).fillna(0.0)
    gap = _num(df["gap_pct"]).fillna(0.0)
    rsi = _num(df["rsi"]).fillna(50.0)
    flags = df["flags"].fillna("").astype(str)

    out = score * 0.55 + close.clip(0, 1) * 25.0

    # Empirically supported confirmation features from the first validation pass.
    out += flags.str.contains("BREAKOUT_20D", regex=False).astype(float) * 8.0
    out += ((close >= 0.75) & flags.str.contains("BREAKOUT_20D", regex=False)).astype(float) * 6.0
    out += ((close >= 0.70) & (vol >= 1.5) & flags.str.contains("BREAKOUT_20D", regex=False)).astype(float) * 6.0
    out += (close >= 0.80).astype(float) * 4.0

    # Moderate volume is useful, but extreme volume had a lower hit rate.
    out += ((vol >= 1.5) & (vol <= 4.0)).astype(float) * 2.0
    out -= (vol > 4.0).astype(float) * 3.0

    # Failed/late breakout proxies.
    out -= (flags.str.contains("BREAKOUT_20D", regex=False) & (close < 0.45)).astype(float) * 10.0
    out -= ((chg > 8.0) & (close < 0.65)).astype(float) * 6.0
    out -= ((gap > 6.0) & (close < 0.70)).astype(float) * 4.0
    out -= ((rsi >= 75.0) & (chg > 6.0)).astype(float) * 3.0

    return out


def max_drawdown(daily_returns_pct: list[float]) -> float:
    equity = 1.0
    peak = 1.0
    mdd = 0.0
    for r in daily_returns_pct:
        if r is None or not math.isfinite(r):
            continue
        equity *= 1.0 + r / 100.0
        peak = max(peak, equity)
        dd = (equity / peak - 1.0) * 100.0
        mdd = min(mdd, dd)
    return round(mdd, 2)


def strategy_rows(df: pd.DataFrame, rank_col: str, top_n: int) -> pd.DataFrame:
    picks = []
    for day, g in df.groupby("signal_date", sort=True):
        ranked = g.sort_values(rank_col, ascending=False).head(top_n)
        row = {"signal_date": day, "strategy": rank_col, "n": len(ranked)}
        for h in (1, 3, 5, 10):
            vals = _num(ranked[f"t{h}"]).dropna()
            row[f"t{h}_avg"] = float(vals.mean()) if len(vals) else None
            row[f"t{h}_win"] = float((vals > 0).mean() * 100) if len(vals) else None

        forward_cols = [f"t{i}" for i in range(1, 16) if f"t{i}" in ranked]
        if forward_cols:
            fwd = ranked[forward_cols].apply(pd.to_numeric, errors="coerce")
            row["avg_mae_15"] = float(fwd.min(axis=1).mean())
            row["avg_mfe_15"] = float(fwd.max(axis=1).mean())
        picks.append(row)
    return pd.DataFrame(picks)


def summarize(daily: pd.DataFrame, label: str) -> dict:
    out = {"strategy": label, "days": int(len(daily))}
    for h in (1, 3, 5, 10):
        vals = pd.to_numeric(daily[f"t{h}_avg"], errors="coerce").dropna()
        out[f"t{h}_avg"] = round(float(vals.mean()), 3) if len(vals) else None
        wins = pd.to_numeric(daily[f"t{h}_win"], errors="coerce").dropna()
        out[f"t{h}_win"] = round(float(wins.mean()), 1) if len(wins) else None
    out["avg_mae_15"] = round(float(pd.to_numeric(daily["avg_mae_15"], errors="coerce").mean()), 3)
    out["avg_mfe_15"] = round(float(pd.to_numeric(daily["avg_mfe_15"], errors="coerce").mean()), 3)
    out["t1_equity_mdd"] = max_drawdown(pd.to_numeric(daily["t1_avg"], errors="coerce").dropna().tolist())
    return out


def main() -> None:
    df = pd.read_csv(SRC)
    df["old_rank"] = _num(df["score"]).fillna(0)
    df["practical_proxy"] = practical_proxy(df)

    top_n = 5
    old_daily = strategy_rows(df, "old_rank", top_n)
    new_daily = strategy_rows(df, "practical_proxy", top_n)

    daily = pd.concat([old_daily, new_daily], ignore_index=True)
    daily.to_csv(OUT, index=False)

    summary = pd.DataFrame([
        summarize(old_daily, "OLD_SCORE_TOP5"),
        summarize(new_daily, "PRACTICAL_PROXY_TOP5"),
    ])
    summary.to_csv(SUMMARY, index=False)
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
