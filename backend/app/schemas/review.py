from pydantic import BaseModel
from typing import Optional


class FactCheckVerdict(BaseModel):
    index: int
    verdict: str
    note: str = ""


class ReviewRequest(BaseModel):
    gate: str
    verdict: str
    rejection_type: Optional[str] = None
    rejection_detail: Optional[str] = None
    target_stage: Optional[str] = None
    fact_check_verdicts: Optional[list[FactCheckVerdict]] = None


class ReviewResponse(BaseModel):
    status: str
    project_id: str
