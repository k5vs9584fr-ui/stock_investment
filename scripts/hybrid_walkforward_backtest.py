from __future__ import annotations

from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "ai_backtest.csv"
OUT = ROOT / "data" / "hybrid_walkforward_results.csv"
SUMMARY = ROOT / "data" / "hybrid_walkforward_summary.csv"

WEIGHTS = (0.0, 0.25, 0.50, 0.75, 1.0)
WARMUP_DAYS = 20
MIN_ADAPT_DAYS = 30
REBALANCE_DAYS = 5
TOP_N = 3
ADAPT_EDGE_THRESHOLD = 0.50
DEFAULT_OLD_WEIGHT = 0.50


def num(s):
    return pd.to_numeric(s, errors="coerce")


def practical_proxy(df: pd.DataFrame) -> pd.Series:
    score = num(df["score"]).fillna(0)
    close = num(df["close_strength"]).fillna(0.5)
    vol = num(df["vol_ratio"]).fillna(1.0)
    chg = num(df["day_chg_pct"]).fillna(0.0)
    gap = num(df["gap_pct"]).fillna(0.0)
    rsi = num(df["rsi"]).fillna(50.0)
    flags = df["flags"].fillna("").astype(str)

    out = score * 0.55 + close.clip(0, 1) * 25.0
    bo = flags.str.contains("BREAKOUT_20D", regex=False)
    out += bo.astype(float) * 8.0
    out += (bo & (close >= 0.75)).astype(float) * 6.0
    out += (bo & (close >= 0.70) & (vol >= 1.5)).astype(float) * 6.0
    out += (close >= 0.80).astype(float) * 4.0
    out += ((vol >= 1.5) & (vol <= 4.0)).astype(float) * 2.0
    out -= (vol > 4.0).astype(float) * 3.0
    out -= (bo & (close < 0.45)).astype(float) * 10.0
    out -= ((chg > 8.0) & (close < 0.65)).astype(float) * 6.0
    out -= ((gap > 6.0) & (close < 0.70)).astype(float) * 4.0
    out -= ((rsi >= 75.0) & (chg > 6.0)).astype(float) * 3.0
    return out


def add_scores(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["old_score"] = num(out["score"]).fillna(0)
    out["practical_proxy"] = practical_proxy(out)
    return out


def top3_day_return(day_df: pd.DataFrame, weight_old: float, horizon: int) -> float | None:
    d = day_df.copy()
    d["hybrid"] = weight_old * d["old_score"] + (1.0 - weight_old) * d["practical_proxy"]
    picks = d.sort_values("hybrid", ascending=False).head(TOP_N)
    vals = num(picks[f"t{horizon}"]).dropna()
    return float(vals.mean()) if len(vals) else None


def evaluate_history(df: pd.DataFrame, dates: list[str], weight_old: float) -> float:
    # Objective favors T+5 return but penalizes unstable daily T+1 drawdowns.
    t5 = []
    t1 = []
    for d in dates:
        day = df[df["signal_date"] == d]
        r5 = top3_day_return(day, weight_old, 5)
        r1 = top3_day_return(day, weight_old, 1)
        if r5 is not None:
            t5.append(r5)
        if r1 is not None:
            t1.append(r1)

    if not t5:
        return -999.0

    equity = peak = 1.0
    mdd = 0.0
    for r in t1:
        equity *= 1 + r / 100.0
        peak = max(peak, equity)
        mdd = min(mdd, (equity / peak - 1) * 100.0)

    return sum(t5) / len(t5) + 0.15 * mdd


def main():
    df = add_scores(pd.read_csv(SRC))
    dates = sorted(df["signal_date"].dropna().astype(str).unique())
    if len(dates) <= WARMUP_DAYS:
        raise RuntimeError("not enough history for walk-forward")

    records = []
    i = WARMUP_DAYS
    while i < len(dates):
        train_dates = dates[:i]
        test_dates = dates[i:i + REBALANCE_DAYS]

        chosen = DEFAULT_OLD_WEIGHT
        if len(train_dates) >= MIN_ADAPT_DAYS:
            scores = {w: evaluate_history(df, train_dates, w) for w in WEIGHTS}
            baseline = scores[DEFAULT_OLD_WEIGHT]
            best_weight = max(scores, key=scores.get)
            if scores[best_weight] >= baseline + ADAPT_EDGE_THRESHOLD:
                chosen = best_weight

        for d in test_dates:
            day = df[df["signal_date"] == d]
            rec = {
                "signal_date": d,
                "chosen_old_weight": chosen,
                "chosen_practical_weight": 1.0 - chosen,
            }
            for h in (1, 3, 5, 10):
                rec[f"t{h}_avg"] = top3_day_return(day, chosen, h)
            records.append(rec)
        i += REBALANCE_DAYS

    out = pd.DataFrame(records)
    out.to_csv(OUT, index=False)

    summary = {
        "test_days": len(out),
        "t1_avg": round(out["t1_avg"].mean(), 3),
        "t3_avg": round(out["t3_avg"].mean(), 3),
        "t5_avg": round(out["t5_avg"].mean(), 3),
        "t10_avg": round(out["t10_avg"].mean(), 3),
        "weight_0_pct": round((out["chosen_old_weight"] == 0).mean() * 100, 1),
        "weight_25_pct": round((out["chosen_old_weight"] == 0.25).mean() * 100, 1),
        "weight_50_pct": round((out["chosen_old_weight"] == 0.50).mean() * 100, 1),
        "weight_75_pct": round((out["chosen_old_weight"] == 0.75).mean() * 100, 1),
        "weight_100_pct": round((out["chosen_old_weight"] == 1.0).mean() * 100, 1),
    }
    pd.DataFrame([summary]).to_csv(SUMMARY, index=False)
    print(pd.DataFrame([summary]).to_string(index=False))


if __name__ == "__main__":
    main()
