import logging
import json
import re
from collections.abc import AsyncIterator
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

from app.engines.ai.base import (
    BrainstormResult, ChatClient, CodeGenerationResult, CodeRepairResult,
    NarrativeResult,
)
from app.services.narrative_validator import (
    NarrativeValidationError,
    validate_and_normalize_scenes,
)

_SPECS_DIR = Path(__file__).parent / "engine_specs"


def _load_engine_specs() -> tuple[dict[str, str], dict[str, str]]:
    """Load narrative_hint and code_prompt from engine_specs/*.yaml."""
    narrative_hints: dict[str, str] = {}
    code_prompts: dict[str, str] = {}
    if _SPECS_DIR.exists():
        for yaml_file in _SPECS_DIR.glob("*.yaml"):
            engine_name = yaml_file.stem
            try:
                data = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
            except Exception as exc:
                logger.warning("Failed to load engine spec %s: %s", yaml_file, exc)
                continue
            if "narrative_hint" in data:
                narrative_hints[engine_name] = data["narrative_hint"]
            if "code_prompt" in data:
                code_prompts[engine_name] = data["code_prompt"]
    return narrative_hints, code_prompts


def _load_engine_specs_as_class_dicts() -> tuple[dict[str, str], dict[str, str]]:
    """Load engine specs at import time for backward-compatible class attributes."""
    return _load_engine_specs()


# Backward-compatible class-level dicts (also used by tests)
_CLASS_NARRATIVE_HINTS, _CLASS_CODE_PROMPTS = _load_engine_specs_as_class_dicts()


