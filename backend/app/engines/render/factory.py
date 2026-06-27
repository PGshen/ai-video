from app.engines.render.manim import ManimRenderEngine


def get_render_engine(engine_name: str = "manim") -> ManimRenderEngine:
    if engine_name == "manim":
        return ManimRenderEngine()
    raise ValueError(f"Unknown render engine: {engine_name}")
