from __future__ import annotations

import json
import os

from app.engines.render.base import SceneInput
from app.engines.render.factory import get_render_engine

VALIDATE_TOOL_NAME = "mcp__codegen__validate"


def scene_filename(index: int) -> str:
    return f"scene_{index:02d}.py"


def _engine_constraints(render_engine: str, aspect_ratio: str) -> str:
    """取提示词模式同款的引擎约束（代码规范 + 画幅规则）。"""
    from app.engines.ai.chat_provider import ChatAIProvider, _load_engine_specs

    _, code_prompts = _load_engine_specs()
    parts = [code_prompts.get(render_engine, "").strip()]
    parts.append(
        ChatAIProvider._build_aspect_ratio_prompt(aspect_ratio, render_engine).strip()
    )
    return "\n\n".join(p for p in parts if p)


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

    # 引擎约束：与提示词模式喂给模型的是同一份（engine_specs/<engine>.yaml 的
    # code_prompt + 画幅推导出的画布/安全区规则）。缺了这段，Agent 拿不到代码
    # 契约与 API 版本约束，会写出能通过校验却渲染不出画面的代码。
    engine_rules = _engine_constraints(render_engine, aspect_ratio)
    if engine_rules:
        lines.append("## 引擎约束")
        lines.append("")
        lines.append(engine_rules)
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
        # 并非只读：validate 会落盘脚本并真正执行渲染引擎的校验子进程
        # （manim.py 的 validate_code 会 create_subprocess_exec 跑 python driver）。
        annotations=ToolAnnotations(readOnlyHint=False),
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
