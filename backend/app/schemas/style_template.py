from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

from app.schemas.prompt_component import StyleAssistantMessage


STYLE_LIBRARY_CATEGORIES = {
    "narrative_style",
    "color_scheme",
    "animation_style",
    "exemplar",
}


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


class StyleLibraryComponentInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    prompt_text: str = Field(..., min_length=1, max_length=8000)

    @field_validator("name", "prompt_text")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value cannot be blank")
        return value


class StyleLibraryComponentDraft(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    name: str = Field(default="", max_length=100)
    description: str = ""
    prompt_text: str = Field(default="", max_length=8000)


class StyleLibraryUpsert(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    components: dict[str, StyleLibraryComponentInput] = Field(
        ..., min_length=4, max_length=4
    )

    @field_validator("name")
    @classmethod
    def validate_library_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name cannot be blank")
        return value

    @field_validator("components")
    @classmethod
    def validate_library_components(
        cls, value: dict[str, StyleLibraryComponentInput]
    ) -> dict[str, StyleLibraryComponentInput]:
        if set(value) != STYLE_LIBRARY_CATEGORIES:
            raise ValueError("components must contain all four style categories")
        return value


class StyleLibraryAssistantRequest(BaseModel):
    name: str = Field(default="", max_length=100)
    description: str = ""
    components: dict[str, StyleLibraryComponentDraft] = Field(default_factory=dict)
    conversation_history: list[StyleAssistantMessage] = Field(
        default_factory=list, max_length=20
    )
    message: str = Field(..., min_length=1, max_length=2000)


class StyleLibraryAssistantResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    reply: str
    name: str
    description: str
    components: dict[str, StyleLibraryComponentDraft]
