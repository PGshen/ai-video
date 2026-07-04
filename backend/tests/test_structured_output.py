import json
from unittest.mock import AsyncMock

import httpx
import pytest

from app.engines.ai.chat_provider import ChatAIProvider
from app.engines.ai.gemini import GeminiClient
from app.engines.ai.openrouter import OpenRouterClient
from app.engines.ai.structured_output import (
    CODE_GENERATION_SCHEMA,
    NARRATIVE_SCHEMA,
    response_format_for,
)
from app.engines.ai.stub import StubChatClient


def test_response_format_uses_strict_json_schema_for_capable_clients():
    response_format = response_format_for(
        StubChatClient(),
        name="narrative",
        schema=NARRATIVE_SCHEMA,
    )

    assert response_format == {
        "type": "json_schema",
        "json_schema": {
            "name": "narrative",
            "strict": True,
            "schema": NARRATIVE_SCHEMA,
        },
    }


def test_response_format_falls_back_to_json_object_for_unsupported_clients():
    class JsonOnlyClient:
        supports_json_schema = False

    assert response_format_for(
        JsonOnlyClient(),  # type: ignore[arg-type]
        name="result",
        schema={"type": "object"},
    ) == {"type": "json_object"}


@pytest.mark.asyncio
async def test_chat_provider_sends_operation_specific_schema():
    client = StubChatClient()
    client.create_chat_completion = AsyncMock(
        return_value=json.dumps({"codes": ["first", "second"]})
    )

    await ChatAIProvider(client).generate_code(
        scenes=[{"scene_index": 0}, {"scene_index": 1}],
        render_engine="manim",
    )

    response_format = client.create_chat_completion.await_args.kwargs["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True
    assert response_format["json_schema"]["schema"] == CODE_GENERATION_SCHEMA


@pytest.mark.asyncio
async def test_gemini_forwards_openai_compatible_json_schema():
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["response_format"]["type"] == "json_schema"
        assert payload["response_format"]["json_schema"]["strict"] is True
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"codes":["ok"]}'}}]},
        )

    client = GeminiClient(
        api_key="test-key",
        model="gemini-2.5-flash",
        transport=httpx.MockTransport(handler),
    )
    await client.create_chat_completion(
        messages=[{"role": "user", "content": "JSON"}],
        response_format=response_format_for(
            client,
            name="code_generation",
            schema=CODE_GENERATION_SCHEMA,
        ),
    )


@pytest.mark.asyncio
async def test_openrouter_requires_schema_capable_upstream_provider():
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["response_format"]["type"] == "json_schema"
        assert payload["provider"] == {"require_parameters": True}
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"codes":["ok"]}'}}]},
        )

    client = OpenRouterClient(
        api_key="test-key",
        model="anthropic/claude-sonnet-4-5",
        transport=httpx.MockTransport(handler),
    )
    await client.create_chat_completion(
        messages=[{"role": "user", "content": "JSON"}],
        response_format=response_format_for(
            client,
            name="code_generation",
            schema=CODE_GENERATION_SCHEMA,
        ),
    )


@pytest.mark.asyncio
async def test_brainstorm_rejects_invalid_candidate_even_in_json_only_mode():
    class InvalidJsonOnlyClient:
        engine_name = "json-only"
        model_name = "json-only-model"
        supports_json_schema = False

        async def create_chat_completion(self, **kwargs):
            assert kwargs["response_format"] == {"type": "json_object"}
            return '{"candidates":[{"title":"缺少字段"}]}'

    with pytest.raises(ValueError, match="Invalid brainstorm candidate"):
        await ChatAIProvider(InvalidJsonOnlyClient()).brainstorm_topics("科学", 1)
