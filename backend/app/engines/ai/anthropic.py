import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.engines.ai.base import CompletionText
from app.engines.ai.live_preview import LiveLLMPreview


class AnthropicClient:
    """Native Anthropic Messages API client for ordinary prompt workflows."""

    engine_name = "anthropic"
    supports_json_schema = True

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "",
        timeout_seconds: float = 600.0,
        default_max_tokens: int = 8192,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is required")
        self.api_key = api_key
        self._model_name = model
        root = (base_url or "https://api.anthropic.com").rstrip("/")
        self.messages_url = root + (
            "/messages" if root.endswith("/v1") else "/v1/messages"
        )
        self.timeout_seconds = timeout_seconds
        self.default_max_tokens = default_max_tokens
        self._transport = transport

    @property
    def model_name(self) -> str:
        return self._model_name

    async def create_chat_completion(
        self,
        messages: list[dict],
        response_format: dict | None = None,
        max_tokens: int | None = None,
    ) -> str:
        payload = self._payload(messages, response_format, max_tokens)
        preview = LiveLLMPreview(
            provider=self.engine_name, model=self.model_name, messages=messages
        )
        chunks: list[str] = []
        usage: dict[str, Any] = {}
        try:
            async with self._new_client() as client:
                async with client.stream(
                    "POST", self.messages_url, json=payload, headers=self._headers()
                ) as response:
                    self._raise_for_status(response)
                    async for content, event_usage in self._iter_sse(response):
                        usage.update(event_usage)
                        if content:
                            chunks.append(content)
                            preview.append(content)
        except BaseException as exc:
            preview.fail(exc)
            raise
        content = "".join(chunks)
        if not content:
            exc = ValueError("Anthropic returned empty content")
            preview.fail(exc)
            raise exc
        preview.finish(chunks=len(chunks), content_len=len(content))
        return CompletionText(content, usage or None)

    async def stream_chat_completion(
        self, messages: list[dict]
    ) -> AsyncIterator[str]:
        payload = self._payload(messages, response_format=None, max_tokens=None)
        preview = LiveLLMPreview(
            provider=self.engine_name, model=self.model_name, messages=messages
        )
        chunk_count = 0
        total_len = 0
        usage: dict[str, Any] = {}
        try:
            async with self._new_client() as client:
                async with client.stream(
                    "POST", self.messages_url, json=payload, headers=self._headers()
                ) as response:
                    self._raise_for_status(response)
                    async for content, event_usage in self._iter_sse(response):
                        usage.update(event_usage)
                        if content:
                            chunk_count += 1
                            total_len += len(content)
                            preview.append(content)
                            yield content
            if usage:
                yield CompletionText("", usage)
        except BaseException as exc:
            preview.fail(exc)
            raise
        preview.finish(chunks=chunk_count, content_len=total_len)

    def _payload(
        self,
        messages: list[dict],
        response_format: dict | None,
        max_tokens: int | None,
    ) -> dict[str, Any]:
        system_parts: list[str] = []
        conversation: list[dict[str, str]] = []
        for message in messages:
            role = message.get("role")
            content = str(message.get("content", ""))
            if role == "system":
                system_parts.append(content)
            elif role in {"user", "assistant"}:
                conversation.append({"role": role, "content": content})
            else:
                raise ValueError(f"Unsupported Anthropic message role: {role}")
        if not conversation:
            raise ValueError("Anthropic requires at least one user or assistant message")

        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": conversation,
            "max_tokens": max_tokens or self.default_max_tokens,
            "stream": True,
        }
        if system_parts:
            payload["system"] = "\n\n".join(system_parts)
        if response_format is not None:
            if response_format.get("type") != "json_schema":
                raise ValueError("Anthropic structured output requires json_schema")
            json_schema = response_format.get("json_schema") or {}
            schema = json_schema.get("schema")
            if not isinstance(schema, dict):
                raise ValueError("Anthropic json_schema is missing schema")
            payload["output_config"] = {
                "format": {"type": "json_schema", "schema": schema}
            }
        return payload

    @staticmethod
    async def _iter_sse(
        response: httpx.Response,
    ) -> AsyncIterator[tuple[str | None, dict[str, Any]]]:
        async for line in response.aiter_lines():
            if not line or not line.startswith("data:"):
                continue
            raw = line.removeprefix("data:").strip()
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                continue
            event_type = event.get("type")
            if event_type == "error":
                error = event.get("error") or {}
                raise RuntimeError(
                    f"Anthropic stream error: {error.get('type', 'unknown')}: "
                    f"{error.get('message', 'unknown error')}"
                )
            if event_type == "content_block_delta":
                delta = event.get("delta") or {}
                if delta.get("type") == "text_delta":
                    yield delta.get("text"), {}
                continue
            if event_type == "message_start":
                usage = (event.get("message") or {}).get("usage") or {}
            elif event_type == "message_delta":
                usage = event.get("usage") or {}
            else:
                usage = {}
            if isinstance(usage, dict) and usage:
                yield None, usage

    def _new_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=self.timeout_seconds,
            transport=self._transport,
        )

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            try:
                body = exc.response.text
            except httpx.ResponseNotRead:
                body = "<streaming response body not read>"
            raise RuntimeError(
                f"Anthropic API request failed ({exc.response.status_code}): {body}"
            ) from exc
