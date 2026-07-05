from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel


class StyleTemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    style_config: dict[str, str] = Field(..., min_length=1, max_length=5)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name cannot be blank")
        return value


class StyleTemplateUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    style_config: dict[str, str] | None = Field(None, min_length=1, max_length=5)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("name cannot be blank")
        return value


class StyleTemplateResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    id: UUID
    name: str
    description: str | None
    style_config: dict[str, str]
    created_at: datetime
    updated_at: datetime


class StyleTemplateListResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    items: list[StyleTemplateResponse]
    total: int
