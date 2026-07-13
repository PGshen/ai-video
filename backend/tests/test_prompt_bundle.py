from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

from app.models.prompt_component import PromptComponent
from app.services.prompt_bundle import (
    BASE_PROMPT_VERSION,
    STYLE_CATEGORIES,
    build_prompt_snapshot,
    style_components_from_snapshot,
)


def test_style_categories_are_blueprint_era():
    assert set(STYLE_CATEGORIES) == {
        "narrative_style",
        "color_scheme",
        "animation_style",
        "exemplar",
    }


def test_build_prompt_snapshot_captures_selected_component_and_defaults():
    selected_id = uuid4()
    selected = SimpleNamespace(
        id=selected_id,
        name="自定义叙事",
        prompt_text="自定义叙事提示词",
        updated_at=datetime(2026, 7, 2, tzinfo=timezone.utc),
    )
    project = SimpleNamespace(
        style_config={"narrative_style": str(selected_id)},
        render_engine="manim",
    )
    db = MagicMock()
    db.get.side_effect = (
        lambda model, value:
        selected if model is PromptComponent and value == selected_id else None
    )

    style_components, snapshot = build_prompt_snapshot(db, project)

    assert style_components["narrative_style"] == "自定义叙事提示词"
    assert set(style_components) == set(STYLE_CATEGORIES)
    assert snapshot["base_prompt_version"] == BASE_PROMPT_VERSION
    assert snapshot["components"]["narrative_style"]["id"] == str(selected_id)
    assert snapshot["components"]["exemplar"]["name"] == "system-default"
    assert snapshot["components"]["color_scheme"]["name"] == "system-default"
    assert snapshot["engine_spec_sha256"]
    assert style_components_from_snapshot(snapshot) == style_components


def test_style_components_from_snapshot_rejects_incomplete_snapshot():
    try:
        style_components_from_snapshot({"components": {}})
    except ValueError as exc:
        assert "narrative_style" in str(exc)
    else:
        raise AssertionError("Expected incomplete snapshot to fail")


def test_style_components_from_snapshot_accepts_legacy_five_category_snapshot():
    """升级前生成的快照包含 pacing / scene_structure，必须原样透传。"""
    legacy = {
        "components": {
            category: {"prompt_text": f"{category} 文本"}
            for category in (
                "narrative_style",
                "pacing",
                "scene_structure",
                "color_scheme",
                "animation_style",
            )
        }
    }
    resolved = style_components_from_snapshot(legacy)
    assert resolved["pacing"] == "pacing 文本"
    assert resolved["scene_structure"] == "scene_structure 文本"
    assert "exemplar" not in resolved
