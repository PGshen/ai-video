from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class CodegenOutcome:
    scenes: list[dict]
    ai_model: str
    trace: dict[str, Any] = field(default_factory=dict)


@dataclass
class NarrativeOutcome:
    scenes: list[dict]
    fact_checks: list[dict]
    ai_model: str
    trace: dict[str, Any] = field(default_factory=dict)


class CodegenStrategy(Protocol):
    async def run(
        self,
        *,
        scenes: list[dict],
        render_engine: str,
        style_components: dict[str, str],
        aspect_ratio: str,
        rejection_context: dict | None,
        previous_code_scenes: list[dict] | None,
        task_id: Any,
    ) -> CodegenOutcome: ...


class NarrativeStrategy(Protocol):
    async def run(
        self,
        *,
        topic_title: str,
        topic_description: str,
        render_engine: str,
        aspect_ratio: str,
        rejection_context: dict | None,
        previous_scenes: list[dict] | None,
        narrative_context: list[dict],
        style_components: dict[str, str],
        task_id: Any,
    ) -> NarrativeOutcome: ...
