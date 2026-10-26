from __future__ import annotations
def oos_adaptation_guard(summary:dict|None)->dict:
    overall=(summary or {}).get("overall") or {}
    n=int(overall.get("n") or 0)
    avg=overall.get("t5_avg"); win=overall.get("t5_win_rate")
    if n<30:return {"stage":"WARMUP","resolved_t5_n":n,"allow_adaptive_weights":False,"position_multiplier":1.0}
    if n<60:return {"stage":"EVALUATE","resolved_t5_n":n,"allow_adaptive_weights":False,"position_multiplier":0.95}
    avg=float(avg or 0.0); win=float(win or 0.0); healthy=avg>0 and win>=52.0
    return {"stage":"TRUSTED" if healthy else "DEGRADED","resolved_t5_n":n,"allow_adaptive_weights":bool(healthy),"position_multiplier":1.0 if healthy else 0.70}
