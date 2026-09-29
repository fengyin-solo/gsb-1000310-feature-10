"""排水清疏接口：维护清疏任务，覆盖安排清疏、开始清疏、复查验收等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.drainage import DrainageService

router = APIRouter(prefix="/api/drainage", tags=["排水清疏"])

service = DrainageService()

LIST_FIELDS = ["清疏编号", "清疏管段", "淤积程度", "清疏方式", "计划日期", "清疏班组", "清出淤泥量", "清疏状态"]
STATUSES = ["待清疏", "清疏中", "已清疏", "需复查"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按清疏编号检索"),
    status: str | None = Query(default=None, description="待清疏、清疏中、已清疏、需复查"),
    pipe_section: str | None = Query(default=None, alias="清疏管段"),
    siltation_level: str | None = Query(default=None, alias="淤积程度"),
    cleaning_method: str | None = Query(default=None, alias="清疏方式"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按清疏编号、状态与管段属性过滤排水清疏列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    filters = {
        "清疏管段": pipe_section,
        "淤积程度": siltation_level,
        "清疏方式": cleaning_method,
    }
    items, total = service.list_entries(
        keyword=keyword,
        status=status,
        filters=filters,
        page=page,
        size=size,
    )
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出排水清疏清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "drainage", "total": total, "items": items}


@router.get("/{entry_id}/profile", response_model=dict)
def get_profile(entry_id: int) -> dict:
    """读取单条任务的前后淤积剖面与统一验收结论。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"清疏任务 {entry_id} 不存在或已归档")
    return entry["淤积变化剖面"]


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条清疏任务明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"清疏任务 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条清疏任务，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="清疏任务已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条清疏任务执行安排清疏、开始清疏、复查验收；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message, ok = service.run_action(entry_id, action)
    if entry is None or not ok:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
