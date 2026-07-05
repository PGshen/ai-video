import json
import logging
import time
from collections.abc import AsyncIterator

import httpx

from app.engines.ai.base import CompletionText, completion_text

logger = logging.getLogger(__name__)


class GeminiClient:
    """Gemini via its OpenAI-compatible REST endpoint."""

    engine_name = "gemini"
    supports_json_schema = True

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai",
        timeout_seconds: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        if not api_key:
            raise ValueError("GEMINI_API_KEY is required")
        self.api_key = api_key
        self._model_name = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
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
        payload: dict = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
        }
        if response_format is not None:
            payload["response_format"] = response_format
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        logger.info(
            "Gemini chat completion request: model=%s messages=%d max_tokens=%s",
            self.model_name, len(messages), max_tokens,
        )
        started = time.monotonic()
        async with self._new_client() as client:
            response = await client.post("/chat/completions", json=payload, headers=self._headers())
        self._raise_for_status(response)
        data = response.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("Unexpected Gemini chat completion response") from exc
        if not content:
            raise ValueError("Gemini returned empty content")
        logger.info(
            "Gemini chat completion response: model=%s elapsed=%.2fs content_len=%d",
            self.model_name, time.monotonic() - started, len(content),
        )
        return completion_text(content, data)

    async def stream_chat_completion(self, messages: list[dict]) -> AsyncIterator[str]:
        payload: dict = {
            "model": self.model_name,
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        logger.info(
            "Gemini stream chat completion request: model=%s messages=%d",
            self.model_name, len(messages),
        )
        started = time.monotonic()
        chunk_count = 0
        total_len = 0
        async with self._new_client() as client:
            async with client.stream(
                "POST",
                "/chat/completions",
                json=payload,
                headers=self._headers(),
            ) as response:
                self._raise_for_status(response)
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    raw = line.removeprefix("data:").strip()
                    if raw == "[DONE]":
                        break
                    try:
                        data = json.loads(raw)
                        choices = data.get("choices") or []
                        delta = choices[0].get("delta") or {} if choices else {}
                    except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                        continue
                    usage = data.get("usage")
                    if isinstance(usage, dict) and not delta.get("content"):
                        yield CompletionText("", usage)
                    content = delta.get("content")
                    if content:
                        chunk_count += 1
                        total_len += len(content)
                        yield content
        logger.info(
            "Gemini stream chat completion done: model=%s elapsed=%.2fs chunks=%d content_len=%d",
            self.model_name, time.monotonic() - started, chunk_count, total_len,
        )

    def _new_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout_seconds,
            transport=self._transport,
        )

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
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
                f"Gemini API request failed ({exc.response.status_code}): {body}"
            ) from exc
