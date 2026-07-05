from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class AICallRecordListItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    id: UUID
    provider: str
    model: str
    business: str
    request_type: str
    status: str
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    cached_tokens: int | None
    reasoning_tokens: int | None
    total_cost: Decimal | None
    currency: str
    duration_ms: int | None
    error_type: str | None
    output_preview: str | None
    started_at: datetime
    completed_at: datetime | None


class AICallRecordDetail(AICallRecordListItem):
    input: dict[str, Any]
    output: str | None
    usage: dict[str, Any] | None
    input_cost: Decimal | None
    output_cost: Decimal | None
    error_message: str | None
    created_at: datetime


class AICallSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    calls: int
    succeeded: int
    failed: int
    total_tokens: int
    total_cost: Decimal
    average_duration_ms: int


class AICallRecordListResponse(BaseModel):
    items: list[AICallRecordListItem]
    total: int
    summary: AICallSummary
