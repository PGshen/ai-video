import json
from collections.abc import AsyncIterator

import httpx


class DeepSeekClient:
    engine_name = "deepseek"

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://api.deepseek.com",
        timeout_seconds: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        if not api_key:
            raise ValueError("DEEPSEEK_API_KEY is required")
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
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
        }
        if response_format is not None:
            payload["response_format"] = response_format
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        async with self._new_client() as client:
            response = await client.post("/chat/completions", json=payload, headers=self._headers())
        self._raise_for_status(response)
        data = response.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("Unexpected DeepSeek chat completion response") from exc
        if not content:
            raise ValueError("DeepSeek returned empty content")
        return content

    async def stream_chat_completion(self, messages: list[dict]) -> AsyncIterator[str]:
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": True,
        }
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
                        delta = data["choices"][0].get("delta") or {}
                    except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                        continue
                    content = delta.get("content")
                    if content:
                        yield content

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
                f"DeepSeek API request failed ({exc.response.status_code}): {body}"
            ) from exc
