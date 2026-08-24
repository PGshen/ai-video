from __future__ import annotations

import json
import os

from app.engines.render.base import SceneInput
from app.engines.render.factory import get_render_engine

VALIDATE_TOOL_NAME = "mcp__codegen__validate"


def scene_filename(index: int) -> str:
    return f"scene_{index:02d}.py"


def write_sandbox(
    workdir: str,
    *,
    scenes: list[dict],
    style_components: dict[str, str],
    aspect_ratio: str,
    render_engine: str,
) -> None:
    """写入 input.json / STYLE.md，并建好空的 scenes/ 目录。"""
    payload = {
        "render_engine": render_engine,
        "aspect_ratio": aspect_ratio,
        "scenes": [
            {
                "scene_index": s["scene_index"],
                "narration": s.get("narration", ""),
                "description": s.get("description", ""),
                "duration_seconds": s.get("duration_seconds"),
                "beats": s.get("beats", []),
            }
            for s in scenes
        ],
    }
    with open(os.path.join(workdir, "input.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    lines = [
        "# 风格与约束",
        "",
        f"- 渲染引擎：{render_engine}",
        f"- 画幅：{aspect_ratio}",
        "",
    ]
    for category, text in style_components.items():
        lines.append(f"## {category}")
        lines.append("")
        lines.append(text)
        lines.append("")
    with open(os.path.join(workdir, "STYLE.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    os.makedirs(os.path.join(workdir, "scenes"), exist_ok=True)


def read_scene_codes(workdir: str, scene_count: int) -> list[str]:
    """按 scene_index 顺序回读代码；文件缺失返回空串。"""
    codes: list[str] = []
    for i in range(scene_count):
        path = os.path.join(workdir, "scenes", scene_filename(i))
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                codes.append(f.read())
        else:
            codes.append("")
    return codes


async def validate_workdir(
    workdir: str, scenes: list[dict], render_engine: str
) -> tuple[bool, str]:
    """回读 scenes/ 并调渲染引擎校验。平台侧与 MCP 工具共用同一条路径。"""
    codes = read_scene_codes(workdir, len(scenes))
    missing = [i for i, code in enumerate(codes) if not code.strip()]
    if missing:
        names = ", ".join(scene_filename(i) for i in missing)
        return False, f"以下镜头文件缺失或为空：{names}"

    scene_inputs = [
        SceneInput(
            scene_index=i,
            narration=scenes[i].get("narration", ""),
            description=scenes[i].get("description", ""),
            code=codes[i],
            audio=None,
        )
        for i in range(len(scenes))
    ]
    return await get_render_engine(render_engine).validate_code(scene_inputs)


def build_validate_server(workdir: str, scenes: list[dict], render_engine: str):
    """构造 in-process MCP server，返回 (server, tool_name)。"""
    from claude_agent_sdk import ToolAnnotations, create_sdk_mcp_server, tool

    @tool(
        "validate",
        "校验 scenes/ 目录下当前全部镜头代码。返回通过或详细报错（报错中会标出出问题的镜头编号）。修改代码后必须再次调用本工具确认通过。",
        {},
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def validate(args):
        is_valid, errors = await validate_workdir(workdir, scenes, render_engine)
        if is_valid:
            return {"content": [{"type": "text", "text": "校验通过。"}]}
        return {
            "content": [{"type": "text", "text": f"校验失败：\n{errors}"}],
            "is_error": True,
        }

    server = create_sdk_mcp_server(name="codegen", version="1.0.0", tools=[validate])
    return server, VALIDATE_TOOL_NAME
