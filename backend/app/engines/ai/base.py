from typing import Protocol, AsyncIterator
from dataclasses import dataclass


@dataclass
class ScriptGenerationResult:
    scenes: list[dict]
    fact_checks: list[dict]


@dataclass
class BrainstormResult:
    candidates: list[dict]


class ChatClient(Protocol):
    @property
    def engine_name(self) -> str: ...

    @property
    def model_name(self) -> str: ...

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

    async def generate_script(
        self,
        topic_title: str,
        topic_description: str,
        render_engine: str,
        rejection_context: dict | None = None,
    ) -> ScriptGenerationResult: ...

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
