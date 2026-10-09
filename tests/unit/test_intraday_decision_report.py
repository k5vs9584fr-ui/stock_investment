from taiwan_stock_agent.domain.intraday_decision_report import build_intraday_decision_report


def _row(symbol, sector, hybrid, practical, surge, dt, confidence="HIGH"):
    return {
        "symbol": symbol,
        "name": symbol,
        "industry_code": sector,
        "hybrid_action_score": hybrid,
        "practical_score": practical,
        "surge_score": surge,
        "score_confidence": {"level": confidence},
        "risk_policy": {"max_position_pct": 20},
        "dt_metrics": dt,
    }


def test_report_builds_top3_capital_and_summary():
    rows = [
        _row("A", "24", 92, 88, 82, {
            "vwap_gap_pct": 0.7, "return_15m_pct": 1.1,
            "volume_accel_5m": 1.8, "near_intraday_high": 0.995,
        }),
        _row("B", "25", 88, 84, 76, {
            "vwap_gap_pct": 0.4, "return_15m_pct": 0.8,
            "volume_accel_5m": 1.4, "near_intraday_high": 0.99,
        }),
        _row("C", "26", 84, 80, 72, {
            "vwap_gap_pct": 0.3, "return_15m_pct": 0.5,
            "volume_accel_5m": 1.3, "near_intraday_high": 0.985,
        }),
    ]
    out = build_intraday_decision_report(rows, [], phase_minutes=15)
    assert len(out["top_candidates"]) == 3
    assert out["summary"]["top_candidate"] == "A"
    assert round(out["capital_plan"]["deployed_weight"] + out["capital_plan"]["cash_weight"], 4) == 1.0


def test_report_includes_rotation_position_plan():
    rows = [
        _row("H", "24", 70, 68, 55, {
            "vwap_gap_pct": -0.4, "return_15m_pct": -0.2,
            "volume_accel_5m": 0.9, "near_intraday_high": 0.97,
        }),
        _row("C", "27", 92, 90, 84, {
            "vwap_gap_pct": 0.8, "return_15m_pct": 1.2,
            "volume_accel_5m": 1.8, "near_intraday_high": 0.995,
        }),
    ]
    holdings = [{"symbol": "H", "name": "H", "cost": 100, "shares": 1000}]
    out = build_intraday_decision_report(
        rows,
        holdings,
        holding_weights={"H": 0.40},
        cost_pct=0.5,
    )
    assert out["rotation_actions"]
    top = out["rotation_actions"][0]
    assert top["held_symbol"] == "H"
    assert top["challenger_symbol"] == "C"
    assert top["position_plan"]["current_weight"] == 0.40


def test_report_surfaces_rejected_open_as_no_chase_or_reject():
    rows = [
        _row("BAD", "24", 95, 92, 90, {
            "vwap_gap_pct": -1.2, "return_15m_pct": -1.5,
            "volume_accel_5m": 0.5, "near_intraday_high": 0.92,
        }),
        _row("GOOD", "25", 88, 84, 76, {
            "vwap_gap_pct": 0.5, "return_15m_pct": 0.8,
            "volume_accel_5m": 1.4, "near_intraday_high": 0.99,
        }),
    ]
    out = build_intraday_decision_report(rows, [], target_n=1)
    assert out["summary"]["top_candidate"] == "GOOD"
    assert any(x["symbol"] == "BAD" for x in out["no_chase"])


def test_report_rotation_actions_are_prioritized():
    rows = [
        _row("H1", "24", 70, 68, 55, {
            "vwap_gap_pct": -0.4, "return_15m_pct": -0.2,
            "volume_accel_5m": 0.9, "near_intraday_high": 0.97,
        }),
        _row("H2", "25", 84, 82, 74, {
            "vwap_gap_pct": 0.3, "return_15m_pct": 0.5,
            "volume_accel_5m": 1.2, "near_intraday_high": 0.985,
        }),
        _row("C", "27", 93, 91, 86, {
            "vwap_gap_pct": 0.8, "return_15m_pct": 1.2,
            "volume_accel_5m": 1.8, "near_intraday_high": 0.995,
        }),
    ]
    holdings = [
        {"symbol": "H1", "cost": 100, "shares": 1000},
        {"symbol": "H2", "cost": 100, "shares": 1000},
    ]
    out = build_intraday_decision_report(
        rows,
        holdings,
        holding_weights={"H1": 0.30, "H2": 0.30},
        cost_pct=0.5,
    )
    priority = {"ROTATE": 2, "WATCH_ROTATION": 1, "KEEP_CURRENT": 0}
    actions = out["rotation_actions"]
    assert actions
    assert priority[actions[0]["action"]] >= priority[actions[-1]["action"]]
