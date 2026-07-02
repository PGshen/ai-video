from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class NarrativeBeatSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    beat_index: int
    cue_text: str
    visual_action: str
    emphasis: Optional[str] = None
    transition: Literal["continue", "transform", "reveal", "replace", "exit"] = "continue"
    fallback_weight: float = 1.0

    cue_start_char: Optional[int] = None
    cue_end_char: Optional[int] = None
    speech_start_seconds: Optional[float] = None
    speech_end_seconds: Optional[float] = None
    animation_start_seconds: Optional[float] = None
    animation_end_seconds: Optional[float] = None
    alignment_status: Literal["pending", "aligned", "interpolated", "failed"] = "pending"
