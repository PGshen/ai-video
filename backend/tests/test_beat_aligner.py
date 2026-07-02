import pytest

from app.services.beat_aligner import align_scene_beats
from app.services.narrative_validator import (
    NarrativeValidationError,
    validate_and_normalize_scenes,
    validate_scenes_for_codegen,
)


def _scene(**overrides):
    scene = {
        "scene_index": 0,
        "narration": "你好，语音测试",
        "description": "逐步显示问候和测试文字。",
        "duration_seconds": 2.0,
        "beats": [
            {
                "beat_index": 0,
                "cue_text": "你好，",
                "visual_action": "问候文字出现。",
                "transition": "reveal",
                "fallback_weight": 1,
            },
            {
                "beat_index": 1,
                "cue_text": "语音测试",
                "visual_action": "测试文字依次出现。",
                "transition": "continue",
                "fallback_weight": 1,
            },
        ],
        "word_timestamps": [
            {"word": "你", "start_time": 0.195, "end_time": 0.335, "confidence": 0.9},
            {"word": "好，", "start_time": 0.335, "end_time": 0.725, "confidence": 0.9},
            {"word": "语", "start_time": 0.985, "end_time": 1.025, "confidence": 0.9},
            {"word": "音", "start_time": 1.025, "end_time": 1.205, "confidence": 0.9},
            {"word": "测", "start_time": 1.205, "end_time": 1.395, "confidence": 0.9},
            {"word": "试", "start_time": 1.395, "end_time": 1.695, "confidence": 0.9},
        ],
    }
    return {**scene, **overrides}


def test_validate_requires_beats():
    with pytest.raises(ValueError, match="beats must be a non-empty array"):
        validate_and_normalize_scenes(
            [{"scene_index": 0, "narration": "旁白", "description": "画面"}]
        )


def test_validate_requires_cues_to_cover_narration():
    scene = _scene()
    scene["beats"][1]["cue_text"] = "错误文本"
    with pytest.raises(ValueError, match="cover narration exactly"):
        validate_and_normalize_scenes([scene])


def test_narrative_validation_collects_all_independent_errors():
    scenes = [
        {
            "scene_index": 4,
            "narration": "第一幕",
            "description": "",
            "beats": [{
                "cue_text": "第一幕",
                "visual_action": "",
                "transition": "fade",
                "fallback_weight": 0,
            }],
        },
        {
            "scene_index": 1,
            "narration": "第二幕",
            "description": "画面",
            "beats": [{
                "cue_text": "错误文本",
                "visual_action": "文字出现",
            }],
        },
    ]

    with pytest.raises(NarrativeValidationError) as exc_info:
        validate_and_normalize_scenes(scenes)

    errors = exc_info.value.errors
    assert len(errors) == 6
    assert any("expected 0, got 4" in error for error in errors)
    assert any("Scene 0 description must be non-empty" in error for error in errors)
    assert any("Scene 0 beat 0 visual_action is required" in error for error in errors)
    assert any("Scene 0 beat 0 fallback_weight must be positive" in error for error in errors)
    assert any("Scene 0 beat 0 has invalid transition" in error for error in errors)
    assert any("Scene 1 cue_text values must cover narration exactly" in error for error in errors)


def test_narrative_validation_discards_model_supplied_timing():
    scene = _scene()
    scene["beats"][0].update(
        {
            "alignment_status": "aligned",
            "speech_start_seconds": 99,
            "speech_end_seconds": 100,
        }
    )
    validated = validate_and_normalize_scenes([scene])[0]
    assert validated["beats"][0]["alignment_status"] == "pending"
    assert validated["beats"][0]["speech_start_seconds"] is None


def test_align_scene_beats_uses_tts_timestamps():
    validated = validate_and_normalize_scenes([_scene()])[0]
    aligned = align_scene_beats(validated)

    assert aligned["alignment_coverage"] == 1.0
    assert aligned["beats"][0]["speech_start_seconds"] == 0.195
    assert aligned["beats"][0]["speech_end_seconds"] == 0.725
    assert aligned["beats"][1]["speech_start_seconds"] == 0.985
    assert aligned["beats"][1]["speech_end_seconds"] == 1.695
    assert all(beat["alignment_status"] == "aligned" for beat in aligned["beats"])
    validate_scenes_for_codegen([aligned])


def test_align_scene_beats_interpolates_when_timestamps_missing():
    scene = validate_and_normalize_scenes([_scene(word_timestamps=[])])[0]
    aligned = align_scene_beats(scene)

    assert aligned["alignment_coverage"] == 0.0
    assert aligned["beats"][0]["speech_start_seconds"] == 0.0
    assert aligned["beats"][0]["speech_end_seconds"] == 1.0
    assert aligned["beats"][1]["speech_start_seconds"] == 1.0
    assert aligned["beats"][1]["speech_end_seconds"] == 2.0
    assert all(beat["alignment_status"] == "interpolated" for beat in aligned["beats"])


def test_align_scene_beats_handles_whitespace_and_full_width_punctuation():
    scene = _scene(
        narration="你好，\n语音测试",
        beats=[
            {
                "beat_index": 0,
                "cue_text": "你好,\n",
                "visual_action": "问候出现。",
            },
            {
                "beat_index": 1,
                "cue_text": "语音测试",
                "visual_action": "测试出现。",
            },
        ],
    )
    validated = validate_and_normalize_scenes([scene])[0]
    aligned = align_scene_beats(validated)
    assert aligned["alignment_coverage"] == 1.0


def test_codegen_validation_rejects_unresolved_alignment():
    scene = validate_and_normalize_scenes([_scene()])[0]
    with pytest.raises(ValueError, match="unresolved alignment"):
        validate_scenes_for_codegen([scene])
