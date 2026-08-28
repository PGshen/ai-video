import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI

from app.engines.ai.base import CompletionText, completion_text

logger = logging.getLogger(__name__)


class OpenAIClient:
    engine_name = "openai"
    supports_json_schema = True

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "",
        timeout_seconds: float = 60.0,
        client_factory=None,
    ):
        if not api_key:
            raise ValueError("OpenAI API key is required")
        self.api_key = api_key
        self._model_name = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._client_factory = client_factory

    @property
    def model_name(self) -> str:
        return self._model_name

    def _new_client(self):
        if self._client_factory is not None:
            return self._client_factory()
        kwargs: dict[str, Any] = {
            "api_key": self.api_key,
            "timeout": self.timeout_seconds,
        }
        if self.base_url:
            kwargs["base_url"] = self.base_url
        return AsyncOpenAI(**kwargs)

    async def create_chat_completion(
        self,
        messages: list[dict],
        response_format: dict | None = None,
        max_tokens: int | None = None,
    ) -> str:
        kwargs: dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
        }
        if response_format is not None:
            kwargs["response_format"] = response_format
        if max_tokens is not None:
            kwargs["max_completion_tokens"] = max_tokens
        logger.info(
            "OpenAI chat completion request: model=%s messages=%d max_tokens=%s",
            self.model_name,
            len(messages),
            max_tokens,
        )
        started = time.monotonic()
        async with self._new_client() as client:
            response = await client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content if response.choices else None
        if not content:
            raise ValueError("OpenAI returned empty content")
        payload = response.model_dump(mode="json")
        logger.info(
            "OpenAI chat completion response: model=%s elapsed=%.2fs content_len=%d",
            self.model_name,
            time.monotonic() - started,
            len(content),
        )
        return completion_text(content, payload)

    async def stream_chat_completion(
        self, messages: list[dict]
    ) -> AsyncIterator[str]:
        kwargs: dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        async with self._new_client() as client:
            stream = await client.chat.completions.create(**kwargs)
            async for chunk in stream:
                usage = chunk.usage.model_dump(mode="json") if chunk.usage else None
                choices = chunk.choices or []
                content = choices[0].delta.content if choices else None
                if usage and not content:
                    yield CompletionText("", usage)
                if content:
                    yield content
