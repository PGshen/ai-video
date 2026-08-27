import json
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.engines.ai.base import (
    CompletionText,
    RecordingChatClient,
    ai_business,
    normalize_usage,
)
from app.engines.ai.chat_provider import ChatAIProvider


class FakeClient:
    engine_name = "fake"
    model_name = "fake-model"
    supports_json_schema = True

    async def create_chat_completion(self, **kwargs):
        return CompletionText(
            "answer",
            {
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "total_tokens": 120,
                "prompt_tokens_details": {"cached_tokens": 40},
                "completion_tokens_details": {"reasoning_tokens": 5},
                "cost": 0.0012,
            },
        )

    async def stream_chat_completion(self, messages):
        yield "part one"
        yield CompletionText("", {"prompt_tokens": 10, "completion_tokens": 2})


@pytest.mark.asyncio
async def test_recording_client_finalizes_success_with_usage():
    client = RecordingChatClient(FakeClient())
    client._create_record = AsyncMock(return_value="record-id")
    client._finish_record = AsyncMock()

    result = await client.create_chat_completion([{"role": "user", "content": "hi"}])

    assert result == "answer"
    finish = client._finish_record.await_args.kwargs
    assert finish["status"] == "succeeded"
    assert finish["output"] == "answer"
    assert finish["usage"]["total_tokens"] == 120


@pytest.mark.asyncio
async def test_recording_client_passes_business_to_pending_record():
    client = RecordingChatClient(FakeClient())
    client._create_record = AsyncMock(return_value="record-id")
    client._finish_record = AsyncMock()

    with ai_business("code_generation"):
        await client.create_chat_completion([])

    assert client._create_record.await_args.kwargs["business"] == "code_generation"


@pytest.mark.asyncio
async def test_recording_client_marks_timeout_and_reraises():
    upstream = FakeClient()
    upstream.create_chat_completion = AsyncMock(side_effect=TimeoutError("too slow"))
    client = RecordingChatClient(upstream)
    client._create_record = AsyncMock(return_value="record-id")
    client._finish_record = AsyncMock()

    with pytest.raises(TimeoutError):
        await client.create_chat_completion([])

    finish = client._finish_record.await_args.kwargs
    assert finish["status"] == "timeout"
    assert isinstance(finish["error"], TimeoutError)


@pytest.mark.asyncio
async def test_recording_client_accumulates_stream_and_usage():
    client = RecordingChatClient(FakeClient())
    client._create_record = AsyncMock(return_value="record-id")
    client._finish_record = AsyncMock()

    chunks = [chunk async for chunk in client.stream_chat_completion([])]

    assert chunks == ["part one"]
    finish = client._finish_record.await_args.kwargs
    assert finish["status"] == "succeeded"
    assert finish["output"] == "part one"
    assert finish["usage"]["completion_tokens"] == 2


def test_normalize_usage_calculates_configured_cost_and_token_details():
    normalized = normalize_usage(
        {
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "prompt_tokens_details": {"cached_tokens": 200},
        },
        {
            "input": Decimal("2"),
            "cached_input": Decimal("0.5"),
            "output": Decimal("8"),
        },
    )

    assert normalized["total_tokens"] == 1500
    assert normalized["cached_tokens"] == 200
    assert normalized["input_cost"] == Decimal("0.0017")
    assert normalized["output_cost"] == Decimal("0.004")
    assert normalized["total_cost"] == Decimal("0.0057")


def test_normalize_usage_accepts_openai_agents_detail_names():
    normalized = normalize_usage(
        {
            "input_tokens": 120,
            "output_tokens": 30,
            "total_tokens": 150,
            "input_tokens_details": {"cached_tokens": 20},
            "output_tokens_details": {"reasoning_tokens": 8},
        }
    )

    assert normalized["cached_tokens"] == 20
    assert normalized["reasoning_tokens"] == 8


@pytest.mark.asyncio
async def test_provider_marks_brainstorm_business():
    upstream = FakeClient()
    upstream.create_chat_completion = AsyncMock(
        return_value=CompletionText(
            json.dumps(
                {
                    "candidates": [
                        {
                            "title": "test",
                            "description": "test",
                            "tags": ["test"],
                        }
                    ]
                }
            )
        )
    )
    client = RecordingChatClient(upstream)
    client._create_record = AsyncMock(return_value="record-id")
    client._finish_record = AsyncMock()

    await ChatAIProvider(client).brainstorm_topics("science", 1)

    assert client._create_record.await_args.kwargs["business"] == "topic_brainstorm"


@pytest.mark.asyncio
async def test_provider_marks_research_stream_business():
    client = RecordingChatClient(FakeClient())
    client._create_record = AsyncMock(return_value="record-id")
    client._finish_record = AsyncMock()
    provider = ChatAIProvider(client)

    chunks = [
        chunk
        async for chunk in provider.research_topic(
            topic_title="topic",
            topic_description="description",
            conversation_history=[],
            new_message="question",
        )
    ]

    assert chunks == ["part one"]
    assert client._create_record.await_args.kwargs["business"] == "topic_research"
