from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel


class _CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


class TTSEngineBase(_CamelModel):
    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=50, pattern=r"^[a-zA-Z0-9_.-]+$")
    provider_type: str = Field(default="volcengine", max_length=30)
    endpoint: str = Field(..., min_length=1, max_length=500)
    resource_id: str = Field(..., min_length=1, max_length=100)
    timeout_seconds: float = Field(default=60.0, gt=0, le=600)
    is_active: bool = True

    @field_validator("provider_type")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        value = value.strip().lower()
        if value != "volcengine":
            raise ValueError("当前仅支持 volcengine")
        return value


class TTSEngineCreate(TTSEngineBase):
    api_key: str = Field(..., min_length=1)


class TTSEngineUpdate(_CamelModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    code: str | None = Field(default=None, min_length=1, max_length=50, pattern=r"^[a-zA-Z0-9_.-]+$")
    provider_type: str | None = Field(default=None, max_length=30)
    endpoint: str | None = Field(default=None, min_length=1, max_length=500)
    api_key: str | None = None
    resource_id: str | None = Field(default=None, min_length=1, max_length=100)
    timeout_seconds: float | None = Field(default=None, gt=0, le=600)
    is_active: bool | None = None

    @field_validator("provider_type")
    @classmethod
    def validate_provider(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().lower()
        if value != "volcengine":
            raise ValueError("当前仅支持 volcengine")
        return value


class TTSEngineResponse(TTSEngineBase):
    id: UUID
    api_key_set: bool
    created_at: datetime
    updated_at: datetime


class TTSVoiceBase(_CamelModel):
    engine_id: UUID
    name: str = Field(..., min_length=1, max_length=100)
    speaker_id: str = Field(..., min_length=1, max_length=200)
    language: str = Field(default="zh-CN", min_length=1, max_length=30)
    gender: str | None = Field(default=None, max_length=20)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool = True

    @field_validator("name", "speaker_id", "language", mode="before")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        return value.strip()


class TTSVoiceCreate(TTSVoiceBase):
    pass


class TTSVoiceUpdate(_CamelModel):
    engine_id: UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100)
    speaker_id: str | None = Field(default=None, min_length=1, max_length=200)
    language: str | None = Field(default=None, min_length=1, max_length=30)
    gender: str | None = Field(default=None, max_length=20)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None

    @field_validator("name", "speaker_id", "language", mode="before")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class TTSVoiceResponse(TTSVoiceBase):
    id: UUID
    created_at: datetime
    updated_at: datetime


class TTSSettingsResponse(_CamelModel):
    engines: list[TTSEngineResponse]
    voices: list[TTSVoiceResponse]


class TTSVoicePreviewRequest(_CamelModel):
    text: str = Field(..., min_length=1, max_length=500)
    speed: float = Field(default=1.0, ge=0.5, le=2.0)

    @field_validator("text")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("试听文字不能为空")
        return value
