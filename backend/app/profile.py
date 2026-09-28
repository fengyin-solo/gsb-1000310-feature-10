"""淤积变化剖面：前后两次淤积测量的可比性判定与结论计算。

趋势图上的曲线、任务列表里的「淤积变化结论」、复查验收给出的验收结论，都必须引用
本模块 build_profile() 的同一份计算结果，避免三处各算一套、口径互相矛盾。

不可比判定规则（任一命中即不可比，并在曲线上标出不可比区间）：
1. 缺历史值：不足两次测量，或相邻任一次缺少淤积值/单位/测量时间；
2. 单位不一致：相邻两次单位不同，不做跨单位换算，直接判不可比；
3. 连续测量断档：相邻两次测量间隔超过 MAX_MEASURE_GAP_DAYS 天。
"""
from __future__ import annotations

from datetime import date
from typing import Any

# 相邻两次测量允许的最大间隔（天），超过即视为连续测量断档
MAX_MEASURE_GAP_DAYS = 45
# 判定「基本持平」的相对带宽：|差值| 不超过参照值的 10% 视为持平
FLAT_RELATIVE = 0.10
# 判定「基本持平」的绝对死区，按单位取值，消除毫米级测量抖动
ABS_EPSILON: dict[str, float] = {"mm": 5.0, "cm": 1.0}
DEFAULT_EPSILON = 1.0

TREND_DOWN = "淤积减轻"
TREND_UP = "淤积加重"
TREND_FLAT = "基本持平"

REASON_MISSING = "缺历史值"
REASON_UNIT = "单位不一致"
REASON_GAP = "连续测量断档"
REASON_FEW = "不足两次测量"

VERDICT_PASS = "验收通过"
VERDICT_FAIL_UP = "验收不通过·淤积加重"
VERDICT_FAIL_FLAT = "验收不通过·变化不明显"
VERDICT_HOLD = "暂缓验收·数据不可比"
VERDICT_IDLE = "暂无测量数据"

PROFILE_KEY = "淤积变化剖面"


def _to_date(value: Any) -> date | None:
    """解析 YYYY-MM-DD / YYYY/MM/DD；解析不了返回 None，由调用方按缺时间处理。"""
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if "-" in text:
            year, month, day = (int(part) for part in text.split("-"))
        elif "/" in text:
            year, month, day = (int(part) for part in text.split("/"))
        else:
            return None
        return date(year, month, day)
    except (ValueError, TypeError):
        return None


def _to_float(value: Any) -> float | None:
    """淤积值允许缺失；非数字一律按缺历史值处理，而不是抛异常。"""
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _trend(previous: float, current: float, unit: str | None) -> str:
    """同单位、同连续区间内的前后值比较，给出三档趋势。"""
    delta = current - previous
    epsilon = ABS_EPSILON.get((unit or "").lower(), DEFAULT_EPSILON)
    reference = max(abs(previous), epsilon)
    if abs(delta) <= epsilon or abs(delta) <= FLAT_RELATIVE * reference:
        return TREND_FLAT
    return TREND_DOWN if delta < 0 else TREND_UP


def _format_value(value: float | None, unit: str | None, degree: str | None) -> str:
    """列表/剖面共用的淤积量显示文案，避免各处自行拼字符串。"""
    if value is None:
        return degree or "缺历史值"
    head = f"{value:g} {unit}".strip()
    return f"{head}（{degree}）" if degree else head


def _normalize_point(seq: int, raw: dict[str, Any]) -> dict[str, Any]:
    value = _to_float(raw.get("淤积值"))
    unit = str(raw.get("单位") or "").strip()
    measured_raw = str(raw.get("测量时间") or "").strip()
    degree = str(raw.get("淤积程度") or "").strip() or None
    method = str(raw.get("清疏方式") or "").strip() or None
    measured_date = _to_date(measured_raw)
    missing = value is None or not unit or not measured_raw
    return {
        "seq": seq,
        "测量时间": measured_raw or None,
        "淤积程度": degree,
        "淤积值": value,
        "单位": unit or None,
        "淤积显示": _format_value(value, unit or None, degree),
        "清疏方式": method,
        "comparable": not missing and measured_date is not None,
        "missing": missing or measured_date is None,
        "_date": measured_date,
    }


