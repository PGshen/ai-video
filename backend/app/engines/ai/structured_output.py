from typing import Any

from app.engines.ai.base import ChatClient


JsonSchema = dict[str, Any]


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
