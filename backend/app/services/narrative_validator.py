from __future__ import annotations

import unicodedata
from typing import Any


_WHITESPACE = {" ", "\t", "\r", "\n", "\u3000"}
_PUNCTUATION_TRANSLATION = str.maketrans(
    {
        "，": ",",
        "。": ".",
        "！": "!",
        "？": "?",
        "：": ":",
        "；": ";",
        "（": "(",
        "）": ")",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
    }
)
_VALID_TRANSITIONS = {"continue", "transform", "reveal", "replace", "exit"}


class NarrativeValidationError(ValueError):
    def __init__(self, errors: list[str]):
        self.errors = tuple(errors)
        details = "\n".join(f"- {error}" for error in errors)
        super().__init__(
            f"Narrative validation failed with {len(errors)} error(s):\n{details}"
        )


def normalize_alignment_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).translate(_PUNCTUATION_TRANSLATION)
    return "".join(char for char in normalized if char not in _WHITESPACE)


def validate_and_normalize_scenes(
    scenes: list[dict[str, Any]],
    *,
    preserve_alignment: bool = False,
) -> list[dict[str, Any]]:
    if not scenes:
        raise NarrativeValidationError(["Narrative must contain at least one scene"])

    errors: list[str] = []
    normalized_scenes: list[dict[str, Any]] = []
    for expected_scene_index, source_scene in enumerate(scenes):
        if not isinstance(source_scene, dict):
            errors.append(f"Scene {expected_scene_index} must be an object")
            continue

        scene = dict(source_scene)
        if scene.get("scene_index") != expected_scene_index:
            errors.append(
                f"Scene indices must be continuous: expected {expected_scene_index}, "
                f"got {scene.get('scene_index')}"
            )

        narration = scene.get("narration")
        description = scene.get("description")
        beats = scene.get("beats")
        narration_is_valid = isinstance(narration, str) and bool(narration.strip())
        description_is_valid = isinstance(description, str) and bool(description.strip())
        beats_are_valid = isinstance(beats, list) and bool(beats)
        if not narration_is_valid:
            errors.append(f"Scene {expected_scene_index} narration must be non-empty")
        if not description_is_valid:
            errors.append(f"Scene {expected_scene_index} description must be non-empty")
        if not beats_are_valid:
            errors.append(f"Scene {expected_scene_index} beats must be a non-empty array")
            continue

        normalized_beats: list[dict[str, Any]] = []
        all_cues_are_valid = True
        for beat_index, source_beat in enumerate(beats):
            if not isinstance(source_beat, dict):
                errors.append(
                    f"Scene {expected_scene_index} beat {beat_index} must be an object"
                )
                all_cues_are_valid = False
                continue
            beat = dict(source_beat)
            cue_text = beat.get("cue_text")
            visual_action = beat.get("visual_action")
            if not isinstance(cue_text, str) or not cue_text:
                errors.append(
                    f"Scene {expected_scene_index} beat {beat_index} cue_text is required"
                )
                all_cues_are_valid = False
            if not isinstance(visual_action, str) or not visual_action.strip():
                errors.append(
                    f"Scene {expected_scene_index} beat {beat_index} visual_action is required"
                )

            try:
                fallback_weight = float(beat.get("fallback_weight", 1.0))
            except (TypeError, ValueError):
                errors.append(
                    f"Scene {expected_scene_index} beat {beat_index} fallback_weight must be numeric"
                )
                fallback_weight = 1.0
            if fallback_weight <= 0:
                errors.append(
                    f"Scene {expected_scene_index} beat {beat_index} fallback_weight must be positive"
                )

            transition = beat.get("transition", "continue")
            if transition not in _VALID_TRANSITIONS:
                allowed = ", ".join(sorted(_VALID_TRANSITIONS))
                errors.append(
                    f"Scene {expected_scene_index} beat {beat_index} has invalid transition "
                    f"{transition!r}; allowed values: {allowed}"
                )

            normalized_beats.append(
                {
                    **beat,
                    "beat_index": beat_index,
                    "cue_text": cue_text if isinstance(cue_text, str) else "",
                    "visual_action": (
                        visual_action.strip() if isinstance(visual_action, str) else ""
                    ),
                    "transition": transition,
                    "fallback_weight": fallback_weight,
                    "alignment_status": (
                        beat.get("alignment_status", "pending")
                        if preserve_alignment
                        else "pending"
                    ),
                    "cue_start_char": beat.get("cue_start_char") if preserve_alignment else None,
                    "cue_end_char": beat.get("cue_end_char") if preserve_alignment else None,
                    "speech_start_seconds": (
                        beat.get("speech_start_seconds") if preserve_alignment else None
                    ),
                    "speech_end_seconds": (
                        beat.get("speech_end_seconds") if preserve_alignment else None
                    ),
                    "animation_start_seconds": (
                        beat.get("animation_start_seconds") if preserve_alignment else None
                    ),
                    "animation_end_seconds": (
                        beat.get("animation_end_seconds") if preserve_alignment else None
                    ),
                }
            )

        if narration_is_valid and all_cues_are_valid:
            normalized_narration = normalize_alignment_text(narration)
            normalized_cues = normalize_alignment_text(
                "".join(beat["cue_text"] for beat in normalized_beats)
            )
            if normalized_cues != normalized_narration:
                errors.append(
                    f"Scene {expected_scene_index} cue_text values must cover narration exactly"
                )

        normalized_scenes.append(
            {
                **scene,
                "narration": "".join(beat["cue_text"] for beat in normalized_beats).strip(),
                "description": description.strip() if isinstance(description, str) else "",
                "beats": normalized_beats,
                "content_schema_version": 2,
            }
        )

    if errors:
        raise NarrativeValidationError(errors)

    return normalized_scenes


