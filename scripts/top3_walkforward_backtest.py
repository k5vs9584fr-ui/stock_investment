from __future__ import annotations

from pathlib import Path
import math
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "ai_backtest.csv"
OUT = ROOT / "data" / "top3_walkforward_summary.csv"


def num(s):
    return pd.to_numeric(s, errors="coerce")


def score_proxy(df: pd.DataFrame) -> pd.Series:
    score = num(df["score"]).fillna(0)
    close = num(df["close_strength"]).fillna(0.5)
    vol = num(df["vol_ratio"]).fillna(1.0)
    chg = num(df["day_chg_pct"]).fillna(0.0)
    gap = num(df["gap_pct"]).fillna(0.0)
    rsi = num(df["rsi"]).fillna(50.0)
    flags = df["flags"].fillna("").astype(str)

    out = score * 0.55 + close.clip(0, 1) * 25
    bo = flags.str.contains("BREAKOUT_20D", regex=False)
    out += bo.astype(float) * 8
    out += (bo & (close >= 0.75)).astype(float) * 6
    out += (bo & (close >= 0.70) & (vol >= 1.5)).astype(float) * 6
    out += (close >= 0.80).astype(float) * 4
    out += ((vol >= 1.5) & (vol <= 4.0)).astype(float) * 2
    out -= (vol > 4.0).astype(float) * 3
    out -= (bo & (close < 0.45)).astype(float) * 10
    out -= ((chg > 8) & (close < 0.65)).astype(float) * 6
    out -= ((gap > 6) & (close < 0.70)).astype(float) * 4
    out -= ((rsi >= 75) & (chg > 6)).astype(float) * 3
    return out


def max_drawdown(returns):
    equity = 1.0
    peak = 1.0
    mdd = 0.0
    for r in returns:
        if pd.isna(r):
            continue
        equity *= 1 + float(r) / 100
        peak = max(peak, equity)
        mdd = min(mdd, (equity / peak - 1) * 100)
    return round(mdd, 2)


def evaluate(df: pd.DataFrame, rank_col: str, top_n: int) -> dict:
    days = []
    for _, g in df.groupby("signal_date", sort=True):
        picks = g.sort_values(rank_col, ascending=False).head(top_n)
        rec = {}
        for h in (1, 3, 5, 10):
            vals = num(picks[f"t{h}"]).dropna()
            rec[f"t{h}"] = vals.mean() if len(vals) else None
            rec[f"w{h}"] = (vals > 0).mean() * 100 if len(vals) else None
        fcols = [f"t{i}" for i in range(1, 16)]
        fwd = picks[fcols].apply(pd.to_numeric, errors="coerce")
        rec["mae"] = fwd.min(axis=1).mean()
        rec["mfe"] = fwd.max(axis=1).mean()
        days.append(rec)

    d = pd.DataFrame(days)
    return {
        "ranking": rank_col,
        "top_n": top_n,
        "days": len(d),
        "t1_avg": round(d["t1"].mean(), 3),
        "t3_avg": round(d["t3"].mean(), 3),
        "t5_avg": round(d["t5"].mean(), 3),
        "t10_avg": round(d["t10"].mean(), 3),
        "t5_win": round(d["w5"].mean(), 1),
        "avg_mae_15": round(d["mae"].mean(), 3),
        "avg_mfe_15": round(d["mfe"].mean(), 3),
        "t1_mdd": max_drawdown(d["t1"].tolist()),
    }


def main():
    df = pd.read_csv(SRC)
    df["old_score"] = num(df["score"]).fillna(0)
    df["practical_proxy"] = score_proxy(df)

    rows = []
    for n in (1, 3, 5, 7, 10):
        rows.append(evaluate(df, "old_score", n))
        rows.append(evaluate(df, "practical_proxy", n))

    out = pd.DataFrame(rows)
    out.to_csv(OUT, index=False)
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
