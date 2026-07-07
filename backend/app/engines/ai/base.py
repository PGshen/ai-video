import asyncio
import json
import logging
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol, AsyncIterator
from dataclasses import dataclass

from sqlalchemy import update

logger = logging.getLogger(__name__)

_ai_business: ContextVar[str] = ContextVar("ai_business", default="unknown")


@contextmanager
def ai_business(name: str):
    """Attach a business purpose to every model call made in this context."""
    token = _ai_business.set(name)
    try:
        yield
    finally:
        _ai_business.reset(token)


class CompletionText(str):
    """A string response carrying provider metadata without breaking callers."""

    usage: dict[str, Any] | None

    def __new__(
        cls, content: str, usage: dict[str, Any] | None = None
    ) -> "CompletionText":
        value = super().__new__(cls, content)
        value.usage = usage
        return value


def completion_text(content: str, response: dict[str, Any]) -> CompletionText:
    usage = response.get("usage")
    return CompletionText(content, usage if isinstance(usage, dict) else None)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _number(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _money(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def normalize_usage(
    usage: dict[str, Any] | None,
    pricing_per_million: dict[str, Decimal] | None = None,
) -> dict[str, Any]:
    usage = usage or {}
    prompt_details = usage.get("prompt_tokens_details") or {}
    completion_details = usage.get("completion_tokens_details") or {}
    cost_details = usage.get("cost_details") or {}
    prompt_tokens = _number(usage.get("prompt_tokens", usage.get("input_tokens")))
    completion_tokens = _number(
        usage.get("completion_tokens", usage.get("output_tokens"))
    )
    total_tokens = _number(usage.get("total_tokens"))
    if total_tokens is None and prompt_tokens is not None and completion_tokens is not None:
        total_tokens = prompt_tokens + completion_tokens
    input_cost = _money(
        usage.get("input_cost", usage.get("prompt_cost", cost_details.get("prompt_cost")))
    )
    output_cost = _money(
        usage.get(
            "output_cost",
            usage.get("completion_cost", cost_details.get("completion_cost")),
        )
    )
    total_cost = _money(
        usage.get(
            "cost",
            usage.get("total_cost", cost_details.get("upstream_inference_cost")),
        )
    )
    cached_tokens = _number(
        prompt_details.get(
            "cached_tokens",
            usage.get(
                "prompt_cache_hit_tokens",
                usage.get("cache_read_input_tokens"),
            ),
        )
    )
    if pricing_per_million:
        million = Decimal(1_000_000)
        cached = cached_tokens or 0
        uncached = max((prompt_tokens or 0) - cached, 0)
        if input_cost is None and prompt_tokens is not None:
            input_cost = (
                Decimal(uncached) * pricing_per_million.get("input", Decimal(0))
                + Decimal(cached)
                * pricing_per_million.get(
                    "cached_input", pricing_per_million.get("input", Decimal(0))
                )
            ) / million
        if output_cost is None and completion_tokens is not None:
            output_cost = (
                Decimal(completion_tokens)
                * pricing_per_million.get("output", Decimal(0))
                / million
            )
        if total_cost is None and (input_cost is not None or output_cost is not None):
            total_cost = (input_cost or Decimal(0)) + (output_cost or Decimal(0))
    return {
        "usage": _json_safe(usage) if usage else None,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "cached_tokens": cached_tokens,
        "reasoning_tokens": _number(
            completion_details.get(
                "reasoning_tokens", usage.get("reasoning_tokens")
            )
        ),
        "input_cost": input_cost,
        "output_cost": output_cost,
        "total_cost": total_cost,
    }


class RecordingChatClient:
    """Best-effort, independent-transaction audit wrapper for ChatClient."""

    def __init__(
        self,
        client: "ChatClient",
        pricing_per_million: dict[str, float] | None = None,
    ):
        self.client = client
        configured_pricing = {
            key: Decimal(str(value))
            for key, value in (pricing_per_million or {}).items()
        }
        self.pricing_per_million = (
            configured_pricing
            if any(value > 0 for value in configured_pricing.values())
            else {}
        )

    @property
    def engine_name(self) -> str:
        return self.client.engine_name

    @property
    def model_name(self) -> str:
        return self.client.model_name

    @property
    def supports_json_schema(self) -> bool:
        return self.client.supports_json_schema

    async def _create_record(
        self,
        request_type: str,
        payload: dict[str, Any],
        business: str,
    ) -> uuid.UUID:
        from app.db import AsyncSessionLocal
        from app.models.ai_call_record import AICallRecord

        record_id = uuid.uuid4()
        try:
            async with AsyncSessionLocal() as db:
                db.add(
                    AICallRecord(
                        id=record_id,
                        provider=self.engine_name,
                        model=self.model_name,
                        business=business,
                        request_type=request_type,
                        status="pending",
                        input=_json_safe(payload),
                    )
                )
                await db.commit()
        except Exception:
            logger.exception("Could not persist pending AI call record %s", record_id)
        return record_id

    async def _finish_record(
        self,
        record_id: uuid.UUID,
        *,
        status: str,
        started: float,
        output: str,
        usage: dict[str, Any] | None = None,
        error: BaseException | None = None,
    ) -> None:
        from app.db import AsyncSessionLocal
        from app.models.ai_call_record import AICallRecord

        values = {
            "status": status,
            "output": output,
            "duration_ms": round((time.monotonic() - started) * 1000),
            "completed_at": datetime.now(timezone.utc),
            "error_type": type(error).__name__ if error else None,
            "error_message": str(error) if error else None,
            **normalize_usage(usage, self.pricing_per_million),
        }
        try:
            async with AsyncSessionLocal() as db:
                await db.execute(
                    update(AICallRecord)
                    .where(AICallRecord.id == record_id)
                    .values(**values)
                )
                await db.commit()
        except Exception:
            logger.exception("Could not finalize AI call record %s", record_id)

    async def create_chat_completion(
        self,
        messages: list[dict],
        response_format: dict | None = None,
        max_tokens: int | None = None,
    ) -> str:
        payload = {
            "messages": messages,
            "response_format": response_format,
            "max_tokens": max_tokens,
        }
        record_id = await self._create_record(
            "chat", payload, business=_ai_business.get()
        )
        started = time.monotonic()
        try:
            result = await self.client.create_chat_completion(
                messages=messages,
                response_format=response_format,
                max_tokens=max_tokens,
            )
        except asyncio.CancelledError as exc:
            await self._finish_record(
                record_id, status="cancelled", started=started, output="", error=exc
            )
            raise
        except Exception as exc:
            status = (
                "timeout"
                if isinstance(exc, TimeoutError) or "timeout" in type(exc).__name__.lower()
                else "failed"
            )
            await self._finish_record(
                record_id, status=status, started=started, output="", error=exc
            )
            raise
        await self._finish_record(
            record_id,
            status="succeeded",
            started=started,
            output=str(result),
            usage=getattr(result, "usage", None),
        )
        return result

    async def stream_chat_completion(
        self, messages: list[dict]
    ) -> AsyncIterator[str]:
        record_id = await self._create_record(
            "stream", {"messages": messages}, business=_ai_business.get()
        )
        started = time.monotonic()
        chunks: list[str] = []
        usage: dict[str, Any] | None = None
        try:
            async for chunk in self.client.stream_chat_completion(messages):
                chunks.append(str(chunk))
                usage = getattr(chunk, "usage", None) or usage
                if chunk:
                    yield chunk
        except GeneratorExit as exc:
            await self._finish_record(
                record_id,
                status="cancelled",
                started=started,
                output="".join(chunks),
                usage=usage,
                error=exc,
            )
            raise
        except asyncio.CancelledError as exc:
            await self._finish_record(
                record_id,
                status="cancelled",
                started=started,
                output="".join(chunks),
                usage=usage,
                error=exc,
            )
            raise
        except Exception as exc:
            status = (
                "timeout"
                if isinstance(exc, TimeoutError) or "timeout" in type(exc).__name__.lower()
                else "failed"
            )
            await self._finish_record(
                record_id,
                status=status,
                started=started,
                output="".join(chunks),
                usage=usage,
                error=exc,
            )
            raise
        else:
            await self._finish_record(
                record_id,
                status="succeeded",
                started=started,
                output="".join(chunks),
                usage=usage,
            )


@dataclass
class BrainstormResult:
    candidates: list[dict]


@dataclass
class NarrativeResult:
    scenes: list[dict]
    fact_checks: list[dict]


@dataclass
class CodeGenerationResult:
    codes: list[str]


@dataclass
class CodeRepairResult:
    repairs: list[dict]


@dataclass
class StyleAssistantResult:
    reply: str
    name: str
    description: str
    prompt_text: str


class ChatClient(Protocol):
    @property
    def engine_name(self) -> str: ...

    @property
    def model_name(self) -> str: ...

    @property
    def supports_json_schema(self) -> bool: ...

    async def create_chat_completion(
        self,
        messages: list[dict],
        response_format: dict | None = None,
        max_tokens: int | None = None,
    ) -> str: ...

    async def stream_chat_completion(
        self,
        messages: list[dict],
    ) -> AsyncIterator[str]: ...


class AIProvider(Protocol):
    @property
    def engine_name(self) -> str: ...

    @property
    def model_name(self) -> str: ...
    
    async def generate_narrative(
        self,
        topic_title: str,
        topic_description: str,
        render_engine: str,
        rejection_context: dict | None = None,
        narrative_context: list[dict] | None = None,
        style_components: dict[str, str] | None = None,
        aspect_ratio: str = "landscape",
    ) -> NarrativeResult: ...

    async def generate_code(
        self,
        scenes: list[dict],
        render_engine: str,
        style_components: dict[str, str] | None = None,
        aspect_ratio: str = "landscape",
        rejection_context: dict | None = None,
    ) -> CodeGenerationResult: ...

    async def repair_code(
        self,
        scenes: list[dict],
        render_engine: str,
        error_message: str,
        style_components: dict[str, str] | None = None,
        aspect_ratio: str = "landscape",
    ) -> CodeRepairResult: ...

    async def brainstorm_topics(
        self,
        topic_direction: str,
        count: int,
    ) -> BrainstormResult: ...

    async def research_topic(
        self,
        topic_title: str,
        topic_description: str,
        conversation_history: list[dict],
        new_message: str,
        use_default_prompt: bool = False,
        system_prompt: str | None = None,
    ) -> AsyncIterator[str]: ...

    async def assist_style_prompt(
        self,
        category: str,
        name: str,
        description: str,
        prompt_text: str,
        conversation_history: list[dict],
        new_message: str,
    ) -> StyleAssistantResult: ...
