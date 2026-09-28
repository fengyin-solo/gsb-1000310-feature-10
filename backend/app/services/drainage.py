"""排水清疏业务规则：状态流转、字段校验与筛选口径都收在这里。

淤积变化（前后两次测量）的趋势与验收结论统一由 app.profile 计算，列表、剖面、
复查验收三处共用同一份结果，避免各算一套。
"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.profile import PROFILE_KEY, build_profile, list_summary, status_for_verdict
from app.store import store

MODULE = "drainage"
REQUIRED_FIELDS = ["清疏编号", "清疏管段", "淤积程度"]
STATUS_ORDER = ["待清疏", "清疏中", "已清疏", "需复查"]
# 安排/开始两类动作只做状态推进；复查验收的目标状态由淤积剖面结论决定
DIRECT_ACTIONS = {"安排清疏": "清疏中", "开始清疏": "已清疏"}
RECHECK_ACTION = "复查验收"
NEGATIVE_ACTIONS = []


class DrainageService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
        with_summary: bool = True,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("清疏编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        page_rows = [dict(row) for row in rows[start:start + size]]
        if with_summary:
            for row in page_rows:
                row.update(list_summary(row))
        return page_rows, total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        row = store.find(MODULE, entry_id)
        if row is None:
            return None
        entry = dict(row)
        entry.update(list_summary(entry))
        return entry

    def get_profile(self, entry_id: int) -> dict[str, Any] | None:
        row = store.find(MODULE, entry_id)
        if row is None:
            return None
        return build_profile(row)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        entry["淤积测量"] = []
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"清疏任务 {entry_id} 不存在或已归档"
        if action == RECHECK_ACTION:
            return self._run_recheck(entry)
        if action not in DIRECT_ACTIONS:
            return None, f"动作「{action}」不属于排水清疏可执行范围"
        target = DIRECT_ACTIONS[action]
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"清疏任务已{action}"

    def _run_recheck(self, entry: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        """复查验收：直接采用淤积剖面结论，验收结果与趋势图/列表完全同源。"""
        profile = build_profile(entry)[PROFILE_KEY]
        mapping = status_for_verdict(profile["verdict_tone"])
        entry["status"] = mapping["status"]
        entry["pending"] = mapping["pending"]
        entry["abnormal"] = mapping["abnormal"]
        entry["验收结论"] = profile["verdict"]
        entry["验收说明"] = profile["conclusion"]
        entry["验收时间"] = date.today().isoformat()
        return entry, f"复查验收完成：{profile['verdict']}（{profile['headline']['conclusion']}）"
