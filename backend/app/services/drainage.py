"""排水清疏业务规则：淤积剖面、状态流转与验收结论统一在这里计算。"""
from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from app.store import store

MODULE = "drainage"
REQUIRED_FIELDS = ["清疏编号", "清疏管段", "淤积程度"]
STATUS_ORDER = ["待清疏", "清疏中", "已清疏", "需复查"]
PENDING_STATUSES = {"待清疏", "清疏中", "需复查"}
ACTION_RULES = {"安排清疏": "清疏中", "开始清疏": "已清疏"}
ACTION_FROM_STATUS = {
    "安排清疏": "待清疏",
    "开始清疏": "清疏中",
}
ACCEPTANCE_STATUSES = {"已清疏", "需复查"}

PROFILE_BEFORE = "清疏前"
PROFILE_AFTER = "清疏后"
CANONICAL_UNIT = "mm"
MAX_POINT_GAP_M = 5.0
# 完整剖面均可比时，平均淤积深度下降达到该比例才允许验收通过。
PASS_REDUCTION_RATE = 0.5
IMPROVEMENT_RATE = 0.1
REBOUND_RATE = -0.1

UNIT_FACTORS = {
    "mm": 1.0,
    "毫米": 1.0,
    "cm": 10.0,
    "厘米": 10.0,
    "m": 1000.0,
    "米": 1000.0,
}


