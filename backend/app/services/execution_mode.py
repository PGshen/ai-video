from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.models.ai_model_config import AIBusinessModelConfig

VALID_EXECUTION_MODES = ("prompt", "agent")
DEFAULT_EXECUTION_MODE = "prompt"


def _normalize(value: Any) -> str | None:
    if isinstance(value, str) and value in VALID_EXECUTION_MODES:
        return value
    return None


def resolve_execution_mode(db: Any, project: Any, business: str) -> str:
    """项目级 → 全局业务配置 → 默认。无效值一律回落到默认。"""
    project_mode = _normalize(getattr(project, "execution_mode", None))
    if project_mode is not None:
        return project_mode

    config = db.execute(
        select(AIBusinessModelConfig).where(
            AIBusinessModelConfig.business == business
        )
    ).scalar_one_or_none()
    if config is not None:
        global_mode = _normalize(getattr(config, "execution_mode", None))
        if global_mode is not None:
            return global_mode

    return DEFAULT_EXECUTION_MODE
