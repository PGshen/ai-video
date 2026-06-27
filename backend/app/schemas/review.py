from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from typing import Literal, Optional


class FactCheckVerdict(BaseModel):
    index: int
    verdict: str
    note: str = ""


class EditedNarrativeScene(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    scene_index: int
    narration: str
    description: str
    estimated_duration_seconds: Optional[float] = None


class ReviewRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    gate: Literal["narrative", "script", "video"]
    verdict: Literal["approved", "rejected", "abandoned"]
    rejection_type: Optional[str] = None
    rejection_detail: Optional[str] = None
    target_stage: Optional[str] = None
    fact_check_verdicts: Optional[list[FactCheckVerdict]] = None
    edited_scenes: Optional[list[EditedNarrativeScene]] = None


class ReviewResponse(BaseModel):
    status: str
    project_id: str
