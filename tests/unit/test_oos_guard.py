from taiwan_stock_agent.domain.oos_guard import oos_adaptation_guard


def test_oos_guard_warmup_blocks_adaptation():
    g = oos_adaptation_guard({"overall": {"n": 12, "t5_avg": 4.0, "t5_win_rate": 70}})
    assert g["stage"] == "WARMUP"
    assert g["allow_adaptive_weights"] is False


def test_oos_guard_trusted_requires_large_healthy_sample():
    g = oos_adaptation_guard({"overall": {"n": 65, "t5_avg": 2.0, "t5_win_rate": 55}})
    assert g["stage"] == "TRUSTED"
    assert g["allow_adaptive_weights"] is True


def test_oos_guard_degraded_cuts_position():
    g = oos_adaptation_guard({"overall": {"n": 70, "t5_avg": -1.0, "t5_win_rate": 45}})
    assert g["stage"] == "DEGRADED"
    assert g["position_multiplier"] == 0.70
