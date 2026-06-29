from typing import Protocol
from dataclasses import dataclass


@dataclass
class SceneAudio:
    scene_index: int
    audio_path: str
    duration_seconds: float


@dataclass
class SceneInput:
    scene_index: int
    narration: str
    description: str
    code: str
    audio: SceneAudio | None


@dataclass
class RenderRequest:
    scenes: list[SceneInput]
    output_format: str
    resolution: tuple[int, int]
    fps: int = 30


@dataclass
class RenderResult:
    success: bool
    output_path: str | None
    duration_seconds: float | None
    error_message: str | None
    render_log: str


class RenderResultWithBytes(RenderResult):
    def __init__(self, *args, video_bytes: bytes, **kwargs):
        super().__init__(*args, **kwargs)
        self.video_bytes = video_bytes


class RenderEngine(Protocol):
    @property
    def engine_name(self) -> str: ...

    async def validate_code(self, scenes: list[SceneInput]) -> tuple[bool, str]: ...

    async def render(self, request: RenderRequest) -> RenderResult: ...

    async def health_check(self) -> bool: ...


class EngineRegistry[T]:
    def __init__(self):
        self._engines: dict[str, T] = {}

    def register(self, engine: T) -> None:
        self._engines[engine.engine_name] = engine

    def get(self, name: str) -> T:
        if name not in self._engines:
            raise ValueError(f"Unknown engine: {name}")
        return self._engines[name]

    def list_engines(self) -> list[str]:
        return list(self._engines.keys())
