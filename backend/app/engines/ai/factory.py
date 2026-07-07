from app.config import settings
from app.engines.ai.base import AIProvider, RecordingChatClient
from app.engines.ai.chat_provider import ChatAIProvider
from app.engines.ai.deepseek import DeepSeekClient
from app.engines.ai.doubao import DoubaoClient
from app.engines.ai.gemini import GeminiClient
from app.engines.ai.openrouter import OpenRouterClient
from app.engines.ai.stub import StubProvider


def get_ai_provider() -> AIProvider:
    provider = settings.AI_PROVIDER.lower()
    if provider == "deepseek" and settings.DEEPSEEK_API_KEY:
        return ChatAIProvider(
            client=RecordingChatClient(
                DeepSeekClient(
                    api_key=settings.DEEPSEEK_API_KEY,
                    base_url=settings.DEEPSEEK_BASE_URL,
                    model=settings.DEEPSEEK_MODEL,
                    timeout_seconds=settings.DEEPSEEK_TIMEOUT_SECONDS,
                ),
                pricing_per_million={
                    "input": settings.DEEPSEEK_INPUT_COST_PER_MILLION,
                    "cached_input": settings.DEEPSEEK_CACHED_INPUT_COST_PER_MILLION,
                    "output": settings.DEEPSEEK_OUTPUT_COST_PER_MILLION,
                },
            ),
            content_max_tokens=settings.DEEPSEEK_CONTENT_MAX_TOKENS,
            json_max_tokens=settings.DEEPSEEK_JSON_MAX_TOKENS,
        )
    if provider == "openrouter" and settings.OPENROUTER_API_KEY:
        return ChatAIProvider(
            client=RecordingChatClient(
                OpenRouterClient(
                    api_key=settings.OPENROUTER_API_KEY,
                    base_url=settings.OPENROUTER_BASE_URL,
                    model=settings.OPENROUTER_MODEL,
                    timeout_seconds=settings.OPENROUTER_TIMEOUT_SECONDS,
                    site_url=settings.OPENROUTER_SITE_URL,
                    site_name=settings.OPENROUTER_SITE_NAME,
                ),
                pricing_per_million={
                    "input": settings.OPENROUTER_INPUT_COST_PER_MILLION,
                    "cached_input": settings.OPENROUTER_CACHED_INPUT_COST_PER_MILLION,
                    "output": settings.OPENROUTER_OUTPUT_COST_PER_MILLION,
                },
            ),
            content_max_tokens=settings.OPENROUTER_CONTENT_MAX_TOKENS,
            json_max_tokens=settings.OPENROUTER_JSON_MAX_TOKENS,
        )
    if provider == "gemini" and settings.GEMINI_API_KEY:
        return ChatAIProvider(
            client=RecordingChatClient(
                GeminiClient(
                    api_key=settings.GEMINI_API_KEY,
                    base_url=settings.GEMINI_BASE_URL,
                    model=settings.GEMINI_MODEL,
                    timeout_seconds=settings.GEMINI_TIMEOUT_SECONDS,
                ),
                pricing_per_million={
                    "input": settings.GEMINI_INPUT_COST_PER_MILLION,
                    "cached_input": settings.GEMINI_CACHED_INPUT_COST_PER_MILLION,
                    "output": settings.GEMINI_OUTPUT_COST_PER_MILLION,
                },
            ),
            content_max_tokens=settings.GEMINI_CONTENT_MAX_TOKENS,
            json_max_tokens=settings.GEMINI_JSON_MAX_TOKENS,
        )
    if provider == "doubao" and settings.DOUBAO_API_KEY:
        return ChatAIProvider(
            client=RecordingChatClient(
                DoubaoClient(
                    api_key=settings.DOUBAO_API_KEY,
                    base_url=settings.DOUBAO_BASE_URL,
                    model=settings.DOUBAO_MODEL,
                    timeout_seconds=settings.DOUBAO_TIMEOUT_SECONDS,
                ),
                pricing_per_million={
                    "input": settings.DOUBAO_INPUT_COST_PER_MILLION,
                    "cached_input": settings.DOUBAO_CACHED_INPUT_COST_PER_MILLION,
                    "output": settings.DOUBAO_OUTPUT_COST_PER_MILLION,
                },
            ),
            content_max_tokens=settings.DOUBAO_CONTENT_MAX_TOKENS,
            json_max_tokens=settings.DOUBAO_JSON_MAX_TOKENS,
        )
    return StubProvider()
