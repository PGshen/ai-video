from app.schemas.narrative import NarrativeVersionSchema, NarrativeSceneSchema
import pytest
from pydantic import ValidationError

from app.schemas.review import ReviewRequest, EditedNarrativeScene
from uuid import uuid4
from datetime import datetime, timezone


def test_narrative_version_schema_from_dict():
    data = {
        "id": str(uuid4()),
        "project_id": str(uuid4()),
        "version_number": 1,
        "scenes": [
            {
                "scene_index": 0,
                "narration": "旁白",
                "description": "描述",
                "beats": [
                    {
                        "beat_index": 0,
                        "cue_text": "旁白",
                        "visual_action": "文字出现",
                    }
                ],
                "estimated_duration_seconds": 8.0,
            }
        ],
        "fact_checks": [],
        "ai_model": "deepseek",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    schema = NarrativeVersionSchema.model_validate(data)
    assert schema.version_number == 1
    assert schema.scenes[0].scene_index == 0


def test_review_request_narrative_gate():
    req = ReviewRequest(
        gate="narrative",
        verdict="approved",
        edited_scenes=[
            EditedNarrativeScene(
                scene_index=0,
                narration="旁白修改",
                description="描述修改",
                beats=[
                    {
                        "beat_index": 0,
                        "cue_text": "旁白修改",
                        "visual_action": "文字更新",
                    }
                ],
            )
        ],
    )
    assert req.gate == "narrative"
    assert req.edited_scenes[0].scene_index == 0


def test_content_rejection_requires_reason():
    with pytest.raises(ValidationError, match="Content rejection requires a rejection reason"):
        ReviewRequest(
            gate="narrative",
            verdict="rejected",
            rejection_type="content",
            rejection_detail="  ",
        )


def test_content_rejection_trims_reason():
    req = ReviewRequest(
        gate="narrative",
        verdict="rejected",
        rejection_type="content",
        rejection_detail="  叙事节奏太平  ",
    )

    assert req.rejection_detail == "叙事节奏太平"


def test_review_request_code_gate_with_target_stage():
    req = ReviewRequest(gate="code", verdict="rejected", target_stage="code")
    assert req.target_stage == "code"
