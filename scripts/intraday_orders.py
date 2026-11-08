from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from taiwan_stock_agent.domain.holdings import load_holdings
from taiwan_stock_agent.domain.intraday_decision_report import build_intraday_decision_report

FINAL_RESULTS = ROOT / "data" / "final_scan_results.json"
DAYTRADE_RESULTS = ROOT / "data" / "daytrade_results.json"
HOLDINGS_FILE = ROOT / "data" / "holdings.json"
OUT = ROOT / "data" / "intraday_order_sheet.json"


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def merge_live_intraday(ranked_rows: list[dict], daytrade_payload: dict) -> list[dict]:
    """Overlay the newest daytrade quote/dt_metrics onto ranked model rows."""
    live_by_symbol = {
        str(x.get("symbol") or ""): x
        for x in (daytrade_payload.get("stocks") or [])
        if str(x.get("symbol") or "")
    }
    merged: list[dict] = []
    for row in ranked_rows:
        r = dict(row)
        symbol = str(r.get("symbol") or "")
        live = live_by_symbol.get(symbol)
        if live:
            for key in ("price", "high", "low", "change_pct", "dt_score", "dt_phase", "dt_flags"):
                if live.get(key) is not None:
                    r[key] = live.get(key)
            if live.get("dt_metrics"):
                r["dt_metrics"] = dict(live["dt_metrics"])
            r["live_overlay"] = True
        else:
            r["live_overlay"] = False
        merged.append(r)
    return merged


def derive_holding_weights(
    holdings: list[dict],
    ranked_rows: list[dict],
    *,
    portfolio_value: float | None,
) -> dict[str, float]:
    """Prefer explicit weight; otherwise derive from shares*price when possible."""
    price_by_symbol = {
        str(x.get("symbol") or ""): float(x.get("price") or 0.0)
        for x in ranked_rows
    }
    out: dict[str, float] = {}
    for h in holdings:
        symbol = str(h.get("symbol") or h.get("ticker") or "")
        if not symbol:
            continue

        explicit = h.get("weight")
        if explicit is not None:
            try:
                out[symbol] = max(0.0, min(1.0, float(explicit)))
                continue
            except (TypeError, ValueError):
                pass

        market_value = h.get("market_value")
        try:
            market_value_num = float(market_value) if market_value is not None else None
        except (TypeError, ValueError):
            market_value_num = None

        if market_value_num is None:
            try:
                shares = float(h.get("shares") or 0.0)
                price = price_by_symbol.get(symbol, 0.0)
                market_value_num = shares * price if shares > 0 and price > 0 else None
            except (TypeError, ValueError):
                market_value_num = None

        if portfolio_value and portfolio_value > 0 and market_value_num is not None:
            out[symbol] = max(0.0, min(1.0, market_value_num / portfolio_value))

    return out


def build_live_report(
    *,
    final_payload: dict,
    daytrade_payload: dict,
    holdings: list[dict],
    phase_minutes: int,
    portfolio_value: float | None,
) -> dict:
    ranked_rows = final_payload.get("top_practical") or final_payload.get("top_final") or []
    ranked_rows = merge_live_intraday(ranked_rows, daytrade_payload)

    holding_weights = derive_holding_weights(
        holdings,
        ranked_rows,
        portfolio_value=portfolio_value,
    )
    market_context = final_payload.get("market_context") or {}

    report = build_intraday_decision_report(
        ranked_rows,
        holdings,
        phase_minutes=phase_minutes,
        oos_guard=final_payload.get("oos_guard") or None,
        holding_weights=holding_weights,
        market_context=market_context,
        portfolio_value=portfolio_value,
    )
    report["scan_date"] = final_payload.get("scan_date")
    report["live_data_generated_at"] = daytrade_payload.get("generated_at")
    report["live_overlay_count"] = sum(1 for x in ranked_rows if x.get("live_overlay"))
    report["holding_weights"] = holding_weights
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Build live intraday Taiwan stock order sheet")
    parser.add_argument("--phase", type=int, choices=(5, 15, 30), default=15)
    parser.add_argument("--portfolio-value", type=float, default=None)
    parser.add_argument("--final-results", type=Path, default=FINAL_RESULTS)
    parser.add_argument("--daytrade-results", type=Path, default=DAYTRADE_RESULTS)
    parser.add_argument("--holdings", type=Path, default=HOLDINGS_FILE)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()

    final_payload = _load_json(args.final_results)
    if not final_payload:
        raise RuntimeError(f"missing final results: {args.final_results}")

    daytrade_payload = _load_json(args.daytrade_results)
    holdings = load_holdings(args.holdings)

    report = build_live_report(
        final_payload=final_payload,
        daytrade_payload=daytrade_payload,
        holdings=holdings,
        phase_minutes=args.phase,
        portfolio_value=args.portfolio_value,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    print(f"phase={args.phase}m live_overlay={report.get('live_overlay_count', 0)}")
    print(f"regime={report.get('summary', {}).get('regime_v2')}")
    print("=== ORDER SHEET ===")
    for i, order in enumerate((report.get("order_sheet") or {}).get("orders") or [], 1):
        shares = order.get("shares")
        shares_text = f"{shares}股" if shares is not None else f"權重 {float(order.get('weight') or 0)*100:.1f}%"
        print(
            f"{i:02d}. {order.get('side')} {order.get('symbol')} {order.get('name','')} | "
            f"{shares_text} | 觸發 {order.get('trigger_price')} | 停損 {order.get('hard_stop')} | "
            f"{order.get('source')}"
        )
    print(f"saved: {args.output}")


if __name__ == "__main__":
    main()
