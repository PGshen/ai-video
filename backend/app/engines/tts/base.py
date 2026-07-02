from typing import Protocol
from dataclasses import dataclass, field


@dataclass
class TTSRequest:
    text: str
    voice: str = "default"
    speed: float = 1.0


@dataclass
class WordTimestamp:
    word: str
    start_time: float
    end_time: float
    confidence: float | None = None


@dataclass
class TTSResult:
    success: bool
    output_path: str | None
    duration_seconds: float | None
    error_message: str | None
    audio_bytes: bytes = field(default=b"")
    word_timestamps: list[WordTimestamp] = field(default_factory=list)


class TTSEngine(Protocol):
    @property
    def engine_name(self) -> str: ...

    async def synthesize(self, request: TTSRequest) -> TTSResult: ...

    async def health_check(self) -> bool: ...
