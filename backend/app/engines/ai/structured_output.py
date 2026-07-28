from copy import deepcopy
from typing import Any

from app.engines.ai.base import ChatClient


JsonSchema = dict[str, Any]
STYLE_PROMPT_MAX_LENGTH = 8000


def response_format_for(
    client: ChatClient,
    *,
    name: str,
    schema: JsonSchema,
) -> dict[str, Any]:
    """Use strict JSON Schema when the client supports it, otherwise JSON mode."""
    if getattr(client, "supports_json_schema", False) is True:
        return {
            "type": "json_schema",
            "json_schema": {
                "name": name,
                "strict": True,
                "schema": schema,
            },
        }
    return {"type": "json_object"}


_BEAT_SCHEMA: JsonSchema = {
    "type": "object",
    "properties": {
        "beat_index": {"type": "integer"},
        "cue_text": {"type": "string"},
        "visual_action": {"type": "string"},
        "emphasis": {"type": ["string", "null"]},
        "transition": {
            "type": "string",
            "enum": ["continue", "transform", "reveal", "replace", "exit"],
        },
        "fallback_weight": {"type": "number"},
    },
    "required": [
        "beat_index",
        "cue_text",
        "visual_action",
        "emphasis",
        "transition",
        "fallback_weight",
    ],
    "additionalProperties": False,
}

_FACT_CHECK_SCHEMA: JsonSchema = {
    "type": "object",
    "properties": {
        "claim_text": {"type": "string"},
        "scene_index": {"type": "integer"},
        "source_url": {"type": ["string", "null"]},
        "source_description": {"type": "string"},
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
        "is_hypothesis": {"type": "boolean"},
        "assumptions": {"type": ["string", "null"]},
        "controversy": {"type": ["string", "null"]},
        "reviewer_verdict": {"type": ["string", "null"]},
        "reviewer_note": {"type": ["string", "null"]},
    },
    "required": [
        "claim_text",
        "scene_index",
        "source_url",
        "source_description",
        "confidence",
        "is_hypothesis",
        "assumptions",
        "controversy",
        "reviewer_verdict",
        "reviewer_note",
    ],
    "additionalProperties": False,
}

NARRATIVE_SCHEMA: JsonSchema = {
    "type": "object",
    "properties": {
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "scene_index": {"type": "integer"},
                    "narration": {"type": "string"},
                    "description": {"type": "string"},
                    "estimated_duration_seconds": {"type": "number"},
                    "beats": {"type": "array", "items": _BEAT_SCHEMA},
                },
                "required": [
                    "scene_index",
                    "narration",
                    "description",
                    "estimated_duration_seconds",
                    "beats",
                ],
                "additionalProperties": False,
            },
        },
        "fact_checks": {"type": "array", "items": _FACT_CHECK_SCHEMA},
    },
    "required": ["scenes", "fact_checks"],
    "additionalProperties": False,
}


def _build_exemplar_prompt_schema() -> JsonSchema:
    """Keep a style exemplar representative without expanding into a full video."""
    schema = deepcopy(NARRATIVE_SCHEMA)
    scenes_schema = schema["properties"]["scenes"]
    scenes_schema["minItems"] = 1
    scenes_schema["maxItems"] = 2

    scene_schema = scenes_schema["items"]
    scene_properties = scene_schema["properties"]
    scene_properties["narration"]["maxLength"] = 220
    scene_properties["description"]["maxLength"] = 360

    beats_schema = scene_properties["beats"]
    beats_schema["minItems"] = 1
    beats_schema["maxItems"] = 4
    beat_properties = beats_schema["items"]["properties"]
    beat_properties["cue_text"]["maxLength"] = 100
    beat_properties["visual_action"]["maxLength"] = 300
    beat_properties["emphasis"]["maxLength"] = 60

    fact_checks_schema = schema["properties"]["fact_checks"]
    fact_checks_schema["maxItems"] = 1
    fact_properties = fact_checks_schema["items"]["properties"]
    fact_properties["claim_text"]["maxLength"] = 200
    fact_properties["source_url"]["maxLength"] = 500
    fact_properties["source_description"]["maxLength"] = 300
    fact_properties["assumptions"]["maxLength"] = 200
    fact_properties["controversy"]["maxLength"] = 200
    fact_properties["reviewer_verdict"]["maxLength"] = 100
    fact_properties["reviewer_note"]["maxLength"] = 200
    return schema


EXEMPLAR_PROMPT_SCHEMA: JsonSchema = _build_exemplar_prompt_schema()

CODE_GENERATION_SCHEMA: JsonSchema = {
    "type": "object",
    "properties": {
        "codes": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["codes"],
    "additionalProperties": False,
}

CODE_REPAIR_SCHEMA: JsonSchema = {
    "type": "object",
    "properties": {
        "repairs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "scene_index": {"type": "integer"},
                    "code": {"type": "string"},
                    "explanation": {"type": "string"},
                },
                "required": ["scene_index", "code", "explanation"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["repairs"],
    "additionalProperties": False,
}

BRAINSTORM_SCHEMA: JsonSchema = {
    "type": "object",
    "properties": {
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["title", "description", "tags"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["candidates"],
    "additionalProperties": False,
}

STYLE_ASSISTANT_SCHEMA: JsonSchema = {
    "type": "object",
    "properties": {
        "reply": {"type": "string"},
        "name": {"type": "string"},
        "description": {"type": "string"},
        "prompt_text": {
            "type": "string",
            "maxLength": STYLE_PROMPT_MAX_LENGTH,
        },
    },
    "required": ["reply", "name", "description", "prompt_text"],
    "additionalProperties": False,
}

STYLE_EXEMPLAR_ASSISTANT_SCHEMA: JsonSchema = {
    "type": "object",
    "properties": {
        "reply": {"type": "string"},
        "name": {"type": "string"},
        "description": {"type": "string"},
        "prompt_text": EXEMPLAR_PROMPT_SCHEMA,
    },
    "required": ["reply", "name", "description", "prompt_text"],
    "additionalProperties": False,
}

_STYLE_LIBRARY_COMPONENT_SCHEMA: JsonSchema = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "description": {"type": "string"},
        "prompt_text": {
            "type": "string",
            "maxLength": STYLE_PROMPT_MAX_LENGTH,
        },
    },
    "required": ["name", "description", "prompt_text"],
    "additionalProperties": False,
}

_STYLE_LIBRARY_EXEMPLAR_COMPONENT_SCHEMA: JsonSchema = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "description": {"type": "string"},
        "prompt_text": EXEMPLAR_PROMPT_SCHEMA,
    },
    "required": ["name", "description", "prompt_text"],
    "additionalProperties": False,
}

STYLE_LIBRARY_ASSISTANT_SCHEMA: JsonSchema = {
    "type": "object",
    "properties": {
        "reply": {"type": "string"},
        "name": {"type": "string"},
        "description": {"type": "string"},
        "components": {
            "type": "object",
            "properties": {
                "narrative_style": _STYLE_LIBRARY_COMPONENT_SCHEMA,
                "color_scheme": _STYLE_LIBRARY_COMPONENT_SCHEMA,
                "animation_style": _STYLE_LIBRARY_COMPONENT_SCHEMA,
                "exemplar": _STYLE_LIBRARY_EXEMPLAR_COMPONENT_SCHEMA,
            },
            "required": [
                "narrative_style",
                "color_scheme",
                "animation_style",
                "exemplar",
            ],
            "additionalProperties": False,
        },
    },
    "required": ["reply", "name", "description", "components"],
    "additionalProperties": False,
}
