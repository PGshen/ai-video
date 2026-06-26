from app.config import settings
from app.engines.ai.base import AIProvider
from app.engines.ai.chat_provider import ChatAIProvider
from app.engines.ai.deepseek import DeepSeekClient
from app.engines.ai.stub import StubProvider


def get_ai_provider() -> AIProvider:
    provider = settings.AI_PROVIDER.lower()
    if provider == "deepseek" and settings.DEEPSEEK_API_KEY:
        return ChatAIProvider(
            client=DeepSeekClient(
                api_key=settings.DEEPSEEK_API_KEY,
                base_url=settings.DEEPSEEK_BASE_URL,
                model=settings.DEEPSEEK_MODEL,
                timeout_seconds=settings.DEEPSEEK_TIMEOUT_SECONDS,
            ),
            script_max_tokens=settings.DEEPSEEK_SCRIPT_MAX_TOKENS,
            json_max_tokens=settings.DEEPSEEK_JSON_MAX_TOKENS,
        )
    return StubProvider()
