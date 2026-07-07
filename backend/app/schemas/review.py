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


class SceneReviewAnnotation(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    scene_index: int
    narrative_issue: Optional[str] = None
    code_issue: Optional[str] = None

    @model_validator(mode="after")
    def trim_empty_fields(self):
        if self.narrative_issue is not None:
            self.narrative_issue = self.narrative_issue.strip() or None
        if self.code_issue is not None:
            self.code_issue = self.code_issue.strip() or None
        return self


class ReviewRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    gate: Literal["narrative", "code", "video"]
    verdict: Literal["approved", "rejected", "abandoned", "retry"]
    rejection_type: Optional[str] = None
    rejection_detail: Optional[str] = None
    target_stage: Optional[Literal["narrative", "code"]] = None
    fact_check_verdicts: Optional[list[FactCheckVerdict]] = None
    edited_scenes: Optional[list[EditedNarrativeScene]] = None
    edited_code_scenes: Optional[list[EditedCodeScene]] = None
    scene_annotations: Optional[list[SceneReviewAnnotation]] = None

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
        if self.scene_annotations is not None:
            self.scene_annotations = [
                item for item in self.scene_annotations
                if item.narrative_issue or item.code_issue
            ]
        return self


class ReviewResponse(BaseModel):
    status: str
    project_id: str
