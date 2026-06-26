from typing import Protocol, AsyncIterator
from dataclasses import dataclass


@dataclass
class ScriptGenerationResult:
    scenes: list[dict]
    fact_checks: list[dict]


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

    async def research_topic(
        self,
        topic_title: str,
        topic_description: str,
        conversation_history: list[dict],
        new_message: str,
        use_default_prompt: bool = False,
    ) -> AsyncIterator[str]: ...