class ChatAIProvider:
    # Class-level attributes for backward compatibility with tests
    _NARRATIVE_ENGINE_HINTS: dict[str, str] = _CLASS_NARRATIVE_HINTS
    _ENGINE_CODE_PROMPTS: dict[str, str] = _CLASS_CODE_PROMPTS
    
    _ENGINE_CODE_PROMPT_FALLBACK = (
        "- code 字段填写适合所选渲染引擎的代码片段（非完整文件），"
        "所有镜头的 code 将被顺序拼合为单个执行单元。"
        "不处理音频，渲染引擎自动注入。"
    )
    _NARRATIVE_ENGINE_HINT_FALLBACK = (
        "description 字段将用于后续渲染代码生成，必须精确描述每个元素的进场、变形、退场及跨镜头衔接关系。"
    )

    # Default style text used when project has no style_config for a category
    _DEFAULT_STYLE_COMPONENTS: dict[str, str] = {
        "color_scheme": """\
【配色系统】
请严格遵循以下配色方案：
背景主色（亮底）：#F7F3FF
亮底上的文字：#1C1433；辅助注释：#8E7DC0
核心概念色：认知紫 #6C4FD4、浅紫 #A98EE8
语义强调：错误红 #FF6B6B、警示橙 #FFB347、理性青 #4ECDC4、结论绿 #44CF6C、直觉粉 #FF9EBB
结构辅助：网格深底 #4A3880、网格亮底 #D4C5F0
配色原则：红色专用于偏差/错误，绿色专用于正确/结论，不可混用。""",
        "narrative_style": """\
【叙事风格】
整体娓娓道来，从一个反直觉的问题或现象切入，逐步建立知识体系，结尾给出有价值的启示。
旁白负责讲解，每句话清晰有力，不空洞，不重复画面文字。""",
        "pacing": """\
【叙事节奏】
目标视频时长 2-3 分钟，需要 15-20 个镜头，每个镜头旁白约 30-50 字、时长 7-10 秒。
estimated_duration_seconds 根据旁白字数和画面复杂度估算，不得少于 5 秒。""",
        "scene_structure": """\
【镜头结构】
镜头 0-1：抛出问题/反直觉现象，吸引注意
镜头 2-5：建立基础知识框架，引入关键概念
镜头 6-14：逐步深入，以动态图示和实例展开论证
镜头 15+：总结升华，给出启示或应用价值""",
        "animation_style": """\
【视觉精致度规范】
构图与层次：每个镜头须有明确的视觉层次——背景装饰层 → 主体图形层 → 文字标注层。
图形之间保持充足间距（≥ 1.5 单位），避免拥挤感。
半透明背景光晕：在主体元素后方放置 fill_opacity=0.12 的同色系大圆作衬底。
精致细节：标题镜头主标题下方配细分隔线；关键概念节点使用双圆结构。
多元素错落入场，节点+连线+标注分三步出现。""",
    }

    def __init__(
        self,
        client: ChatClient,
        script_max_tokens: int = 8192,
        json_max_tokens: int = 4096,
        narrative_validation_retries: int = 1,
    ):
        self.client = client
        self.script_max_tokens = script_max_tokens
        self.json_max_tokens = json_max_tokens
        self.narrative_validation_retries = max(0, narrative_validation_retries)
        self._narrative_engine_hints, self._engine_code_prompts = _load_engine_specs()

    @property
    def engine_name(self) -> str:
        return self.client.engine_name

    @property
    def model_name(self) -> str:
        return self.client.model_name

    def _build_narrative_system_prompt(
        self,
        render_engine: str,
        style_components: dict[str, str],
    ) -> str:
        defaults = self._DEFAULT_STYLE_COMPONENTS
        narrative_style = style_components.get("narrative_style", defaults.get("narrative_style", ""))
        pacing = style_components.get("pacing", defaults.get("pacing", ""))
        scene_structure = style_components.get("scene_structure", defaults.get("scene_structure", ""))
        color_scheme = style_components.get("color_scheme", defaults.get("color_scheme", ""))
        engine_hint = self._narrative_engine_hints.get(render_engine, self._NARRATIVE_ENGINE_HINT_FALLBACK)

        parts = [
            "你是知识视频叙事脚本生成器。请严格输出 JSON object，不要输出 Markdown。",
            "",
            'JSON 格式示例：\n{{\n  "scenes": [\n    {{\n      "scene_index": 0,\n      "narration": "如果现场只有你一个人，责任几乎全部落在你身上。",\n      "description": "用人物和责任计量环解释唯一旁观者承担全部责任。",\n      "estimated_duration_seconds": 8.0,\n      "beats": [\n        {{\n          "beat_index": 0,\n          "cue_text": "如果现场只有你一个人，",\n          "visual_action": "中央出现唯一旁观者，周围保持空旷。",\n          "emphasis": "唯一旁观者",\n          "transition": "reveal",\n          "fallback_weight": 1.0\n        }},\n        {{\n          "beat_index": 1,\n          "cue_text": "责任几乎全部落在你身上。",\n          "visual_action": "责任计量环增长至100%，人物成为唯一高亮主体。",\n          "emphasis": "100%责任",\n          "transition": "continue",\n          "fallback_weight": 1.0\n        }}\n      ]\n    }}\n  ],\n  "fact_checks": [\n    {{\n      "claim_text": "需要核查的具体论断",\n      "scene_index": 0,\n      "source_url": null,\n      "source_description": "建议核查来源或说明",\n      "confidence": "medium",\n      "is_hypothesis": false,\n      "assumptions": null,\n      "controversy": null,\n      "reviewer_verdict": null,\n      "reviewer_note": null\n    }}\n  ]\n}}',
            "",
        ]
        if narrative_style:
            parts.append(narrative_style)
        if pacing:
            parts.append(pacing)
        if scene_structure:
            parts.append(scene_structure)
        if color_scheme:
            parts.append(color_scheme)
            parts.append("颜色名与 Hex 对照（description 中用颜色名即可，代码生成阶段再转 Hex）")
        parts += [
            "",
            "【语义节拍契约】",
            "- 每个 scene 除 narration、description 外必须输出非空 beats 数组",
            "- 普通镜头输出 2-4 个 beats，纯标题或结尾镜头可输出 1-2 个",
            "- cue_text 必须逐字取自 narration，并按顺序完整覆盖 narration；不得概括、改写或遗漏",
            "- visual_action 只描述这一句旁白发生时画面产生的知识性变化",
            "- 每个 beat 必须推进信息、关系或状态，禁止用“保持画面”凑数量",
            "- beat_index 在每个 scene 内必须从 0 连续递增",
            "- transition 只能是 continue、transform、reveal、replace、exit 之一",
            "- 不输出绝对时间；时间由 TTS 完成后计算",
            "- visual_action 不得出现渲染引擎 API、类名、组件名或代码语法",
        ]
        parts.append(engine_hint)
        parts += [
            "",
            "要求：",
            "- scenes 是镜头数组，scene_index 从 0 连续递增；镜头数量遵循 pacing 组件",
            "- 每个镜头包含 narration、description、beats、estimated_duration_seconds",
            "- fact_checks 覆盖脚本中的关键事实论断和可能争议点",
            "- 只能输出合法 JSON object",
        ]
        return "\n".join(parts)

    def _build_code_system_prompt(
        self,
        render_engine: str,
        style_components: dict[str, str],
    ) -> str:
        defaults = self._DEFAULT_STYLE_COMPONENTS
        color_scheme = style_components.get("color_scheme", defaults.get("color_scheme", ""))
        animation_style = style_components.get("animation_style", defaults.get("animation_style", ""))
        engine_hint = self._engine_code_prompts.get(render_engine, self._ENGINE_CODE_PROMPT_FALLBACK)

        parts = [
            "你是知识视频代码生成器。请严格输出 JSON object，不要输出 Markdown。",
            "",
            "你将收到一个知识视频的所有镜头叙事脚本，需要为每个镜头生成渲染代码片段。",
            "",
            'JSON 格式：\n{{\n  "codes": [\n    "镜头 0 的代码片段",\n    "镜头 1 的代码片段"\n  ]\n}}',
            "",
            "codes 数组长度必须与输入 scenes 数组长度完全一致，按 scene_index 顺序对应。",
            "",
            f"渲染引擎：{render_engine}",
        ]
        if color_scheme:
            parts.append(color_scheme)
        if animation_style:
            parts.append(animation_style)
        parts += [
            "",
            "【语义节拍时间执行契约】",
            "- scene 中 beats 已按顺序给出真实 speech 时间和建议 animation 时间",
            "- 每个 beat 的 visual_action 必须在自己的 animation 时间窗口内发生",
            "- 关键词对应的主要视觉结果最迟应在 speech_end_seconds 前清晰可见",
            "- 不得在第一个 beat 中一次性完成整个镜头的全部动画",
            "- 相邻 beat 优先通过已有元素的移动、变形、分裂、聚合或强调连续推进",
            "- 最后一个 beat 结束后可保持最终画面，但不得用无意义循环填满时间",
            "- alignment_status 为 interpolated 时仍使用给出的时间",
        ]
        parts.append(engine_hint)
        parts += [
            "",
            "【代码拼合规则】",
            "所有镜头的 code 片段将被渲染引擎按顺序拼合为单个执行单元，每段之间插入注释分隔符。",
            "音频由渲染引擎在每个镜头开始时自动注入，code 里不处理音频。",
            "",
            "【音画同步规则】",
            "每个镜头 JSON 包含 duration_seconds 字段，代表该镜头旁白音频的时长（秒）。",
            "动画总时长（所有 run_time 与 self.wait 之和）必须 ≤ duration_seconds。",
            "渲染引擎会在每个镜头末尾自动补齐剩余时间，因此禁止在镜头末尾添加用于补齐音频时长的 self.wait()。",
            "",
            "要求：",
            "- 严格按照每个镜头的 description 实现动画逻辑",
            "- 充分利用跨镜头变量复用",
            "- 每个 code 片段不写外层结构（详见各引擎规范）",
            "- 只能输出合法 JSON object",
        ]
        return "\n".join(parts)

    async def generate_narrative(
        self,
        topic_title: str,
        topic_description: str,
        render_engine: str,
        rejection_context: dict | None = None,
        narrative_context: list[dict] | None = None,
        style_components: dict[str, str] | None = None,
    ) -> NarrativeResult:
        system_prompt = self._build_narrative_system_prompt(
            render_engine=render_engine,
            style_components=style_components or {},
        )

        user_payload: dict = {
            "topic_title": topic_title,
            "topic_description": topic_description,
            "render_engine": render_engine,
        }
        if rejection_context:
            user_payload["rejection_context"] = rejection_context
            user_note = "（注意：这是一次重新生成，请参考 rejection_context 中的驳回原因修正叙事结构）"
        else:
            user_note = ""

        context_note = ""
        if narrative_context:
            snippets_text = "\n---\n".join(
                item["text"] for item in narrative_context if item.get("text")
            )
            if snippets_text:
                context_note = (
                    "\n\n以下是创作者标注的参考内容，请在叙事中参考这些观点和表述方式：\n\n"
                    + snippets_text
                )

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"请为以下选题生成知识视频叙事脚本 JSON{user_note}：\n"
                + json.dumps(user_payload, ensure_ascii=False)
                + context_note,
            },
        ]

        for attempt in range(self.narrative_validation_retries + 1):
            content = await self.client.create_chat_completion(
                messages=messages,
                response_format={"type": "json_object"},
                max_tokens=self.script_max_tokens,
            )
            try:
                payload = parse_json_object(content)
                scenes = payload.get("scenes")
                fact_checks = payload.get("fact_checks")
                structure_errors = []
                normalized_scenes = None
                if not isinstance(scenes, list):
                    structure_errors.append("Narrative response scenes must be an array")
                else:
                    try:
                        normalized_scenes = validate_and_normalize_scenes(scenes)
                    except NarrativeValidationError as exc:
                        structure_errors.extend(exc.errors)
                if not isinstance(fact_checks, list):
                    structure_errors.append("Narrative response fact_checks must be an array")
                if structure_errors:
                    raise NarrativeValidationError(structure_errors)

                if normalized_scenes is None:
                    raise RuntimeError("Narrative scenes were not normalized")
                return NarrativeResult(
                    scenes=normalized_scenes,
                    fact_checks=fact_checks,
                )
            except ValueError as exc:
                if attempt >= self.narrative_validation_retries:
                    raise

                validation_errors = (
                    list(exc.errors)
                    if isinstance(exc, NarrativeValidationError)
                    else [str(exc)]
                )
                logger.warning(
                    "Narrative response validation failed; requesting correction "
                    "(attempt %d/%d): %s",
                    attempt + 1,
                    self.narrative_validation_retries,
                    "; ".join(validation_errors),
                )
                messages.extend(
                    [
                        {"role": "assistant", "content": content},
                        {
                            "role": "user",
                            "content": (
                                "上一次输出未通过校验。请根据以下全部错误修改上一份 JSON，"
                                "并返回修正后的完整 JSON object；不要解释，不要遗漏未报错的内容：\n"
                                + json.dumps(
                                    {"validation_errors": validation_errors},
                                    ensure_ascii=False,
                                    indent=2,
                                )
                            ),
                        },
                    ]
                )

        raise RuntimeError("Narrative validation loop exited unexpectedly")

    async def generate_code(
        self,
        scenes: list[dict],
        render_engine: str,
        style_components: dict[str, str] | None = None,
    ) -> CodeGenerationResult:
        system_prompt = self._build_code_system_prompt(
            render_engine=render_engine,
            style_components=style_components or {},
        )
        content = await self.client.create_chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": "请为以下镜头脚本生成渲染代码 JSON：\n"
                    + json.dumps({"scenes": scenes}, ensure_ascii=False),
                },
            ],
            response_format={"type": "json_object"},
            max_tokens=self.script_max_tokens,
        )
        payload = parse_json_object(content)
        codes = payload.get("codes")
        if not isinstance(codes, list):
            raise ValueError("Code generation response must contain codes array")
        if len(codes) != len(scenes):
            raise ValueError(
                f"Code generation returned {len(codes)} codes for {len(scenes)} scenes"
            )
        if any(not isinstance(code, str) or not code.strip() for code in codes):
            raise ValueError("Every generated scene code must be a non-empty string")
        return CodeGenerationResult(codes=codes)

    async def repair_code(
        self,
        scenes: list[dict],
        render_engine: str,
        error_message: str,
        style_components: dict[str, str] | None = None,
    ) -> CodeRepairResult:
        engine_hint = self._engine_code_prompts.get(render_engine, self._ENGINE_CODE_PROMPT_FALLBACK)
        defaults = self._DEFAULT_STYLE_COMPONENTS
        color_scheme = (style_components or {}).get("color_scheme", defaults.get("color_scheme", ""))
        animation_style = (style_components or {}).get("animation_style", defaults.get("animation_style", ""))
        system_prompt = f"""\
你是知识视频渲染代码修复专家。请严格输出 JSON object，不要输出 Markdown。

你会收到一次整体渲染失败的完整错误信息，以及按执行顺序排列的全部镜头。

你的任务：
1. 结合错误信息审查全部镜头，定位直接错误、上游根因和可能由同类写法引发后续失败的镜头。
2. 尽可能在这一次响应中修复全部可能有错误的镜头。
3. 保持旁白、画面意图、镜头顺序和跨镜头变量关系；只修改需要修复的代码。
4. repairs 仅列出需要修改的镜头；每个 scene_index 必须来自输入且不得重复。
5. code 必须是可直接替换原镜头 code 的完整代码片段。
6. explanation 用简短中文说明该镜头的问题和修复方式。

JSON 格式：
{{
  "repairs": [
    {{
      "scene_index": 0,
      "code": "修复后的完整代码片段",
      "explanation": "问题与修复说明"
    }}
  ]
}}

渲染引擎：{render_engine}
{color_scheme}
{animation_style}
{engine_hint}

只能输出合法 JSON object。"""
        content = await self.client.create_chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": "请一次性检查并修复所有可能出错的镜头：\n"
                    + json.dumps(
                        {
                            "render_engine": render_engine,
                            "error_message": error_message,
                            "scenes": scenes,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            response_format={"type": "json_object"},
            max_tokens=self.script_max_tokens,
        )
        payload = parse_json_object(content)
        repairs = payload.get("repairs")
        if not isinstance(repairs, list):
            raise ValueError("Code repair response must contain repairs array")

        valid_indices = {
            scene.get("scene_index")
            for scene in scenes
            if isinstance(scene, dict) and isinstance(scene.get("scene_index"), int)
        }
        seen_indices: set[int] = set()
        normalized: list[dict] = []
        for repair in repairs:
            if not isinstance(repair, dict):
                raise ValueError("Each code repair must be an object")
            scene_index = repair.get("scene_index")
            code = repair.get("code")
            explanation = repair.get("explanation")
            if (
                scene_index not in valid_indices
                or scene_index in seen_indices
                or not isinstance(code, str)
                or not code.strip()
                or not isinstance(explanation, str)
            ):
                raise ValueError("Invalid code repair item")
            seen_indices.add(scene_index)
            normalized.append({"scene_index": scene_index, "code": code, "explanation": explanation})
        return CodeRepairResult(repairs=normalized)

    async def brainstorm_topics(self, topic_direction: str, count: int) -> BrainstormResult:
        system_prompt = """\
你是知识视频选题策划助手。请严格输出 JSON object，不要输出 Markdown。

JSON 格式示例：
{
  "candidates": [
    {
      "title": "一个反直觉、可论证、适合动画化的选题标题",
      "description": "一句话说明选题切入角度和知识价值",
      "tags": ["物理", "认知"]
    }
  ]
}

要求：
- candidates 数量必须匹配用户要求。
- title 适合自媒体知识视频标题，避免空泛。
- description 说明反直觉点、可论证点或可视化潜力。
- tags 使用 2 到 5 个中文短标签。
- 只能输出合法 JSON object。"""
        user_prompt = f"请围绕「{topic_direction}」生成 {count} 个候选选题 JSON。"
        content = await self.client.create_chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            max_tokens=self.json_max_tokens,
        )
        payload = parse_json_object(content)
        candidates = payload.get("candidates")
        if not isinstance(candidates, list):
            raise ValueError("Brainstorm response must contain candidates array")
        return BrainstormResult(candidates=candidates[:count])

    async def research_topic(
        self,
        topic_title: str,
        topic_description: str,
        conversation_history: list[dict],
        new_message: str,
        use_default_prompt: bool = False,
        system_prompt: str | None = None,
    ) -> AsyncIterator[str]:
        if system_prompt is None:
            system_prompt = (
                "你是一位知识视频选题研究助手。请基于事实、理论背景和可视化潜力回答，"
                "输出 Markdown。"
            )

        messages = [{"role": "system", "content": system_prompt}]
        for item in conversation_history:
            role = item.get("role")
            content = item.get("content")
            if role in {"user", "assistant"} and isinstance(content, str):
                messages.append({"role": role, "content": content})
        messages.append(
            {
                "role": "user",
                "content": (
                    f"当前选题：{topic_title}\n"
                    f"选题描述：{topic_description or '无'}\n\n"
                    f"问题：{new_message}"
                ),
            }
        )

        async for chunk in self.client.stream_chat_completion(messages):
            yield chunk


def parse_json_object(content: str) -> dict:
    text = content.strip()
    fence_match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("AI response is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("AI JSON response must be an object")
    return payload
