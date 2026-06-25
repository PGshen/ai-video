from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from typing import Optional


class FactCheckVerdict(BaseModel):
    index: int
    verdict: str
    note: str = ""


class ReviewRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    gate: str
    verdict: str
    rejection_type: Optional[str] = None
    rejection_detail: Optional[str] = None
    target_stage: Optional[str] = None
    fact_check_verdicts: Optional[list[FactCheckVerdict]] = None


class ReviewResponse(BaseModel):
    status: str
    project_id: str
