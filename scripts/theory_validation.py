from __future__ import annotations
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "ai_backtest.csv"
OUT = ROOT / "data" / "theory_validation.csv"


def _has(s: pd.Series, token: str) -> pd.Series:
    return s.fillna("").astype(str).str.contains(token, regex=False)


def _summary(df: pd.DataFrame, mask: pd.Series) -> dict:
    sub = df.loc[mask]
    out = {"n": int(len(sub))}
    for col in ("t1", "t3", "t5", "t10"):
        vals = pd.to_numeric(sub[col], errors="coerce").dropna() if col in sub else pd.Series(dtype=float)
        out[col + "_avg"] = round(float(vals.mean()), 3) if len(vals) else None
        out[col + "_win"] = round(float((vals > 0).mean() * 100), 1) if len(vals) else None
    return out


def main() -> None:
    df = pd.read_csv(SRC)
    flags = df["flags"].fillna("")
    close = pd.to_numeric(df["close_strength"], errors="coerce")
    vol = pd.to_numeric(df["vol_ratio"], errors="coerce")
    chg = pd.to_numeric(df["day_chg_pct"], errors="coerce")

    rules = {
        "ALL": pd.Series(True, index=df.index),
        "BREAKOUT_20D": _has(flags, "BREAKOUT_20D"),
        "POCKET_PIVOT": _has(flags, "POCKET_PIVOT"),
        "BB_SQUEEZE_BREAK": _has(flags, "BB_SQUEEZE_BREAK"),
        "STRONG_CLOSE": close >= 0.80,
        "VOL_2X_4X": (vol >= 2.0) & (vol <= 4.0),
        "VOL_GT4X": vol > 4.0,
        "MOVE_2_7PCT": (chg >= 2.0) & (chg <= 7.0),
        "MOVE_GT8PCT": chg > 8.0,
        "ONEIL_PROXY": _has(flags, "BREAKOUT_20D") & (close >= 0.70) & (vol >= 1.5),
        "LIVERMORE_PROXY": _has(flags, "BREAKOUT_20D") & (close >= 0.75) & (chg > 0),
        "VCP_PROXY": _has(flags, "BB_SQUEEZE_BREAK") & (close >= 0.70),
    }

    rows = [{"rule": name, **_summary(df, mask)} for name, mask in rules.items()]
    out = pd.DataFrame(rows)
    base = out.loc[out["rule"] == "ALL"].iloc[0]
    for col in ("t1_avg", "t3_avg", "t5_avg", "t10_avg"):
        out[col + "_lift"] = out[col] - base[col]
    out = out.sort_values(["t5_avg", "t3_avg", "n"], ascending=[False, False, False])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