def _public_point(point: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in point.items() if not key.startswith("_")}


def _build_segment(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    """相邻两次测量构成一个区间，区间结论同时服务曲线着色与前后比较。"""
    reasons: list[str] = []
    if previous["missing"] or current["missing"]:
        reasons.append(REASON_MISSING)
    if previous["单位"] != current["单位"]:
        reasons.append(REASON_UNIT)

    gap_days: int | None = None
    if previous["_date"] is not None and current["_date"] is not None:
        gap_days = (current["_date"] - previous["_date"]).days
        if gap_days > MAX_MEASURE_GAP_DAYS:
            reasons.append(REASON_GAP)
    else:
        # 时间无法解析就无法证明测量连续，按断档处理
        reasons.append(REASON_GAP)

    reasons = list(dict.fromkeys(reasons))
    comparable = not reasons
    trend: str | None = None
    delta: float | None = None
    if comparable:
        delta = round(float(current["淤积值"]) - float(previous["淤积值"]), 2)
        trend = _trend(float(previous["淤积值"]), float(current["淤积值"]), current["单位"])

    return {
        "from_seq": previous["seq"],
        "to_seq": current["seq"],
        "from_time": previous["测量时间"],
        "to_time": current["测量时间"],
        "comparable": comparable,
        "reasons": reasons,
        "gap_days": gap_days,
        "前次": _public_point(previous),
        "后次": _public_point(current),
        "前值": previous["淤积值"],
        "后值": current["淤积值"],
        "前单位": previous["单位"],
        "后单位": current["单位"],
        "trend": trend,
        "delta": delta,
    }


def _build_headline(ordered: list[dict[str, Any]], segments: list[dict[str, Any]]) -> dict[str, Any]:
    """前后两次 = 时间序列上最近的两次测量；结论即列表/验收复用的那句话。"""
    if not ordered:
        return {
            "comparable": False,
            "reasons": [],
            "trend": None,
            "delta": None,
            "gap_days": None,
            "前次": None,
            "后次": None,
            "conclusion": "暂无淤积测量记录",
        }
    if len(ordered) < 2:
        only = _public_point(ordered[-1])
        return {
            "comparable": False,
            "reasons": [REASON_FEW],
            "trend": None,
            "delta": None,
            "gap_days": None,
            "前次": only,
            "后次": only,
            "conclusion": f"仅 {only['测量时间'] or '一次'} 一次测量，无法比较前后淤积变化",
        }

    segment = segments[-1]
    previous, current = ordered[-2], ordered[-1]
    headline = {
        "comparable": segment["comparable"],
        "reasons": segment["reasons"],
        "trend": segment["trend"],
        "delta": segment["delta"],
        "gap_days": segment["gap_days"],
        "前次": _public_point(previous),
        "后次": _public_point(current),
    }
    if not segment["comparable"]:
        headline["conclusion"] = (
            f"前后两次测量{'、'.join(segment['reasons'])}，淤积变化不可直接比较"
        )
        return headline

    direction = {TREND_DOWN: "下降", TREND_UP: "上升", TREND_FLAT: "基本持平"}[segment["trend"]]
    effect = {
        TREND_DOWN: "清疏有效",
        TREND_FLAT: "清疏效果不明显",
        TREND_UP: "淤积反弹",
    }[segment["trend"]]
    headline["conclusion"] = (
        f"淤积由 {previous['淤积值']:g} {previous['单位']} {direction}至 "
        f"{current['淤积值']:g} {current['单位']}，{segment['trend']}，{effect}"
    )
    return headline


def _build_verdict(ordered: list[dict[str, Any]], headline: dict[str, Any]) -> tuple[str, str, str]:
    """复查验收结论，与趋势图/列表共用 headline，不另行判读。"""
    if not ordered:
        return VERDICT_IDLE, "idle", "暂无测量数据，无法形成淤积变化结论"
    if len(ordered) < 2:
        return VERDICT_HOLD, "hold", f"{headline['conclusion']}，暂缓验收，需补测后再复核"
    if not headline["comparable"]:
        return VERDICT_HOLD, "hold", f"{headline['conclusion']}，暂缓验收，需补测或统一单位后再复核"
    if headline["trend"] == TREND_DOWN:
        return VERDICT_PASS, "pass", f"{headline['conclusion']}，复查验收通过"
    if headline["trend"] == TREND_UP:
        return VERDICT_FAIL_UP, "fail", f"{headline['conclusion']}，复查验收不通过，需重新清疏"
    return VERDICT_FAIL_FLAT, "fail", f"{headline['conclusion']}，复查验收不通过，需重新清疏"


def _build_summary(ordered: list[dict[str, Any]], headline: dict[str, Any]) -> tuple[str, str]:
    """任务列表「淤积变化结论」列使用的短结论，口径与验收结论完全一致。"""
    if not ordered:
        return "none", "暂无测量"
    if len(ordered) < 2 or not headline["comparable"]:
        return "hold", "数据不可比"
    return {
        TREND_DOWN: ("down", "淤积减轻"),
        TREND_UP: ("up", "淤积加重"),
        TREND_FLAT: ("flat", "基本持平"),
    }[headline["trend"]]


def build_profile(entry: dict[str, Any]) -> dict[str, Any]:
    """计算单条清疏任务的淤积变化剖面（趋势点、不可比区间、前后结论、验收结论）。"""
    raw_points = entry.get("淤积测量") or []
    points = [_normalize_point(index, raw) for index, raw in enumerate(raw_points, start=1)]

    # 时间可解析的按时间排序；时间缺失的排到末尾并保留相对顺序，便于曲线仍能标出缺口
    dated = sorted((point for point in points if point["_date"] is not None), key=lambda item: item["_date"])
    undated = [point for point in points if point["_date"] is None]
    ordered = dated + undated
    for index, point in enumerate(ordered, start=1):
        point["seq"] = index

    segments = [_build_segment(ordered[index - 1], ordered[index]) for index in range(1, len(ordered))]
    headline = _build_headline(ordered, segments)
    verdict, tone, conclusion = _build_verdict(ordered, headline)
    summary_key, summary_text = _build_summary(ordered, headline)

    profile = {
        "points": [_public_point(point) for point in ordered],
        "segments": segments,
        "headline": headline,
        "verdict": verdict,
        "verdict_tone": tone,
        "conclusion": conclusion,
        "summary_key": summary_key,
        "summary_text": summary_text,
        "max_gap_days": MAX_MEASURE_GAP_DAYS,
        "has_incomparable": any(not segment["comparable"] for segment in segments),
    }
    result = dict(entry)
    result[PROFILE_KEY] = profile
    return result


def list_summary(entry: dict[str, Any]) -> dict[str, Any]:
    """列表行附加的统一结论字段；只取 build_profile 的结果，不在列表侧另算趋势。"""
    profile = build_profile(entry)[PROFILE_KEY]
    return {
        "淤积变化结论": profile["summary_text"],
        "结论标识": profile["summary_key"],
        "结论说明": profile["headline"]["conclusion"],
        "存在不可比区间": profile["has_incomparable"],
        "验收结论": entry.get("验收结论"),
        "验收时间": entry.get("验收时间"),
    }


def status_for_verdict(tone: str) -> dict[str, Any]:
    """验收结论映射回任务状态：通过即闭环；不可比/不通过都转「需复查」并标异常。"""
    if tone == "pass":
        return {"status": "已清疏", "pending": False, "abnormal": False}
    return {"status": "需复查", "pending": True, "abnormal": True}
