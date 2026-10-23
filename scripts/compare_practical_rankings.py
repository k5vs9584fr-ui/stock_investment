from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "final_scan_results.json"


def main() -> None:
    data = json.loads(SRC.read_text(encoding="utf-8"))
    practical = data.get("top_practical") or []
    model = data.get("top_model_score") or []

    print("=== TOP 10: MODEL SCORE vs PRACTICAL SCORE ===")
    print(f"{'RANK':<5} {'MODEL':<24} {'PRACTICAL':<24}")
    for i in range(10):
        m = model[i] if i < len(model) else {}
        p = practical[i] if i < len(practical) else {}
        mtxt = f"{m.get('symbol','')} {m.get('name','')} {float(m.get('final_score') or 0):.1f}"
        ptxt = f"{p.get('symbol','')} {p.get('name','')} {float(p.get('practical_score') or 0):.1f}"
        print(f"{i+1:<5} {mtxt:<24} {ptxt:<24}")

    model_top10 = {str(x.get("symbol")) for x in model[:10]}
    practical_top10 = {str(x.get("symbol")) for x in practical[:10]}
    promoted = practical_top10 - model_top10
    demoted = model_top10 - practical_top10

    print("\nPromoted into Practical Top10:", ", ".join(sorted(promoted)) or "-")
    print("Demoted from Model Top10:", ", ".join(sorted(demoted)) or "-")


if __name__ == "__main__":
    main()
