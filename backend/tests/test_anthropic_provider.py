import json
from decimal import Decimal

import httpx
import pytest

from app.engines.ai.anthropic import AnthropicClient
from app.engines.ai.factory import ProviderSettings, _chat_provider


def stream_response(*events: dict) -> httpx.Response:
    body = "\n\n".join(
        f"event: {event['type']}\ndata: {json.dumps(event, ensure_ascii=False)}"
        for event in events
    )
    return httpx.Response(200, content=body)


def test_anthropic_provider_uses_native_client_in_prompt_mode():
    provider = _chat_provider(
        ProviderSettings(
            provider_type="anthropic",
            api_key="test-key",
            base_url="",
            model="claude-sonnet-4-6",
            timeout_seconds=30,
            content_max_tokens=8192,
            json_max_tokens=4096,
            input_cost_per_million=Decimal("1"),
            cached_input_cost_per_million=Decimal("0.1"),
            output_cost_per_million=Decimal("2"),
        )
    )

    assert provider.engine_name == "anthropic"
    assert isinstance(provider.client.client, AnthropicClient)


@pytest.mark.asyncio
async def test_anthropic_client_uses_native_messages_stream_and_preserves_usage():
    schema = {
        "type": "object",
        "properties": {"ok": {"type": "boolean"}},
        "required": ["ok"],
        "additionalProperties": False,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.url.path == "/v1/messages"
        assert request.headers["x-api-key"] == "test-key"
        assert request.headers["anthropic-version"] == "2023-06-01"
        assert payload == {
            "model": "claude-sonnet-4-6",
            "messages": [{"role": "user", "content": "hello"}],
            "system": "return JSON",
            "max_tokens": 123,
            "stream": True,
            "output_config": {
                "format": {"type": "json_schema", "schema": schema}
            },
        }
        return stream_response(
            {
                "type": "message_start",
                "message": {
                    "usage": {
                        "input_tokens": 12,
                        "cache_read_input_tokens": 4,
                    }
                },
            },
            {
                "type": "content_block_delta",
                "delta": {"type": "text_delta", "text": '{"ok":'},
            },
            {
                "type": "content_block_delta",
                "delta": {"type": "text_delta", "text": "true}"},
            },
            {"type": "message_delta", "usage": {"output_tokens": 3}},
            {"type": "message_stop"},
        )

    client = AnthropicClient(
        api_key="test-key",
        model="claude-sonnet-4-6",
        transport=httpx.MockTransport(handler),
    )
    content = await client.create_chat_completion(
        messages=[
            {"role": "system", "content": "return JSON"},
            {"role": "user", "content": "hello"},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "result", "strict": True, "schema": schema},
        },
        max_tokens=123,
    )

    assert content == '{"ok":true}'
    assert content.usage == {
        "input_tokens": 12,
        "cache_read_input_tokens": 4,
        "output_tokens": 3,
    }


@pytest.mark.asyncio
async def test_anthropic_custom_v1_base_url_is_not_duplicated():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://gateway.example.com/v1/messages"
        return stream_response(
            {
                "type": "content_block_delta",
                "delta": {"type": "text_delta", "text": "ok"},
            }
        )

    client = AnthropicClient(
        api_key="test-key",
        model="claude-test",
        base_url="https://gateway.example.com/v1",
        transport=httpx.MockTransport(handler),
    )

    assert await client.create_chat_completion(
        messages=[{"role": "user", "content": "hello"}]
    ) == "ok"


@pytest.mark.asyncio
async def test_anthropic_stream_surfaces_api_error_event():
    def handler(request: httpx.Request) -> httpx.Response:
        return stream_response(
            {
                "type": "error",
                "error": {"type": "overloaded_error", "message": "busy"},
            }
        )

    client = AnthropicClient(
        api_key="test-key",
        model="claude-test",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(RuntimeError, match="overloaded_error: busy"):
        await client.create_chat_completion(
            messages=[{"role": "user", "content": "hello"}]
        )