def validate_scenes_for_codegen(scenes: list[dict[str, Any]]) -> None:
    if not scenes:
        raise ValueError("Code generation requires at least one scene")
    for expected_scene_index, scene in enumerate(scenes):
        if scene.get("scene_index") != expected_scene_index:
            raise ValueError(
                f"Scene indices must be continuous before code generation: "
                f"expected {expected_scene_index}, got {scene.get('scene_index')}"
            )
        beats = scene.get("beats")
        duration_value = scene.get("duration_seconds")
        if duration_value is None or float(duration_value) <= 0:
            raise ValueError(f"Scene {expected_scene_index} has no valid audio duration")
        duration = float(duration_value)
        if not isinstance(beats, list) or not beats:
            raise ValueError(f"Scene {expected_scene_index} beats must be non-empty")
        previous_speech_start = -1.0
        previous_animation_start = -1.0
        for expected_beat_index, beat in enumerate(beats):
            if not isinstance(beat, dict) or beat.get("beat_index") != expected_beat_index:
                raise ValueError(
                    f"Scene {expected_scene_index} beat indices must be continuous"
                )
            if beat.get("alignment_status") not in {"aligned", "interpolated"}:
                raise ValueError(
                    f"Scene {expected_scene_index} beat {expected_beat_index} "
                    f"has unresolved alignment"
                )
            for field in (
                "speech_start_seconds",
                "speech_end_seconds",
                "animation_start_seconds",
                "animation_end_seconds",
            ):
                if beat.get(field) is None:
                    raise ValueError(
                        f"Scene {expected_scene_index} beat {expected_beat_index} "
                        f"is missing {field}"
                    )
            speech_start = float(beat["speech_start_seconds"])
            speech_end = float(beat["speech_end_seconds"])
            animation_start = float(beat["animation_start_seconds"])
            animation_end = float(beat["animation_end_seconds"])
            if not (
                0 <= speech_start <= speech_end <= duration
                and 0 <= animation_start <= animation_end <= duration
            ):
                raise ValueError(
                    f"Scene {expected_scene_index} beat {expected_beat_index} timing is out of range"
                )
            if (
                speech_start < previous_speech_start
                or animation_start < previous_animation_start
            ):
                raise ValueError(
                    f"Scene {expected_scene_index} beat timing must be monotonic"
                )
            previous_speech_start = speech_start
            previous_animation_start = animation_start
