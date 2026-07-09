from datetime import datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_active_user
from app.db import get_async_session
from app.models.ai_call_record import AICallRecord
from app.schemas.ai_call_record import (
    AICallRecordDetail,
    AICallRecordListItem,
    AICallRecordListResponse,
    AICallSummary,
)

router = APIRouter(prefix="/api/ai-call-records", tags=["ai-call-records"])


def _filters(
    status: str | None,
    provider: str | None,
    business: str | None,
    model: str | None,
    started_after: datetime | None,
    started_before: datetime | None,
) -> list:
    clauses = []
    if status:
        clauses.append(AICallRecord.status == status)
    if provider:
        clauses.append(AICallRecord.provider == provider)
    if business:
        clauses.append(AICallRecord.business == business)
    if model:
        clauses.append(AICallRecord.model.ilike(f"%{model}%"))
    if started_after:
        clauses.append(AICallRecord.started_at >= started_after)
    if started_before:
        clauses.append(AICallRecord.started_at <= started_before)
    return clauses


def _list_item(record: AICallRecord) -> AICallRecordListItem:
    output_preview = record.output[:240] if record.output else None
    return AICallRecordListItem(
        id=record.id,
        provider=record.provider,
        model=record.model,
        business=record.business,
        request_type=record.request_type,
        status=record.status,
        prompt_tokens=record.prompt_tokens,
        completion_tokens=record.completion_tokens,
        total_tokens=record.total_tokens,
        cached_tokens=record.cached_tokens,
        reasoning_tokens=record.reasoning_tokens,
        total_cost=record.total_cost,
        currency=record.currency,
        duration_ms=record.duration_ms,
        error_type=record.error_type,
        output_preview=output_preview,
        started_at=record.started_at,
        completed_at=record.completed_at,
    )


@router.get("", response_model=AICallRecordListResponse)
async def list_ai_call_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    provider: str | None = None,
    business: str | None = None,
    model: str | None = None,
    started_after: datetime | None = None,
    started_before: datetime | None = None,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(require_active_user),
):
    clauses = _filters(
        status, provider, business, model, started_after, started_before
    )
    base = select(AICallRecord).where(*clauses)
    records_result = await db.execute(
        base.order_by(AICallRecord.started_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    records = records_result.scalars().all()

    stats_result = await db.execute(
        select(
            func.count(AICallRecord.id),
            func.coalesce(
                func.sum(case((AICallRecord.status == "succeeded", 1), else_=0)), 0
            ),
            func.coalesce(
                func.sum(
                    case(
                        (
                            AICallRecord.status.in_(["failed", "timeout", "cancelled"]),
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ),
            func.coalesce(func.sum(AICallRecord.total_tokens), 0),
            func.coalesce(func.sum(AICallRecord.total_cost), 0),
            func.coalesce(func.avg(AICallRecord.duration_ms), 0),
        ).where(*clauses)
    )
    calls, succeeded, failed, tokens, cost, avg_duration = stats_result.one()
    return AICallRecordListResponse(
        items=[_list_item(record) for record in records],
        total=int(calls),
        summary=AICallSummary(
            calls=int(calls),
            succeeded=int(succeeded),
            failed=int(failed),
            total_tokens=int(tokens),
            total_cost=Decimal(cost),
            average_duration_ms=round(avg_duration),
        ),
    )


@router.get("/{record_id}", response_model=AICallRecordDetail)
async def get_ai_call_record(
    record_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(require_active_user),
):
    record = await db.get(AICallRecord, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="AI call record not found")
    return AICallRecordDetail(
        **_list_item(record).model_dump(),
        input=record.input,
        output=record.output,
        usage=record.usage,
        input_cost=record.input_cost,
        output_cost=record.output_cost,
        error_message=record.error_message,
        created_at=record.created_at,
    )