class DrainageService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        filters: dict[str, str] | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("清疏编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        for field, value in (filters or {}).items():
            keyword_value = str(value or "").strip()
            if keyword_value:
                rows = [row for row in rows if keyword_value in str(row.get(field, ""))]
        total = len(rows)
        start = max(page - 1, 0) * size
        return [self._present_entry(row) for row in rows[start:start + size]], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None
        return self._present_entry(entry)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        optional_fields = ["清疏方式", "计划日期", "清疏班组", "清出淤泥量"]
        entry.update({field: values.get(field) for field in optional_fields if values.get(field) is not None})
        entry["status"] = STATUS_ORDER[0]
        entry["清疏状态"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return self._present_entry(entry), []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str, bool]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"清疏任务 {entry_id} 不存在或已归档", False
        if action not in ACTION_RULES and action != "复查验收":
            return None, f"动作「{action}」不属于排水清疏可执行范围", False
        if action == "复查验收":
            if entry.get("status") not in ACCEPTANCE_STATUSES:
                return None, f"当前状态为「{entry.get('status')}」，不能执行复查验收", False
            return self._run_acceptance(entry)

        expected_status = ACTION_FROM_STATUS[action]

        target = ACTION_RULES[action]
        self._set_status(entry, target)
        return self._present_entry(entry), f"清疏任务已{action}", True

    def build_profile(self, entry: dict[str, Any]) -> dict[str, Any]:
        """构造前后两次淤积剖面，并给出趋势图、列表、验收共用的唯一结论。"""
        before = self._read_phase(entry, PROFILE_BEFORE)
        after = self._read_phase(entry, PROFILE_AFTER)
        positions = sorted({point["里程"] for point in before + after if point["里程"] is not None})
        before_by_position = {point["里程"]: point for point in before if point["里程"] is not None}
        after_by_position = {point["里程"]: point for point in after if point["里程"] is not None}

        raw_points = []
        for position in positions:
            before_point = before_by_position.get(position)
            after_point = after_by_position.get(position)
            reasons: list[str] = []
            if before_point is None:
                reasons.append("缺少清疏前历史值")
            if after_point is None:
                reasons.append("缺少清疏后复测值")
            if (
                before_point is not None
                and after_point is not None
                and before_point.get("单位")
                and after_point.get("单位")
                and before_point["单位"] != after_point["单位"]
            ):
                reasons.append("前后测量单位不一致")
            if before_point is not None and before_point.get("数值") is None:
                reasons.append("缺少清疏前历史值")
            if after_point is not None and after_point.get("数值") is None:
                reasons.append("缺少清疏后复测值")
            if before_point is not None and before_point.get("数值") is not None and before_point.get("标准值_mm") is None:
                reasons.append("测量单位缺失或不支持")
            if after_point is not None and after_point.get("数值") is not None and after_point.get("标准值_mm") is None:
                reasons.append("测量单位缺失或不支持")

            raw_points.append({
                "里程": position,
                "清疏前": before_point.get("标准值_mm") if before_point else None,
                "清疏前显示值": before_point.get("数值") if before_point else None,
                "清疏前单位": before_point.get("单位") if before_point else None,
                "清疏后": after_point.get("标准值_mm") if after_point else None,
                "清疏后显示值": after_point.get("数值") if after_point else None,
                "清疏后单位": after_point.get("单位") if after_point else None,
                "测点可比较": not reasons,
                "不可比原因": reasons,
            })

        segments = self._build_segments(raw_points, positions)
        comparable_positions = {
            point["里程"]
            for point in raw_points
            if any(
                segment["可比较"]
                and point["里程"] in (segment["起点里程"], segment["终点里程"])
                for segment in segments
            )
        }
        for point in raw_points:
            point["纳入趋势"] = point["测点可比较"] and point["里程"] in comparable_positions

        statistics = self._build_statistics(raw_points, segments)
        conclusion = self._build_conclusion(statistics, segments)
        return {
            "清疏编号": entry.get("清疏编号"),
            "清疏管段": entry.get("清疏管段"),
            "淤积程度": entry.get("淤积程度"),
            "清疏方式": entry.get("清疏方式"),
            "制图单位": CANONICAL_UNIT,
            "连续测量最大间距_m": MAX_POINT_GAP_M,
            "测点": raw_points,
            "区间": segments,
            "统计": statistics,
            "结论": conclusion,
        }

    def _run_acceptance(self, entry: dict[str, Any]) -> tuple[dict[str, Any], str, bool]:
        profile = self.build_profile(entry)
        conclusion = profile["结论"]
        result = conclusion["结果"]

        if result == "验收通过":
            self._set_status(entry, "已清疏")
            entry["验收结果"] = result
            entry["验收结论"] = conclusion["说明"]
            return self._present_entry(entry), f"复查验收通过：{conclusion['说明']}", True

        target_status = "需复查"
        self._set_status(entry, target_status)
        entry["验收结果"] = result
        entry["验收结论"] = conclusion["说明"]
        return self._present_entry(entry), f"复查未通过：{conclusion['说明']}", False

    def _set_status(self, entry: dict[str, Any], status: str) -> None:
        entry["status"] = status
        entry["清疏状态"] = status
        entry["pending"] = status in PENDING_STATUSES
        entry["abnormal"] = status == "需复查"

    def _present_entry(self, entry: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(entry)
        profile = self.build_profile(entry)
        conclusion = profile["结论"]
        result["淤积变化剖面"] = profile
        result["淤积变化"] = conclusion["趋势"]
        result["验收结果"] = conclusion["结果"]
        result["变化结论"] = conclusion["说明"]
        result["不可比区间数"] = conclusion["不可比区间数"]
        return result

    def _read_phase(self, entry: dict[str, Any], phase_name: str) -> list[dict[str, Any]]:
        profile_data = entry.get("淤积剖面") or {}
        raw_points = profile_data.get(phase_name) if isinstance(profile_data, dict) else None
        if not isinstance(raw_points, list):
            return []

        points = []
        for raw in raw_points:
            if not isinstance(raw, dict):
                continue
            position = self._number(raw.get("里程(m)") if "里程(m)" in raw else raw.get("里程"))
            value = self._number(raw.get("淤积深度") if "淤积深度" in raw else raw.get("数值"))
            unit = self._unit(raw.get("单位", ""))
            point = {
                "里程": position,
                "数值": value,
                "单位": unit,
                "标准值_mm": None,
            }
            if value is not None and unit in UNIT_FACTORS:
                point["标准值_mm"] = round(value * UNIT_FACTORS[unit], 3)
            points.append(point)
        return [point for point in points if point["里程"] is not None]

    @staticmethod
    def _number(value: Any) -> float | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if value is None:
            return None
        match = re.search(r"-?\d+(?:\.\d+)?", str(value).replace(",", ""))
        return float(match.group()) if match else None

    @staticmethod
    def _unit(value: Any) -> str | None:
        text = str(value or "").strip().lower()
        if not text:
            return None
        if "毫米" in text or "mm" in text:
            return "mm"
        if "厘米" in text or "cm" in text:
            return "cm"
        # 先判断 mm，避免 m 命中 mm。
        if "米" in text or re.search(r"(?<![a-z])m(?![a-z])", text):
            return "m"
        return None

    def _build_segments(self, points: list[dict[str, Any]], positions: list[float]) -> list[dict[str, Any]]:
        point_map = {point["里程"]: point for point in points}
        segments = []
        for start, end in zip(positions, positions[1:]):
            start_point = point_map[start]
            end_point = point_map[end]
            reasons: list[str] = []

            for phase in ("清疏前", "清疏后"):
                if start_point.get(phase) is None:
                    reasons.append(f"起点缺少{phase}测量值")
                if end_point.get(phase) is None:
                    reasons.append(f"终点缺少{phase}测量值")
                if start_point.get(f"{phase}单位") and end_point.get(f"{phase}单位"):
                    if start_point[f"{phase}单位"] != end_point[f"{phase}单位"]:
                        reasons.append("连续测量单位不一致")

            if not start_point["测点可比较"] or not end_point["测点可比较"]:
                other_reasons = [
                    reason
                    for point in (start_point, end_point)
                    for reason in point["不可比原因"]
                    if "缺少" not in reason
                ]
                reasons.extend(other_reasons)

            distance = round(end - start, 3)
            if distance > MAX_POINT_GAP_M:
                reasons.append("连续测量断档")

            deduped_reasons = list(dict.fromkeys(reasons))
            segments.append({
                "起点里程": start,
                "终点里程": end,
                "长度_m": distance,
                "可比较": not deduped_reasons,
                "不可比原因": deduped_reasons,
            })
        return segments

    def _build_statistics(
        self, points: list[dict[str, Any]], segments: list[dict[str, Any]]
    ) -> dict[str, Any]:
        trend_points = [point for point in points if point["纳入趋势"]]
        comparable_segments = [segment for segment in segments if segment["可比较"]]
        incomparable_segments = [segment for segment in segments if not segment["可比较"]]

        before_values = [point["清疏前"] for point in trend_points if point["清疏前"] is not None]
        after_values = [point["清疏后"] for point in trend_points if point["清疏后"] is not None]
        avg_before = round(sum(before_values) / len(before_values), 2) if before_values else None
        avg_after = round(sum(after_values) / len(after_values), 2) if after_values else None

        reduction_rate = None
        delta_mm = None
        if avg_before is not None and avg_after is not None:
            delta_mm = round(avg_after - avg_before, 2)
            if avg_before > 0:
                reduction_rate = round((avg_before - avg_after) / avg_before, 4)
            elif avg_after <= 0:
                reduction_rate = 1.0
            else:
                # 从 0 增加到正数，下降率无法表示，按明显反弹处理。
                reduction_rate = -1.0

        if reduction_rate is None:
            trend = "无法判定"
        elif reduction_rate >= IMPROVEMENT_RATE:
            trend = "淤积改善"
        elif reduction_rate <= REBOUND_RATE:
            trend = "淤积反弹"
        else:
            trend = "无明显变化"

        return {
            "可比较区间数": len(comparable_segments),
            "不可比区间数": len(incomparable_segments),
            "可比较长度_m": round(sum(segment["长度_m"] for segment in comparable_segments), 3),
            "纳入趋势测点数": len(trend_points),
            "平均清疏前_mm": avg_before,
            "平均清疏后_mm": avg_after,
            "平均变化_mm": delta_mm,
            "下降率": reduction_rate,
            "趋势": trend,
        }

    def _build_conclusion(
        self, statistics: dict[str, Any], segments: list[dict[str, Any]]
    ) -> dict[str, Any]:
        incomparable = [
            {
                "起点里程": segment["起点里程"],
                "终点里程": segment["终点里程"],
                "长度_m": segment["长度_m"],
                "原因": segment["不可比原因"],
            }
            for segment in segments
            if not segment["可比较"]
        ]
        trend = statistics["趋势"]
        reduction_rate = statistics["下降率"]
        avg_before = statistics["平均清疏前_mm"]
        avg_after = statistics["平均清疏后_mm"]

        if incomparable:
            reasons = list(dict.fromkeys(
                reason
                for segment in incomparable
                for reason in segment["原因"]
            ))
            result = "无法验收"
            message = (
                f"存在 {len(incomparable)} 段不可比区间"
                f"（{'、'.join(reasons)}），不能据此得出验收结论"
            )
        elif trend == "淤积改善" and reduction_rate is not None and reduction_rate >= PASS_REDUCTION_RATE:
            result = "验收通过"
            message = (
                f"清疏后平均淤积深度由 {avg_before}mm 降至 {avg_after}mm，"
                f"下降 {reduction_rate * 100:.1f}%"
            )
        elif trend == "无法判定":
            result = "无法验收"
            message = "缺少可比较的前后历史值，暂不能得出淤积变化结论"
        elif trend == "淤积反弹":
            result = "验收不通过"
            message = (
                f"清疏后淤积反弹，平均淤积深度由 {avg_before}mm 升至 {avg_after}mm，"
                f"增加 {abs(float(statistics['平均变化_mm']))}mm"
            )
        else:
            result = "验收不通过"
            rate_text = "无法计算" if reduction_rate is None else f"{reduction_rate * 100:.1f}%"
            message = f"淤积下降 {rate_text}，未达到 {PASS_REDUCTION_RATE * 100:.0f}% 的验收标准"

        return {
            "结果": result,
            "趋势": trend,
            "说明": message,
            "不可比区间数": len(incomparable),
            "不可比区间": incomparable,
        }
