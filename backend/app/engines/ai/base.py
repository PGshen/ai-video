from typing import Protocol, AsyncIterator
from dataclasses import dataclass


@dataclass
class BrainstormResult:
    candidates: list[dict]


@dataclass
class NarrativeResult:
    scenes: list[dict]
    fact_checks: list[dict]


@dataclass
class CodeGenerationResult:
    codes: list[str]


@dataclass
class CodeRepairResult:
    repairs: list[dict]


class ChatClient(Protocol):
    @property
    def engine_name(self) -> str: ...

    @property
    def model_name(self) -> str: ...

    @property
    def supports_json_schema(self) -> bool: ...

    async def create_chat_completion(
        self,
        messages: list[dict],
        response_format: dict | None = None,
        max_tokens: int | None = None,
    ) -> str: ...

    async def stream_chat_completion(
        self,
        messages: list[dict],
    ) -> AsyncIterator[str]: ...


class AIProvider(Protocol):
    @property
    def engine_name(self) -> str: ...

    @property
    def model_name(self) -> str: ...
    
    async def generate_narrative(
        self,
        topic_title: str,
        topic_description: str,
        render_engine: str,
        rejection_context: dict | None = None,
        narrative_context: list[dict] | None = None,
        style_components: dict[str, str] | None = None,
        aspect_ratio: str = "landscape",
    ) -> NarrativeResult: ...

    async def generate_code(
        self,
        scenes: list[dict],
        render_engine: str,
        style_components: dict[str, str] | None = None,
        aspect_ratio: str = "landscape",
    ) -> CodeGenerationResult: ...

    async def repair_code(
        self,
        scenes: list[dict],
        render_engine: str,
        error_message: str,
        style_components: dict[str, str] | None = None,
        aspect_ratio: str = "landscape",
    ) -> CodeRepairResult: ...

    async def brainstorm_topics(
        self,
        topic_direction: str,
        count: int,
    ) -> BrainstormResult: ...

    async def research_topic(
        self,
        topic_title: str,
        topic_description: str,
        conversation_history: list[dict],
        new_message: str,
        use_default_prompt: bool = False,
        system_prompt: str | None = None,
    ) -> AsyncIterator[str]: ...
