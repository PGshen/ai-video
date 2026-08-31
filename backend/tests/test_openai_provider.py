from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.engines.ai.openai import OpenAIClient


class FakeOpenAIClient:
    def __init__(self, create):
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(create=create),
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False


@pytest.mark.asyncio
async def test_openai_client_uses_chat_completion_shape_and_preserves_usage():
    async def chunks():
        yield SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content='{"ok":'))],
            usage=None,
        )
        yield SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content=" true}"))],
            usage=None,
        )
        yield SimpleNamespace(
            choices=[],
            usage=SimpleNamespace(
                model_dump=lambda **kwargs: {
                    "prompt_tokens": 12,
                    "completion_tokens": 3,
                    "total_tokens": 15,
                }
            ),
        )

    create = AsyncMock(return_value=chunks())
    client = OpenAIClient(
        api_key="test-key",
        model="gpt-5.4",
        client_factory=lambda: FakeOpenAIClient(create),
    )

    content = await client.create_chat_completion(
        messages=[{"role": "user", "content": "hello"}],
        response_format={"type": "json_object"},
        max_tokens=123,
    )

    assert content == '{"ok": true}'
    assert content.usage == {
        "prompt_tokens": 12,
        "completion_tokens": 3,
        "total_tokens": 15,
    }
    assert create.await_args.kwargs == {
        "model": "gpt-5.4",
        "messages": [{"role": "user", "content": "hello"}],
        "stream": True,
        "stream_options": {"include_usage": True},
        "response_format": {"type": "json_object"},
        "max_completion_tokens": 123,
    }


@pytest.mark.asyncio
async def test_openai_client_stream_yields_content_and_usage():
    async def chunks():
        yield SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content="第一段"))],
            usage=None,
        )
        yield SimpleNamespace(
            choices=[],
            usage=SimpleNamespace(
                model_dump=lambda **kwargs: {
                    "prompt_tokens": 4,
                    "completion_tokens": 2,
                    "total_tokens": 6,
                }
            ),
        )

    create = AsyncMock(return_value=chunks())
    client = OpenAIClient(
        api_key="test-key",
        model="gpt-5.4",
        client_factory=lambda: FakeOpenAIClient(create),
    )

    output = []
    usage = None
    async for chunk in client.stream_chat_completion(
        [{"role": "user", "content": "hello"}]
    ):
        output.append(str(chunk))
        usage = getattr(chunk, "usage", None) or usage

    assert output == ["第一段", ""]
    assert usage == {
        "prompt_tokens": 4,
        "completion_tokens": 2,
        "total_tokens": 6,
    }
    assert create.await_args.kwargs["stream"] is True
    assert create.await_args.kwargs["stream_options"] == {"include_usage": True}
