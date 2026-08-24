from unittest.mock import MagicMock

from app.services.execution_mode import resolve_execution_mode


def _db_with_business_mode(mode):
    db = MagicMock()
    config = MagicMock()
    config.execution_mode = mode
    db.execute.return_value.scalar_one_or_none.return_value = config
    return db


def test_project_level_overrides_global():
    project = MagicMock()
    project.execution_mode = "agent"
    db = _db_with_business_mode("prompt")
    assert resolve_execution_mode(db, project, "code_generation") == "agent"


def test_null_project_falls_back_to_global():
    project = MagicMock()
    project.execution_mode = None
    db = _db_with_business_mode("agent")
    assert resolve_execution_mode(db, project, "code_generation") == "agent"


def test_missing_global_config_defaults_to_prompt():
    project = MagicMock()
    project.execution_mode = None
    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = None
    assert resolve_execution_mode(db, project, "code_generation") == "prompt"


def test_unknown_value_defaults_to_prompt():
    project = MagicMock()
    project.execution_mode = "banana"
    db = _db_with_business_mode("prompt")
    assert resolve_execution_mode(db, project, "code_generation") == "prompt"
