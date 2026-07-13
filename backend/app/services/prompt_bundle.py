from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import Any

from app.engines.ai.chat_provider import ChatAIProvider
from app.models.prompt_component import PromptComponent


BASE_PROMPT_VERSION = "blueprint-exemplar-v1"
STYLE_CATEGORIES = (
    "narrative_style",
    "color_scheme",
    "animation_style",
    "exemplar",
)
# 旧版快照包含 pacing / scene_structure（已并入叙事蓝图），解析时原样透传；
# 新旧快照都必须至少包含以下类别。
REQUIRED_SNAPSHOT_CATEGORIES = (
    "narrative_style",
    "color_scheme",
    "animation_style",
)
_ENGINE_SPECS_DIR = Path(__file__).resolve().parents[1] / "engines" / "ai" / "engine_specs"


def build_prompt_snapshot(db: Any, project: Any) -> tuple[dict[str, str], dict[str, Any]]:
    style_config = project.style_config or {}
    style_components: dict[str, str] = {}
    component_metadata: dict[str, dict[str, Any]] = {}

    for category in STYLE_CATEGORIES:
        component = None
        component_id = style_config.get(category)
        if component_id:
            try:
                component = db.get(PromptComponent, uuid.UUID(str(component_id)))
            except (ValueError, TypeError):
                component = None

        if component is not None:
            prompt_text = component.prompt_text
            updated_at = getattr(component, "updated_at", None)
            metadata = {
                "id": str(component.id),
                "name": component.name,
                "prompt_text": prompt_text,
                "updated_at": updated_at.isoformat() if updated_at else None,
                "sha256": hashlib.sha256(prompt_text.encode("utf-8")).hexdigest(),
            }
        else:
            prompt_text = ChatAIProvider._DEFAULT_STYLE_COMPONENTS[category]
            metadata = {
                "id": None,
                "name": "system-default",
                "prompt_text": prompt_text,
                "updated_at": None,
                "sha256": hashlib.sha256(prompt_text.encode("utf-8")).hexdigest(),
            }

        style_components[category] = prompt_text
        component_metadata[category] = metadata

    engine = project.render_engine
    engine_spec_path = _ENGINE_SPECS_DIR / f"{engine}.yaml"
    engine_spec_sha256 = (
        hashlib.sha256(engine_spec_path.read_bytes()).hexdigest()
        if engine_spec_path.exists()
        else None
    )
    snapshot = {
        "base_prompt_version": BASE_PROMPT_VERSION,
        "render_engine": engine,
        "engine_spec_sha256": engine_spec_sha256,
        "components": component_metadata,
    }
    return style_components, snapshot


def style_components_from_snapshot(snapshot: dict[str, Any]) -> dict[str, str]:
    components = snapshot.get("components")
    if not isinstance(components, dict):
        raise ValueError("Prompt snapshot components are missing")

    resolved: dict[str, str] = {}
    for category, metadata in components.items():
        if not isinstance(metadata, dict) or not isinstance(metadata.get("prompt_text"), str):
            raise ValueError(f"Prompt snapshot has invalid category {category}")
        resolved[category] = metadata["prompt_text"]
    for category in REQUIRED_SNAPSHOT_CATEGORIES:
        if category not in resolved:
            raise ValueError(f"Prompt snapshot is missing category {category}")
    return resolved
