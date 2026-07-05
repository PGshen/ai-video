from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from typing import Optional
from datetime import datetime
from uuid import UUID


class PromptComponentBase(BaseModel):
    category: str
    name: str
    description: Optional[str] = None
    prompt_text: str = Field(..., max_length=8000)


class PromptComponentCreate(PromptComponentBase):
    pass


class PromptComponentUpdate(BaseModel):
    category: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    prompt_text: Optional[str] = Field(None, max_length=8000)


class PromptComponentResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    id: UUID
    category: str
    name: str
    description: Optional[str]
    prompt_text: str
    is_builtin: bool
    created_by: Optional[str]
    created_at: datetime
    updated_at: datetime


class PromptComponentListResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    items: list[PromptComponentResponse]
    total: int


class StyleAssistantMessage(BaseModel):
    role: str
    content: str


class StyleAssistantRequest(BaseModel):
    category: str
    name: str = ""
    description: str = ""
    prompt_text: str = Field(default="", max_length=8000)
    conversation_history: list[StyleAssistantMessage] = Field(default_factory=list, max_length=20)
    message: str = Field(..., min_length=1, max_length=2000)


class StyleAssistantResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    reply: str
    name: str
    description: str
    prompt_text: str
