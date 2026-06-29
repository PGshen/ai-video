from app.engines.render.manim import ManimRenderEngine
from app.engines.render.remotion import RemotionRenderEngine


def get_render_engine(engine_name: str = "manim"):
    if engine_name == "manim":
        return ManimRenderEngine()
    if engine_name == "remotion":
        return RemotionRenderEngine()
    raise ValueError(f"Unknown render engine: {engine_name}")
