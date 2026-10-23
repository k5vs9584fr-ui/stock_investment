from __future__ import annotations

INDUSTRY_CODE_MAP = {
    "24": "半導體業",
    "25": "電腦及週邊設備業",
    "26": "光電業",
    "27": "通信網路業",
    "28": "電子零組件業",
    "29": "電子通路業",
    "30": "資訊服務業",
    "31": "其他電子業",
}


def normalize_industry(industry: str | None) -> str:
    raw = str(industry or "")
    return INDUSTRY_CODE_MAP.get(raw, raw)


def segmented_risk_adjustment(
    industry: str | None,
    flags: list[str] | None,
    segment_stats: dict | None,
) -> tuple[float, list[str]]:
    stats = segment_stats or {}
    out_flags: list[str] = []
    bonus = 0.0
    industry = normalize_industry(industry)
    flag_names = [str(x).split(":")[0] for x in (flags or [])]

    by_pattern = stats.get("by_pattern") or {}
    by_combo = stats.get("industry_pattern") or {}

    for flag in flag_names:
        p = by_pattern.get(flag) or {}
        n = int(p.get("n") or 0)
        fail = p.get("failure_rate")
        if n >= 25 and fail is not None:
            fail = float(fail)
            if fail >= 55:
                bonus -= 3.0
                out_flags.append(f"PATTERN_HIGH_FAIL:{flag}")
            elif fail <= 35:
                bonus += 2.0
                out_flags.append(f"PATTERN_LOW_FAIL:{flag}")

        combo = by_combo.get(f"{industry}|{flag}") or {}
        cn = int(combo.get("n") or 0)
        cfail = combo.get("failure_rate")
        if cn >= 10 and cfail is not None:
            cfail = float(cfail)
            if cfail >= 60:
                bonus -= 4.0
                out_flags.append(f"INDUSTRY_PATTERN_HIGH_FAIL:{flag}")
            elif cfail <= 30:
                bonus += 2.0
                out_flags.append(f"INDUSTRY_PATTERN_LOW_FAIL:{flag}")

    return round(bonus, 1), out_flags
