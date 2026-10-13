from taiwan_stock_agent.domain.opening_progression import compare_snapshots, build_opening_progression


def snap(rows):
    return {"top_candidates": rows}


def test_compare_snapshots_marks_upgrade_and_dropped():
    prev = snap([
        {"symbol":"A","rank":2,"opening_score":75},
        {"symbol":"B","rank":1,"opening_score":82},
    ])
    cur = snap([
        {"symbol":"A","rank":1,"opening_score":83},
        {"symbol":"C","rank":2,"opening_score":78},
    ])
    rows = {x["symbol"]: x for x in compare_snapshots(prev, cur)}
    assert rows["A"]["status"] == "UPGRADE"
    assert rows["B"]["status"] == "DROPPED"
    assert rows["C"]["status"] == "NEW"


def test_progression_identifies_persistent_leader_and_fake_breakout():
    s5 = snap([
        {"symbol":"A","rank":2,"opening_score":74},
        {"symbol":"B","rank":1,"opening_score":84},
    ])
    s15 = snap([
        {"symbol":"A","rank":1,"opening_score":82},
        {"symbol":"B","rank":2,"opening_score":80},
    ])
    s30 = snap([
        {"symbol":"A","rank":1,"opening_score":86},
        {"symbol":"C","rank":2,"opening_score":79},
    ])
    out = build_opening_progression([(5,s5),(15,s15),(30,s30)])
    assert "A" in out["persistent_leaders"]
    assert "B" in out["fake_breakouts"]
