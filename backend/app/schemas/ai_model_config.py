from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel


AI_PROVIDER_TYPES = {
    "deepseek",
    "openrouter",
    "gemini",
    "doubao",
    "anthropic",
    "openai",
}


class AIBusinessOption(BaseModel):
    key: str
    label: str


class AIModelProviderBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    name: str = Field(..., min_length=1, max_length=100)
    provider_type: str = Field(..., max_length=30)
    base_url: str = Field(default="", max_length=300)
    timeout_seconds: float = Field(default=600.0, gt=0)
    site_url: str | None = Field(default=None, max_length=300)
    site_name: str | None = Field(default=None, max_length=100)
    is_active: bool = True

    @field_validator("provider_type")
    @classmethod
    def validate_provider_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in AI_PROVIDER_TYPES:
            raise ValueError(f"provider_type must be one of {sorted(AI_PROVIDER_TYPES)}")
        return normalized


class AIModelProviderCreate(AIModelProviderBase):
    api_key: str = Field(..., min_length=1)


class AIModelProviderUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    name: str | None = Field(default=None, min_length=1, max_length=100)
    provider_type: str | None = Field(default=None, max_length=30)
    base_url: str | None = Field(default=None, max_length=300)
    api_key: str | None = None
    timeout_seconds: float | None = Field(default=None, gt=0)
    site_url: str | None = Field(default=None, max_length=300)
    site_name: str | None = Field(default=None, max_length=100)
    is_active: bool | None = None

    @field_validator("provider_type")
    @classmethod
    def validate_provider_type(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip().lower()
        if normalized not in AI_PROVIDER_TYPES:
            raise ValueError(f"provider_type must be one of {sorted(AI_PROVIDER_TYPES)}")
        return normalized


class AIModelProviderResponse(AIModelProviderBase):
    id: UUID
    api_key_set: bool
    created_at: datetime
    updated_at: datetime


class AIProviderModelBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    provider_id: UUID
    name: str = Field(..., min_length=1, max_length=100)
    model: str = Field(..., min_length=1, max_length=150)
    content_max_tokens: int = Field(default=100000, ge=1)
    json_max_tokens: int = Field(default=100000, ge=1)
    input_cost_per_million: Decimal = Field(default=Decimal("0"), ge=0)
    cached_input_cost_per_million: Decimal = Field(default=Decimal("0"), ge=0)
    output_cost_per_million: Decimal = Field(default=Decimal("0"), ge=0)
    is_active: bool = True


class AIProviderModelCreate(AIProviderModelBase):
    pass


class AIProviderModelUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    provider_id: UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100)
    model: str | None = Field(default=None, min_length=1, max_length=150)
    content_max_tokens: int | None = Field(default=None, ge=1)
    json_max_tokens: int | None = Field(default=None, ge=1)
    input_cost_per_million: Decimal | None = Field(default=None, ge=0)
    cached_input_cost_per_million: Decimal | None = Field(default=None, ge=0)
    output_cost_per_million: Decimal | None = Field(default=None, ge=0)
    is_active: bool | None = None


class AIProviderModelResponse(AIProviderModelBase):
    id: UUID
    created_at: datetime
    updated_at: datetime


class AIModelTestRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    provider_id: UUID
    model: str = Field(..., min_length=1, max_length=150)


class AIModelTestResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    ok: bool
    latency_ms: int | None = None
    reply: str | None = None
    message: str | None = None


class AIBusinessModelConfigUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    model_id: UUID | None = None


class AIBusinessModelConfigResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    id: UUID
    business: str
    model_id: UUID
    created_at: datetime
    updated_at: datetime


class AIModelSettingsResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    providers: list[AIModelProviderResponse]
    models: list[AIProviderModelResponse]
    business_configs: list[AIBusinessModelConfigResponse]
    business_options: list[AIBusinessOption]
