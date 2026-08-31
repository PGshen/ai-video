import json
from collections.abc import AsyncIterator

import httpx


async def iter_openai_sse(
    response: httpx.Response,
) -> AsyncIterator[tuple[str | None, dict | None]]:
    """Yield text and usage from an OpenAI-compatible SSE response."""
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
        yield delta.get("content"), usage if isinstance(usage, dict) else None
