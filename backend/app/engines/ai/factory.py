import logging
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.db import get_sync_session
from app.engines.ai.base import AIProvider, RecordingChatClient
from app.engines.ai.chat_provider import ChatAIProvider
from app.engines.ai.deepseek import DeepSeekClient
from app.engines.ai.doubao import DoubaoClient
from app.engines.ai.gemini import GeminiClient
from app.engines.ai.openai import OpenAIClient
from app.engines.ai.openrouter import OpenRouterClient
from app.engines.ai.stub import StubProvider
from app.models.ai_model_config import (
    AIBusinessModelConfig,
    AIModelProvider,
    AIProviderModel,
)


logger = logging.getLogger(__name__)

BUSINESS_OPTIONS: tuple[tuple[str, str], ...] = (
    ("default", "默认兜底"),
    ("topic_brainstorm", "选题脑暴"),
    ("topic_research", "选题研究"),
    ("narrative_generation", "叙事生成"),
    ("code_generation", "代码生成"),
    ("code_repair", "代码修复"),
    ("style_assistant", "风格助手"),
)


@dataclass(frozen=True)
class ProviderSettings:
    provider_type: str
    api_key: str
    base_url: str
    model: str
    timeout_seconds: float
    content_max_tokens: int
    json_max_tokens: int
    input_cost_per_million: Decimal
    cached_input_cost_per_million: Decimal
    output_cost_per_million: Decimal
    site_url: str = ""
    site_name: str = ""


def _provider_settings_from_db(business: str | None) -> ProviderSettings | None:
    requested_businesses = [business or "default"]
    if requested_businesses[0] != "default":
        requested_businesses.append("default")

    db = get_sync_session()
    try:
        for business_key in requested_businesses:
            config = db.execute(
                select(AIBusinessModelConfig).where(
                    AIBusinessModelConfig.business == business_key
                )
            ).scalar_one_or_none()
            if config is None:
                continue
            model = db.get(AIProviderModel, config.model_id)
            if model is None or not model.is_active:
                continue
            provider = db.get(AIModelProvider, model.provider_id)
            if provider is None or not provider.is_active or not provider.api_key:
                continue
            return ProviderSettings(
                provider_type=provider.provider_type.lower(),
                api_key=provider.api_key,
                base_url=provider.base_url,
                model=model.model,
                timeout_seconds=provider.timeout_seconds,
                content_max_tokens=model.content_max_tokens,
                json_max_tokens=model.json_max_tokens,
                input_cost_per_million=model.input_cost_per_million,
                cached_input_cost_per_million=model.cached_input_cost_per_million,
                output_cost_per_million=model.output_cost_per_million,
                site_url=provider.site_url or "",
                site_name=provider.site_name or "",
            )
    except SQLAlchemyError:
        logger.exception("Could not load AI model settings; falling back to env")
    finally:
        db.close()
    return None


