from taiwan_stock_agent.domain.market_universe import score_hot_universe, merge_universes


def test_hot_universe_keeps_liquid_hot_stock():
    score, flags = score_hot_universe({
        "price": 100,
        "change_pct": 4.0,
        "value": 1_500_000_000,
        "volume": 12000,
        "close_strength": 0.9,
        "high": 102,
        "low": 96,
    })
    assert score >= 60
    assert "VALUE_PRIME" in flags or "VALUE_TOP" in flags


def test_hot_universe_does_not_hard_drop_red_watch():
    score, flags = score_hot_universe({
        "price": 80,
        "change_pct": -1.5,
        "value": 800_000_000,
        "volume": 8000,
        "close_strength": 0.7,
        "high": 82,
        "low": 78,
    })
    assert score > 0
    assert "RED_WATCH" in flags


def test_hot_universe_rejects_illiquid_stock():
    score, flags = score_hot_universe({
        "price": 20,
        "change_pct": 3,
        "value": 10_000_000,
        "volume": 100,
        "close_strength": 0.9,
        "high": 21,
        "low": 19,
    })
    assert score == 0
    assert "UNIVERSE_TOO_ILLIQUID" in flags


def test_merge_universes_deduplicates_and_preserves_best_score():
    out = merge_universes(
        [{"symbol":"2332","value":100,"universe_score":70,"source":"market_snapshot"}],
        [{"symbol":"2332","value":120,"universe_score":85,"source":"electronic_watchlist"},
         {"symbol":"8150","value":200,"universe_score":80}],
        limit=10,
    )
    assert len(out) == 2
    d = {x["symbol"]:x for x in out}
    assert d["2332"]["universe_score"] == 85
    assert "market_snapshot" in d["2332"]["universe_sources"]
    assert "electronic_watchlist" in d["2332"]["universe_sources"]
