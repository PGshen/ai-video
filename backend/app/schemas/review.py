from pydantic import BaseModel, ConfigDict, model_validator
from pydantic.alias_generators import to_camel
from typing import Literal, Optional
from app.schemas.narrative import NarrativeBeatSchema


class FactCheckVerdict(BaseModel):
    index: int
    verdict: str
    note: str = ""


class EditedNarrativeScene(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    scene_index: int
    narration: str
    description: str
    beats: list[NarrativeBeatSchema]
    estimated_duration_seconds: Optional[float] = None


class EditedCodeScene(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    scene_index: int
    code: str


class ReviewRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    gate: Literal["narrative", "code", "video"]
    verdict: Literal["approved", "rejected", "abandoned"]
    rejection_type: Optional[str] = None
    rejection_detail: Optional[str] = None
    target_stage: Optional[Literal["narrative", "code"]] = None
    fact_check_verdicts: Optional[list[FactCheckVerdict]] = None
    edited_scenes: Optional[list[EditedNarrativeScene]] = None
    edited_code_scenes: Optional[list[EditedCodeScene]] = None

    @model_validator(mode="after")
    def validate_content_rejection_reason(self):
        if (
            self.verdict == "rejected"
            and self.rejection_type == "content"
            and not (self.rejection_detail or "").strip()
        ):
            raise ValueError("Content rejection requires a rejection reason")
        if self.rejection_detail is not None:
            self.rejection_detail = self.rejection_detail.strip()
        return self


class ReviewResponse(BaseModel):
    status: str
    project_id: str
