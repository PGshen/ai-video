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


def with_execution_trace(
    prompt_snapshot: dict, execution_mode: str, trace: dict | None = None
) -> dict:
    """产物溯源：把执行模式与 Agent 执行信息并进 prompt_snapshot（只增键）。"""
    snapshot = {**prompt_snapshot, "execution_mode": execution_mode}
    if execution_mode != "agent":
        return snapshot
    trace = trace or {}
    snapshot["agent"] = {
        "sdk_version": trace.get("sdk_version"),
        "model": trace.get("model"),
        "max_turns": trace.get("max_turns"),
        "num_turns": trace.get("num_turns"),
        "tool_calls": trace.get("tool_calls") or [],
        "total_cost_usd": trace.get("total_cost_usd"),
        "resumed": bool(trace.get("resumed")),
        "validated_first_pass": bool(trace.get("validated_first_pass")),
    }
    return snapshot
