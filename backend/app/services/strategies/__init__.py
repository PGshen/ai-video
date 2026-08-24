from app.services.strategies.base import (
    CodegenOutcome,
    CodegenStrategy,
    NarrativeOutcome,
    NarrativeStrategy,
)
from app.services.strategies.prompt_codegen import PromptCodegenStrategy
from app.services.strategies.prompt_narrative import PromptNarrativeStrategy

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


def get_codegen_strategy(execution_mode: str) -> CodegenStrategy:
    return PromptCodegenStrategy()


def get_narrative_strategy(execution_mode: str) -> NarrativeStrategy:
    return PromptNarrativeStrategy()
