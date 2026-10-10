from __future__ import annotations
import csv,json
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; TRACK=ROOT/"data"/"oos_top3_tracking.csv"; OUT=ROOT/"data"/"oos_top3_summary.json"

def fnum(v):
    try:return float(v)
    except (TypeError,ValueError):return None

def stats(rows):
    vals=[fnum(r.get("t5_return")) for r in rows if str(r.get("resolved_t5")).lower()=="true"]
    vals=[x for x in vals if x is not None]
    return {"n":len(vals),"t5_avg":round(sum(vals)/len(vals),3) if vals else None,"t5_win_rate":round(sum(x>0 for x in vals)/len(vals)*100,1) if vals else None,"t5_loss_rate":round(sum(x<0 for x in vals)/len(vals)*100,1) if vals else None}

def grouped(rows,key):
    b=defaultdict(list)
    for r in rows:b[str(r.get(key) or "UNKNOWN")].append(r)
    out={}
    for k,v in b.items():
        s=stats(v)
        if s["n"]>0:out[k]=s
    return out

def main():
    if not TRACK.exists():
        OUT.write_text(json.dumps({"signals_total":0,"overall":{"n":0}},indent=2),encoding="utf-8");return
    rows=list(csv.DictReader(TRACK.open("r",encoding="utf-8")))
    out={"signals_total":len(rows),"overall":stats(rows),"by_rank":grouped(rows,"rank"),"by_confidence":grouped(rows,"confidence_level"),"by_entry_mode":grouped(rows,"entry_mode"),"by_regime":grouped(rows,"regime_v2"),"by_sector":grouped(rows,"sector_key"),"by_explosive_phase":grouped(rows,"explosive_phase")}
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8");print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
