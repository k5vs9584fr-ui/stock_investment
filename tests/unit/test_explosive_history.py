from taiwan_stock_agent.domain.explosive_history import (
    explosive_history_adjustment,
    summarize_explosive_history,
)


def test_summarize_explosive_history_tracks_t1_t3_t5_and_big_wins():
    rows = [
        {"explosive_phase":"FRESH_IGNITION","t1_return":1.0,"t3_return":4.0,"t5_return":5.0},
        {"explosive_phase":"FRESH_IGNITION","t1_return":-1.0,"t3_return":2.0,"t5_return":-2.0},
        {"explosive_phase":"EARLY_MAIN_MOVE","t1_return":2.0,"t3_return":6.0,"t5_return":8.0},
    ]
    out = summarize_explosive_history(rows)
    fresh = out["FRESH_IGNITION"]
    assert fresh["t3_n"] == 2
    assert fresh["t3_win_rate"] == 100.0
    assert fresh["t3_big_win_rate"] == 50.0
    assert fresh["t3_avg"] == 3.0


def test_strong_phase_history_adds_score():
    row = {
        "surge_score":80,
        "surge_stage":"S級：首發動可追",
        "surge_metrics":{"fresh_ignition":True,"overextended":False},
    }
    stats = {
        "FRESH_IGNITION":{
            "t3_n":30,
            "t3_win_rate":70.0,
            "t3_big_win_rate":45.0,
            "t3_avg":3.5,
        }
    }
    bonus, flags = explosive_history_adjustment(row, stats)
    assert bonus > 3
    assert "EXPLOSIVE_HISTORY_STRONG" in flags


def test_weak_phase_history_reduces_score():
    row = {
        "surge_score":90,
        "surge_stage":"S+級：主升初段可追",
        "surge_metrics":{"early_main_move":True,"overextended":False},
    }
    stats = {
        "EARLY_MAIN_MOVE":{
            "t3_n":30,
            "t3_win_rate":35.0,
            "t3_big_win_rate":10.0,
            "t3_avg":-1.5,
        }
    }
    bonus, flags = explosive_history_adjustment(row, stats)
    assert bonus < -3
    assert "EXPLOSIVE_HISTORY_WEAK" in flags


def test_small_sample_history_is_ignored():
    row = {
        "surge_score":80,
        "surge_stage":"S級：首發動可追",
        "surge_metrics":{"fresh_ignition":True,"overextended":False},
    }
    stats = {
        "FRESH_IGNITION":{
            "t3_n":3,
            "t3_win_rate":100.0,
            "t3_big_win_rate":100.0,
            "t3_avg":10.0,
        }
    }
    bonus, flags = explosive_history_adjustment(row, stats)
    assert bonus == 0.0
    assert "EXPLOSIVE_HISTORY_INSUFFICIENT" in flags
