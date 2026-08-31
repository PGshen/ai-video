from collections.abc import AsyncIterator

import httpx

from app.engines.ai.base import CompletionText
from app.engines.ai.live_preview import LiveLLMPreview
from app.engines.ai.streaming import iter_openai_sse


class OpenRouterClient:
    engine_name = "openrouter"
    supports_json_schema = True

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://openrouter.ai/api/v1",
        timeout_seconds: float = 60.0,
        site_url: str = "",
        site_name: str = "",
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is required")
        self.api_key = api_key
        self._model_name = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.site_url = site_url
        self.site_name = site_name
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
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if response_format is not None:
            payload["response_format"] = response_format
            if response_format.get("type") == "json_schema":
                # Do not route to an upstream provider that would ignore the schema.
                payload["provider"] = {"require_parameters": True}
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        preview = LiveLLMPreview(
            provider=self.engine_name, model=self.model_name, messages=messages
        )
        chunks: list[str] = []
        usage = None
        try:
            async with self._new_client() as client:
                async with client.stream(
                    "POST", "/chat/completions", json=payload, headers=self._headers()
                ) as response:
                    self._raise_for_status(response)
                    async for content, chunk_usage in iter_openai_sse(response):
                        if chunk_usage is not None:
                            usage = chunk_usage
                        if content:
                            chunks.append(content)
                            preview.append(content)
        except BaseException as exc:
            preview.fail(exc)
            raise
        content = "".join(chunks)
        if not content:
            exc = ValueError("OpenRouter returned empty content")
            preview.fail(exc)
            raise exc
        preview.finish(chunks=len(chunks), content_len=len(content))
        return CompletionText(content, usage)

    async def stream_chat_completion(self, messages: list[dict]) -> AsyncIterator[str]:
        payload: dict = {
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
                async with client.stream(
                    "POST", "/chat/completions", json=payload, headers=self._headers()
                ) as response:
                    self._raise_for_status(response)
                    async for content, usage in iter_openai_sse(response):
                        if isinstance(usage, dict) and not content:
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

    def _new_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout_seconds,
            transport=self._transport,
        )

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.site_url:
            headers["HTTP-Referer"] = self.site_url
        if self.site_name:
            headers["X-Title"] = self.site_name
        return headers

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
                f"OpenRouter API request failed ({exc.response.status_code}): {body}"
            ) from exc
