import pytest
from pydantic import ValidationError
from uuid import uuid4

from app.schemas.project import ProjectCreate


def _base_kwargs(**overrides):
    kwargs = dict(
        topic_id=uuid4(),
        render_engine="manim",
        tts_voice="voice-1",
        aspect_ratio="16:9",
    )
    kwargs.update(overrides)
    return kwargs


def test_execution_mode_defaults_to_none():
    project = ProjectCreate(**_base_kwargs())
    assert project.execution_mode is None


def test_execution_mode_accepts_prompt():
    project = ProjectCreate(**_base_kwargs(execution_mode="prompt"))
    assert project.execution_mode == "prompt"


def test_execution_mode_accepts_agent():
    project = ProjectCreate(**_base_kwargs(execution_mode="agent"))
    assert project.execution_mode == "agent"


def test_execution_mode_rejects_invalid_value():
    with pytest.raises(ValidationError):
        ProjectCreate(**_base_kwargs(execution_mode="banana"))
