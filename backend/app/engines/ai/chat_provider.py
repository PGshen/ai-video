import logging
import json
import re
from collections.abc import AsyncIterator
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

from app.engines.ai.base import (
    BrainstormResult, ChatClient, CodeGenerationResult, CodeRepairResult,
    NarrativeResult, StyleAssistantResult, ai_business,
)
from app.engines.ai.structured_output import (
    BRAINSTORM_SCHEMA,
    CODE_GENERATION_SCHEMA,
    CODE_REPAIR_SCHEMA,
    NARRATIVE_SCHEMA,
    STYLE_ASSISTANT_SCHEMA,
    response_format_for,
)
from app.services.narrative_validator import (
    NarrativeValidationError,
    validate_and_normalize_scenes,
)
from app.video_format import normalize_aspect_ratio, resolution_for_aspect_ratio

_SPECS_DIR = Path(__file__).parent / "engine_specs"

_CODEGEN_SCENE_FIELDS = (
    "scene_index",
    "narration",
    "description",
    "duration_seconds",
    "beats",
    "code",
)


def _strip_codegen_fields(scenes: list[dict]) -> list[dict]:
    """Drop TTS-only fields (e.g. word_timestamps) that code generation/repair never uses."""
    return [
        {k: scene[k] for k in _CODEGEN_SCENE_FIELDS if k in scene}
        for scene in scenes
    ]


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
    _JSON_ESCAPE_RULE = (
        "- 字符串值中如需引用或强调用词，一律使用「」『』中文书名号/引号，"
        "禁止使用英文直引号 \" 包裹文字；确需输出英文双引号或反斜杠时必须按 JSON 规则转义（\\\" 、\\\\），"
        "确保每个字符串值本身是合法转义的 JSON 字符串"
    )

    @staticmethod
    def _build_aspect_ratio_prompt(aspect_ratio: str, render_engine: str) -> str:
        normalized = normalize_aspect_ratio(aspect_ratio)
        width, height = resolution_for_aspect_ratio(normalized)
        orientation = "竖屏 9:16（手机端）" if normalized == "portrait" else "横屏 16:9"
        if normalized == "portrait":
            composition_rules = (
                "- 采用自上而下的纵向视觉动线，优先使用上下分区、单列卡片和垂直流程\n"
                "- 避免依赖横向空间的左右多列、超宽坐标轴和长横排关系；对比内容优先上下排列\n"
                "- 主体、关键词和关键动作放在画面中部安全区，顶部和底部预留移动端界面遮挡空间\n"
                "- 每屏减少并列元素数量，文字短句化并适当增大字号，保证手机小屏可读"
            )
        else:
            composition_rules = (
                "- 充分利用横向空间，可使用左右对比、横向时间线和多列关系图\n"
                "- 主体保持在中心安全区，避免关键信息贴近左右边缘"
            )

        engine_rules = ""
        if render_engine == "manim":
            logical_width = 4.5 if normalized == "portrait" else 14.222
            safe_x = "[-1.9, 1.9]" if normalized == "portrait" else "[-6.0, 6.0]"
            fit_width = "3.6" if normalized == "portrait" else "11"
            engine_rules = (
                f"\n- Manim 逻辑画布约为 {logical_width:g} × 8 单位；"
                f"安全区 x ∈ {safe_x}、y ∈ [-3.5, 3.5]，大型 VGroup 最大宽度 {fit_width}"
            )
        elif render_engine == "remotion":
            engine_rules = (
                f"\n- Remotion 必须通过 useVideoConfig() 读取 width={width}、height={height}；"
                "所有坐标、尺寸和 SVG viewBox 均从 width/height 推导，不得沿用固定横屏坐标"
            )

        return (
            "【画幅与构图规范（最高优先级）】\n"
            f"- 本项目画幅：{orientation}，最终视频尺寸：{width} × {height} px\n"
            "- 本节覆盖引擎通用规范中任何固定画布尺寸、坐标和横屏布局示例\n"
            f"{composition_rules}"
            f"{engine_rules}"
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
【叙事蓝图】
一、叙事风格
整体娓娓道来，从一个反直觉的问题或现象切入，逐步建立知识体系，结尾给出有价值的启示。
旁白负责讲解，每句话清晰有力，不空洞，不重复画面文字。
二、叙事节奏
目标视频时长 2-3 分钟，需要 15-20 个镜头，每个镜头旁白约 30-50 字、时长 7-10 秒。
estimated_duration_seconds 根据旁白字数和画面复杂度估算，不得少于 5 秒。
三、镜头结构
镜头 0-1：抛出问题/反直觉现象，吸引注意
镜头 2-5：建立基础知识框架，引入关键概念
镜头 6-14：逐步深入，以动态图示和实例展开论证
镜头 15+：总结升华，给出启示或应用价值""",
        "exemplar": """\
{
  "scenes": [
    {
      "scene_index": 0,
      "narration": "如果现场只有你一个人，责任几乎全部落在你身上。",
      "description": "用人物和责任计量环解释唯一旁观者承担全部责任。",
      "estimated_duration_seconds": 8.0,
      "beats": [
        {
          "beat_index": 0,
          "cue_text": "如果现场只有你一个人，",
          "visual_action": "画面中央从轮廓到填充逐步绘制出唯一的旁观者，脚下一圈淡色涟漪缓缓扩散一次，四周保持空旷。",
          "emphasis": "唯一旁观者",
          "transition": "reveal",
          "fallback_weight": 1.0
        },
        {
          "beat_index": 1,
          "cue_text": "责任几乎全部落在你身上。",
          "visual_action": "人物脚下升起责任计量环，数值从0%连续增长到100%约2秒，到达时环体加粗、人物提亮成为唯一高亮主体。",
          "emphasis": "100%责任",
          "transition": "continue",
          "fallback_weight": 1.0
        }
      ]
    }
  ],
  "fact_checks": [
    {
      "claim_text": "需要核查的具体论断",
      "scene_index": 0,
      "source_url": null,
      "source_description": "建议核查来源或说明",
      "confidence": "medium",
      "is_hypothesis": false,
      "assumptions": null,
      "controversy": null,
      "reviewer_verdict": null,
      "reviewer_note": null
    }
  ]
}""",
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
        content_max_tokens: int = 8192,
        json_max_tokens: int = 4096,
        narrative_validation_retries: int = 1,
    ):
        self.client = client
        self.content_max_tokens = content_max_tokens
        self.json_max_tokens = json_max_tokens
        self.narrative_validation_retries = max(0, narrative_validation_retries)
        self._narrative_engine_hints, self._engine_code_prompts = _load_engine_specs()

    async def _complete(self, business: str, **kwargs) -> str:
        with ai_business(business):
            return await self.client.create_chat_completion(**kwargs)

    async def _stream(
        self, business: str, messages: list[dict]
    ) -> AsyncIterator[str]:
        stream = self.client.stream_chat_completion(messages).__aiter__()
        try:
            while True:
                with ai_business(business):
                    try:
                        chunk = await anext(stream)
                    except StopAsyncIteration:
                        break
                yield chunk
        finally:
            await stream.aclose()

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
        aspect_ratio: str = "landscape",
    ) -> str:
        defaults = self._DEFAULT_STYLE_COMPONENTS
        narrative_style = style_components.get("narrative_style") or defaults["narrative_style"]
        color_scheme = style_components.get("color_scheme") or defaults["color_scheme"]
        exemplar = style_components.get("exemplar") or defaults["exemplar"]
        animation_style = style_components.get("animation_style") or defaults["animation_style"]
        engine_hint = self._narrative_engine_hints.get(render_engine, self._NARRATIVE_ENGINE_HINT_FALLBACK)

        parts = [
            "你是知识视频叙事脚本生成器。请严格输出 JSON object，不要输出 Markdown。",
            "",
            "【输出格式与风格范例】",
            "以下范例既定义输出的 JSON 结构，也示范本风格的旁白语感与信息密度。"
            "输出结构必须与范例完全一致；旁白的语感、句式与每镜信息密度请贴近范例，"
            "但内容必须来自当前选题，禁止照搬范例文字。"
            "范例可能只节选一部完整成片中的少数镜头（scene_index 不连续即为节选）；"
            "实际输出必须完整覆盖叙事蓝图要求的全部镜头，且 scene_index 从 0 连续递增：",
            exemplar,
            "",
        ]
        if narrative_style:
            parts.append(narrative_style)
        if color_scheme:
            parts.append(color_scheme)
            parts.append("颜色名与 Hex 对照（description 中用颜色名即可，代码生成阶段再转 Hex）")
        if animation_style:
            parts.append(
                "【视觉/动画风格约束（转化为画面语言，不得照抄其中的引擎术语）】\n"
                "以下是本项目的视觉精致度与动画风格要求，请将其中的布局骨架、留白密度、"
                "图标克制、转场语义等设计意图体现在 description 与 visual_action 的画面描述中；"
                "禁止在 description/visual_action 中出现其中提到的具体类名或方法名"
                "（如 VGroup、arrange、Transform、FadeOut 等）——这些留给代码生成阶段处理。"
            )
            parts.append(animation_style)
        parts += [
            "",
            "【语义节拍契约】",
            "- 每个 scene 除 narration、description 外必须输出非空 beats 数组",
            "- beats 数量遵循叙事蓝图组件的节拍规则；组件未规定时，普通镜头输出 2-4 个，纯标题或结尾镜头 1-2 个",
            "- cue_text 必须逐字取自 narration，并按顺序完整覆盖 narration；不得概括、改写或遗漏",
            "- 长句在逗号处继续拆分为多个 beat；一个 beat 覆盖的旁白朗读时长明显超过其动画动作所需时间时，必须增加 beat 而不是留白",
            "- visual_action 只描述这一句旁白发生时画面产生的知识性变化",
            "- visual_action 优先描述有时间过程的动画（逐个出现、描边生长、数值增长、移动变形、连线延伸），旁白进行中每 2-3 秒画面应有可感知的新变化，禁止一次性淡入后长时间静置",
            "- 每个 beat 必须推进信息、关系或状态，禁止用“保持画面”凑数量",
            "- beat_index 在每个 scene 内必须从 0 连续递增",
            "- transition 只能是 continue、transform、reveal、replace、exit 之一",
            "- 不输出绝对时间；时间由 TTS 完成后计算",
            "- visual_action 不得出现渲染引擎 API、类名、组件名或代码语法",
        ]
        parts.append(engine_hint)
        parts += [
            "",
            self._build_aspect_ratio_prompt(aspect_ratio, render_engine),
        ]
        parts += [
            "",
            "要求：",
            "- 第一个镜头需要按照视觉系统组件要求设置背景颜色",
            "- scenes 是镜头数组，scene_index 从 0 连续递增",
            "- 每个镜头包含 narration、description、beats、estimated_duration_seconds",
            "- narration旁白中的公式使用自然语言表述，因为TTS读公式可能读不对",
            "- 不再使用的镜头元素需要及时退场或消失，避免画面残留，这个很容易被忽略",
            "- fact_checks 覆盖脚本中的关键事实论断和可能争议点",
            "- 镜头数量、每镜旁白字数和视频总时长必须满足叙事蓝图组件的要求，不可偷懒；仅当组件完全未规定时，才默认至少 16 个镜头、时长 2-3 分钟",
            self._JSON_ESCAPE_RULE,
            "- 只能输出合法 JSON object",
        ]
        return "\n".join(parts)

    def _build_code_system_prompt(
        self,
        render_engine: str,
        style_components: dict[str, str],
        aspect_ratio: str = "landscape",
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
            "【硬性约束：镜头数量】",
            "- codes 数组长度必须与输入 scenes 数组长度完全一致（一一对应，按 scene_index 顺序排列），这是本任务最高优先级的强制要求，违反即视为失败输出。",
            "- 禁止合并、跳过、省略任何镜头；即使某些镜头内容相似或简单，也必须逐一单独生成对应的 code 片段。",
            "- 禁止因为担心输出过长而只生成部分镜头；如果内容较多，请压缩每个镜头 code 的写法（减少注释、复用变量），但绝不能减少 codes 数组的元素个数。",
            "- 生成完成后请在内部自查：codes.length 是否等于 scenes.length；如不相等，必须补全后再输出。",
            "",
            f"渲染引擎：{render_engine}",
        ]
        if color_scheme:
            parts.append("【视觉系统】")
            parts.append(color_scheme)
        if animation_style:
            parts.append("【动画系统】")
            parts.append(animation_style)
        parts += [
            "",
            "【语义节拍时间执行契约】",
            "- scene 中 beats 已按顺序给出真实 speech 时间和建议 animation 时间",
            "- 每个 beat 的 visual_action 必须在自己的 animation 时间窗口内发生",
            "- 每个 beat 的动画活动必须覆盖其时间窗口的 70% 以上；禁止用一个短动作加长时间静止完成 beat，时间富余时拉长过程性动画（错落入场、数值增长、逐段绘制）消化，而不是等待",
            "- 关键词对应的主要视觉结果最迟应在 speech_end_seconds 前清晰可见",
            "- 不得在第一个 beat 中一次性完成整个镜头的全部动画",
            "- 相邻 beat 优先通过已有元素的移动、变形、分裂、聚合或强调连续推进",
            "- 最后一个 beat 结束后可保持最终画面，但不得用无意义循环填满时间",
            "- alignment_status 为 interpolated 时仍使用给出的时间",
        ]
        parts.append(engine_hint)
        parts += [
            "",
            self._build_aspect_ratio_prompt(aspect_ratio, render_engine),
        ]
        parts += [
            "",
            "【代码拼合规则】",
            "所有镜头的 code 片段将被渲染引擎按顺序拼合为单个执行单元，每段之间插入注释分隔符。",
            "音频由渲染引擎在每个镜头开始时自动注入，code 里不处理音频。",
            "",
            "【音画同步规则】",
            "每个镜头 JSON 包含 duration_seconds 字段，代表该镜头旁白音频的时长（秒）。",
            "动画总时长（所有 run_time 与 self.wait 之和）必须 ≤ duration_seconds，且不得低于 duration_seconds 的 85%，目标 90-100%。",
            "不足 85% 时回去拉长过程动画（计数增长、逐段绘制、错落入场、状态扫过），禁止靠镜头末尾静置补齐；渲染引擎只负责补齐最后不足 1 秒的零头，禁止在镜头末尾添加用于补齐音频时长的 self.wait()。",
            "",
            "【遗留元素处理（每个镜头开场第一件事）】",
            "先处理上一镜头遗留元素的退场或让位（FadeOut / 移位 / Transform 复用），再入场本镜头新主体。",
            "降低透明度不是退场：除非该对象在语义上'仍在场但被忽略/被否决'（此时降透明是状态表达），否则一律 FadeOut；同屏处于低透明状态的对象组不得超过 1 组。",
            "",
            "要求：",
            "- 严格按照每个镜头的 description 实现动画逻辑",
            "- 充分利用跨镜头变量复用",
            "- 每个 code 片段不写外层结构（详见各引擎规范）",
            self._JSON_ESCAPE_RULE,
            "- 只能输出合法 JSON object",
        ]
        return "\n".join(parts)

    async def generate_narrative(
        self,
        topic_title: str,
        topic_description: str,
        render_engine: str,
        rejection_context: dict | None = None,
        previous_scenes: list[dict] | None = None,
        narrative_context: list[dict] | None = None,
        style_components: dict[str, str] | None = None,
        aspect_ratio: str = "landscape",
    ) -> NarrativeResult:
        system_prompt = self._build_narrative_system_prompt(
            render_engine=render_engine,
            style_components=style_components or {},
            aspect_ratio=aspect_ratio,
        )

        user_payload: dict = {
            "topic_title": topic_title,
            "topic_description": topic_description,
            "render_engine": render_engine,
            "aspect_ratio": normalize_aspect_ratio(aspect_ratio),
        }
        if rejection_context and previous_scenes:
            user_payload["rejection_context"] = rejection_context
            user_payload["previous_scenes"] = previous_scenes
            user_note = (
                "（注意：这是一次重新生成，previous_scenes 是上一版被驳回的完整叙事脚本，"
                "请在其基础上根据 rejection_context 中的驳回原因做针对性修改，"
                "不要抛弃未被指出问题的部分，仅重写需要修正之处）"
            )
        else:
            user_note = ""

        context_note = ""
        if narrative_context:
            snippets_text = "\n---\n".join(
                item["text"] for item in narrative_context if item.get("text")
            )
            if snippets_text:
                context_note = (
                    "\n\n以下是创作者标注的参考内容，请在叙事中参考这些观点或表述方式（不是全盘接收）：\n\n"
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
            content = await self._complete(
                "narrative_generation",
                messages=messages,
                response_format=response_format_for(
                    self.client,
                    name="narrative",
                    schema=NARRATIVE_SCHEMA,
                ),
                max_tokens=self.content_max_tokens,
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
        aspect_ratio: str = "landscape",
        rejection_context: dict | None = None,
        previous_code_scenes: list[dict] | None = None,
    ) -> CodeGenerationResult:
        system_prompt = self._build_code_system_prompt(
            render_engine=render_engine,
            style_components=style_components or {},
            aspect_ratio=aspect_ratio,
        )
        user_payload: dict = {
            "aspect_ratio": normalize_aspect_ratio(aspect_ratio),
            "scenes": scenes,
        }
        if rejection_context:
            user_payload["rejection_context"] = rejection_context
            if previous_code_scenes:
                user_payload["previous_code_scenes"] = _strip_codegen_fields(previous_code_scenes)
                del user_payload["scenes"]
                user_note = (
                    "（注意：这是一次重新生成，previous_code_scenes 是上一版被驳回的完整渲染代码（含每个镜头的 code），"
                    "请在其基础上根据 rejection_context 中标注的问题做针对性修改，"
                    "未被指出问题的镜头代码应尽量保留，仅重写需要修正之处）"
                )
            else:
                user_note = "（注意：这是一次重新生成，请优先修正 rejection_context 中标注的代码问题，并参考相关叙事问题）"
        else:
            user_note = ""
        content = await self._complete(
            "code_generation",
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"请为以下镜头叙事生成渲染代码 JSON{user_note}：\n"
                    + json.dumps(user_payload, ensure_ascii=False)
                    + f"\n\n（再次强调：输入共 {len(scenes)} 个镜头，"
                    f"codes 数组必须恰好包含 {len(scenes)} 个元素，逐一对应，不得合并或省略任何镜头）",
                },
            ],
            response_format=response_format_for(
                self.client,
                name="code_generation",
                schema=CODE_GENERATION_SCHEMA,
            ),
            max_tokens=self.content_max_tokens,
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
        aspect_ratio: str = "landscape",
    ) -> CodeRepairResult:
        engine_hint = self._engine_code_prompts.get(render_engine, self._ENGINE_CODE_PROMPT_FALLBACK)
        defaults = self._DEFAULT_STYLE_COMPONENTS
        color_scheme = (style_components or {}).get("color_scheme", defaults.get("color_scheme", ""))
        animation_style = (style_components or {}).get("animation_style", defaults.get("animation_style", ""))
        aspect_prompt = self._build_aspect_ratio_prompt(aspect_ratio, render_engine)
        system_prompt = f"""\
你是知识视频渲染代码修复专家。请严格输出 JSON object，不要输出 Markdown。

你会收到一次整体渲染失败的完整错误信息，以及按执行顺序排列的全部镜头。

你的任务：
1. 结合错误信息审查收到的镜头，定位直接错误、上游根因和可能由同类写法引发后续失败的镜头。
2. 尽可能在这一次响应中修复全部可能有错误的镜头。
3. 保持旁白、画面意图、镜头顺序和跨镜头变量关系；只修改需要修复的代码。
4. repairs 仅列出需要修改的镜头；每个 scene_index 必须来自输入且不得重复。
5. code 必须是可直接替换原镜头 code 的完整代码片段。
6. explanation 用简短中文说明该镜头的问题和修复方式。

注意项：
1. 修复代码时尤其注意变量作用域，保证变量先声明再使用，避免跨镜头变量冲突。
2. {self._JSON_ESCAPE_RULE.lstrip("- ")}

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
{engine_hint}

只能输出合法 JSON object。"""
        content = await self._complete(
            "code_repair",
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": "请一次性检查并修复所有可能出错的镜头：\n"
                    + json.dumps(
                        {
                            "render_engine": render_engine,
                            "aspect_ratio": normalize_aspect_ratio(aspect_ratio),
                            "error_message": error_message,
                            "scenes": _strip_codegen_fields(scenes),
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            response_format=response_format_for(
                self.client,
                name="code_repair",
                schema=CODE_REPAIR_SCHEMA,
            ),
            max_tokens=self.content_max_tokens,
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
        system_prompt = f"""\
你是知识视频选题策划助手。请严格输出 JSON object，不要输出 Markdown。

JSON 格式示例：
{{
  "candidates": [
    {{
      "title": "一个有吸引力、可论证、适合动画化的选题标题",
      "description": "一句话说明选题切入角度和知识价值",
      "tags": ["物理", "认知"]
    }}
  ]
}}

要求：
- candidates 数量必须匹配用户要求。
- title 适合自媒体知识视频标题，避免空泛。
- description 说明吸引力（重要）、可论证点或可视化潜力。
- tags 使用 2 到 5 个中文短标签。
{self._JSON_ESCAPE_RULE}
- 只能输出合法 JSON object。"""
        user_prompt = f"请围绕「{topic_direction}」生成 {count} 个候选选题 JSON。"
        content = await self._complete(
            "topic_brainstorm",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format=response_format_for(
                self.client,
                name="brainstorm",
                schema=BRAINSTORM_SCHEMA,
            ),
            max_tokens=self.json_max_tokens,
        )
        payload = parse_json_object(content)
        candidates = payload.get("candidates")
        if not isinstance(candidates, list):
            raise ValueError("Brainstorm response must contain candidates array")
        for candidate in candidates:
            if (
                not isinstance(candidate, dict)
                or not isinstance(candidate.get("title"), str)
                or not candidate["title"].strip()
                or not isinstance(candidate.get("description"), str)
                or not isinstance(candidate.get("tags"), list)
                or any(not isinstance(tag, str) for tag in candidate["tags"])
            ):
                raise ValueError("Invalid brainstorm candidate")
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

        async for chunk in self._stream("topic_research", messages):
            yield chunk

    async def assist_style_prompt(
        self,
        category: str,
        name: str,
        description: str,
        prompt_text: str,
        conversation_history: list[dict],
        new_message: str,
    ) -> StyleAssistantResult:
        system_prompt = f"""\
你是一位知识视频生产系统的风格提示词设计助手。你的任务是通过对话，把用户的想法整理成清晰、可执行、可复用的风格组件提示词。

规则：
- 只修改当前组件类型范围内的规则，不混入其他组件的职责。
- 提示词写给后续的叙事或视频生成模型，应使用明确的约束、层级和可检查的表达，避免空泛形容词。
- 保留用户已有提示词中未要求删除的有效约束；若要求有冲突，在 reply 中简短指出你的取舍。
- prompt_text 必须是可直接投入生成工作流的完整文本，不要使用 Markdown 代码围栏。
- name 简洁易辨识；description 用一句话说明适用场景。
- reply 用 1-3 句中文说明本轮做了什么，并可提出一个有价值的后续问题。
- 即使用户只是在询问，也要返回当前版本的完整 name、description、 prompt_text和replay。
{self._JSON_ESCAPE_RULE}
- 只能输出合法 JSON object。"""
        category_labels = {
            "narrative_style": "叙事蓝图（叙事风格+节奏+镜头结构）",
            "color_scheme": "视觉系统",
            "animation_style": "动画系统",
            "exemplar": "金样本（输出 JSON 结构与旁白语感范例）",
        }
        messages = [{"role": "system", "content": system_prompt}]
        for item in conversation_history[-20:]:
            role = item.get("role")
            content = item.get("content")
            if role in {"user", "assistant"} and isinstance(content, str):
                messages.append({"role": role, "content": content})
        messages.append(
            {
                "role": "user",
                "content": (
                    f"组件类型：{category_labels.get(category, category)}\n"
                    f"当前名称：{name or '未填写'}\n"
                    f"当前说明：{description or '未填写'}\n"
                    f"当前提示词：\n{prompt_text or '（尚未创建）'}\n\n"
                    f"本轮要求：{new_message}"
                ),
            }
        )
        content = await self._complete(
            "style_assistant",
            messages=messages,
            response_format=response_format_for(
                self.client,
                name="style_assistant",
                schema=STYLE_ASSISTANT_SCHEMA,
            ),
            max_tokens=self.json_max_tokens,
        )
        print(f"Style assistant raw response: {content}")
        payload = parse_json_object(content)
        generated_prompt = payload.get("prompt_text", payload.get("promptText"))
        if not isinstance(generated_prompt, str) or not generated_prompt.strip():
            raise ValueError("Style assistant returned an empty prompt")

        generated_name = payload.get("name")
        if not isinstance(generated_name, str) or not generated_name.strip():
            generated_name = name

        generated_description = payload.get("description")
        if not isinstance(generated_description, str):
            generated_description = description

        reply = payload.get("reply")
        if not isinstance(reply, str) or not reply.strip():
            reply = "我已根据你的要求更新了左侧提示词。你可以继续告诉我需要强化或删减的部分。"

        return StyleAssistantResult(
            reply=reply.strip(),
            name=generated_name.strip(),
            description=generated_description.strip(),
            prompt_text=generated_prompt.strip(),
        )


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
