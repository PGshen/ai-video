from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI

from app.engines.ai.base import CompletionText
from app.engines.ai.live_preview import LiveLLMPreview


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
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if response_format is not None:
            kwargs["response_format"] = response_format
        if max_tokens is not None:
            kwargs["max_completion_tokens"] = max_tokens
        preview = LiveLLMPreview(
            provider=self.engine_name, model=self.model_name, messages=messages
        )
        chunks: list[str] = []
        usage = None
        try:
            async with self._new_client() as client:
                stream = await client.chat.completions.create(**kwargs)
                async for chunk in stream:
                    chunk_usage = (
                        chunk.usage.model_dump(mode="json") if chunk.usage else None
                    )
                    if chunk_usage is not None:
                        usage = chunk_usage
                    choices = chunk.choices or []
                    content = choices[0].delta.content if choices else None
                    if content:
                        chunks.append(content)
                        preview.append(content)
        except BaseException as exc:
            preview.fail(exc)
            raise
        content = "".join(chunks)
        if not content:
            exc = ValueError("OpenAI returned empty content")
            preview.fail(exc)
            raise exc
        preview.finish(chunks=len(chunks), content_len=len(content))
        return CompletionText(content, usage)

    async def stream_chat_completion(
        self, messages: list[dict]
    ) -> AsyncIterator[str]:
        kwargs: dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        preview = LiveLLMPreview(
            provider=self.engine_name, model=self.model_name, messages=messages
        )
        chunk_count = 0
        total_len = 0
        try:
            async with self._new_client() as client:
                stream = await client.chat.completions.create(**kwargs)
                async for chunk in stream:
                    usage = (
                        chunk.usage.model_dump(mode="json") if chunk.usage else None
                    )
                    choices = chunk.choices or []
                    content = choices[0].delta.content if choices else None
                    if usage and not content:
                        yield CompletionText("", usage)
                    if content:
                        chunk_count += 1
                        total_len += len(content)
                        preview.append(content)
                        yield content
        except BaseException as exc:
            preview.fail(exc)
            raise
        preview.finish(chunks=chunk_count, content_len=total_len)