def _provider_settings_from_env() -> ProviderSettings | None:
    provider = settings.AI_PROVIDER.lower()
    if provider == "deepseek" and settings.DEEPSEEK_API_KEY:
        return ProviderSettings(
            provider_type=provider,
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            model=settings.DEEPSEEK_MODEL,
            timeout_seconds=settings.DEEPSEEK_TIMEOUT_SECONDS,
            content_max_tokens=settings.DEEPSEEK_CONTENT_MAX_TOKENS,
            json_max_tokens=settings.DEEPSEEK_JSON_MAX_TOKENS,
            input_cost_per_million=Decimal(str(settings.DEEPSEEK_INPUT_COST_PER_MILLION)),
            cached_input_cost_per_million=Decimal(str(settings.DEEPSEEK_CACHED_INPUT_COST_PER_MILLION)),
            output_cost_per_million=Decimal(str(settings.DEEPSEEK_OUTPUT_COST_PER_MILLION)),
        )
    if provider == "openrouter" and settings.OPENROUTER_API_KEY:
        return ProviderSettings(
            provider_type=provider,
            api_key=settings.OPENROUTER_API_KEY,
            base_url=settings.OPENROUTER_BASE_URL,
            model=settings.OPENROUTER_MODEL,
            timeout_seconds=settings.OPENROUTER_TIMEOUT_SECONDS,
            content_max_tokens=settings.OPENROUTER_CONTENT_MAX_TOKENS,
            json_max_tokens=settings.OPENROUTER_JSON_MAX_TOKENS,
            input_cost_per_million=Decimal(str(settings.OPENROUTER_INPUT_COST_PER_MILLION)),
            cached_input_cost_per_million=Decimal(str(settings.OPENROUTER_CACHED_INPUT_COST_PER_MILLION)),
            output_cost_per_million=Decimal(str(settings.OPENROUTER_OUTPUT_COST_PER_MILLION)),
            site_url=settings.OPENROUTER_SITE_URL,
            site_name=settings.OPENROUTER_SITE_NAME,
        )
    if provider == "gemini" and settings.GEMINI_API_KEY:
        return ProviderSettings(
            provider_type=provider,
            api_key=settings.GEMINI_API_KEY,
            base_url=settings.GEMINI_BASE_URL,
            model=settings.GEMINI_MODEL,
            timeout_seconds=settings.GEMINI_TIMEOUT_SECONDS,
            content_max_tokens=settings.GEMINI_CONTENT_MAX_TOKENS,
            json_max_tokens=settings.GEMINI_JSON_MAX_TOKENS,
            input_cost_per_million=Decimal(str(settings.GEMINI_INPUT_COST_PER_MILLION)),
            cached_input_cost_per_million=Decimal(str(settings.GEMINI_CACHED_INPUT_COST_PER_MILLION)),
            output_cost_per_million=Decimal(str(settings.GEMINI_OUTPUT_COST_PER_MILLION)),
        )
    if provider == "doubao" and settings.DOUBAO_API_KEY:
        return ProviderSettings(
            provider_type=provider,
            api_key=settings.DOUBAO_API_KEY,
            base_url=settings.DOUBAO_BASE_URL,
            model=settings.DOUBAO_MODEL,
            timeout_seconds=settings.DOUBAO_TIMEOUT_SECONDS,
            content_max_tokens=settings.DOUBAO_CONTENT_MAX_TOKENS,
            json_max_tokens=settings.DOUBAO_JSON_MAX_TOKENS,
            input_cost_per_million=Decimal(str(settings.DOUBAO_INPUT_COST_PER_MILLION)),
            cached_input_cost_per_million=Decimal(str(settings.DOUBAO_CACHED_INPUT_COST_PER_MILLION)),
            output_cost_per_million=Decimal(str(settings.DOUBAO_OUTPUT_COST_PER_MILLION)),
        )
    return None


def _chat_provider(config: ProviderSettings) -> AIProvider:
    provider = config.provider_type.lower()
    pricing = {
        "input": float(config.input_cost_per_million),
        "cached_input": float(config.cached_input_cost_per_million),
        "output": float(config.output_cost_per_million),
    }
    if provider == "deepseek":
        return ChatAIProvider(
            client=RecordingChatClient(
                DeepSeekClient(
                    api_key=config.api_key,
                    base_url=config.base_url,
                    model=config.model,
                    timeout_seconds=config.timeout_seconds,
                ),
                pricing_per_million=pricing,
            ),
            content_max_tokens=config.content_max_tokens,
            json_max_tokens=config.json_max_tokens,
        )
    if provider == "openrouter":
        return ChatAIProvider(
            client=RecordingChatClient(
                OpenRouterClient(
                    api_key=config.api_key,
                    base_url=config.base_url,
                    model=config.model,
                    timeout_seconds=config.timeout_seconds,
                    site_url=config.site_url,
                    site_name=config.site_name,
                ),
                pricing_per_million=pricing,
            ),
            content_max_tokens=config.content_max_tokens,
            json_max_tokens=config.json_max_tokens,
        )
    if provider == "openai":
        return ChatAIProvider(
            client=RecordingChatClient(
                OpenAIClient(
                    api_key=config.api_key,
                    base_url=config.base_url,
                    model=config.model,
                    timeout_seconds=config.timeout_seconds,
                ),
                pricing_per_million=pricing,
            ),
            content_max_tokens=config.content_max_tokens,
            json_max_tokens=config.json_max_tokens,
        )
    if provider == "gemini":
        return ChatAIProvider(
            client=RecordingChatClient(
                GeminiClient(
                    api_key=config.api_key,
                    base_url=config.base_url,
                    model=config.model,
                    timeout_seconds=config.timeout_seconds,
                ),
                pricing_per_million=pricing,
            ),
            content_max_tokens=config.content_max_tokens,
            json_max_tokens=config.json_max_tokens,
        )
    if provider == "doubao":
        return ChatAIProvider(
            client=RecordingChatClient(
                DoubaoClient(
                    api_key=config.api_key,
                    base_url=config.base_url,
                    model=config.model,
                    timeout_seconds=config.timeout_seconds,
                ),
                pricing_per_million=pricing,
            ),
            content_max_tokens=config.content_max_tokens,
            json_max_tokens=config.json_max_tokens,
        )
    logger.warning("Unsupported AI provider %s; using stub provider", provider)
    return StubProvider()


def get_ai_provider(business: str | None = None) -> AIProvider:
    config = _provider_settings_from_db(business) or _provider_settings_from_env()
    if config is None:
        return StubProvider()
    return _chat_provider(config)
