from typing import Protocol
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
