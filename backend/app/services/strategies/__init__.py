import logging

from app.services.strategies.base import (
    CodegenOutcome,
    CodegenStrategy,
    NarrativeOutcome,
    NarrativeStrategy,
)
from app.services.strategies.prompt_codegen import PromptCodegenStrategy
from app.services.strategies.prompt_narrative import PromptNarrativeStrategy

logger = logging.getLogger(__name__)

__all__ = [
    "CodegenOutcome",
    "CodegenStrategy",
    "NarrativeOutcome",
    "NarrativeStrategy",
    "PromptCodegenStrategy",
    "PromptNarrativeStrategy",
    "get_codegen_strategy",
    "get_narrative_strategy",
]


VALID_EXECUTION_MODES = ("prompt", "agent")


def _normalize_mode(execution_mode: str) -> str:
    """未知取值一律回落到 prompt，避免脏数据把任务打到 Agent 分支。"""
    if execution_mode not in VALID_EXECUTION_MODES:
        logger.warning(
            "[Strategies] 未知 execution_mode=%r，回落到 prompt", execution_mode
        )
        return "prompt"
    return execution_mode


def get_codegen_strategy(execution_mode: str) -> CodegenStrategy:
    if _normalize_mode(execution_mode) == "agent":
        from app.services.strategies.agent_codegen import AgentCodegenStrategy

        return AgentCodegenStrategy()
    return PromptCodegenStrategy()


def get_narrative_strategy(execution_mode: str) -> NarrativeStrategy:
    _normalize_mode(execution_mode)
    return PromptNarrativeStrategy()
