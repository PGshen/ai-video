import json
import re
from collections.abc import AsyncIterator

from app.engines.ai.base import BrainstormResult, ChatClient, CodeGenerationResult, NarrativeResult, ScriptGenerationResult


class ChatAIProvider:
    _ENGINE_CODE_PROMPTS: dict[str, str] = {
        "manim": """\
【Manim 代码规范】

渲染引擎已生成外层结构（from manim import *、Scene 类定义、construct() 等），code 字段只写 construct() 方法体内的代码片段：

      # === 镜头 0 ===
      <scene 0 的 code>
      # === 镜头 1 ===
      <scene 1 的 code>
      ...

禁止在 code 里写 import 语句、def construct、或结构定义。

【变量生命周期规则】
- scene 0 声明的变量（如 title = Text("...")）在 scene 1、2... 中仍在作用域内，可直接引用
- 若下一镜头不再需要某元素，必须在本镜头末尾显式移除：self.play(FadeOut(obj))
- 若下一镜头复用某元素（变形/移动/替换），用 Transform / ReplacementTransform / .animate，不要重新声明同名变量
- 禁止在不同镜头中对同一逻辑元素重复声明同名变量

【动画时序规则】
- 用 self.wait(n) 控制停留时长，单位秒
- 每个镜头 code 的所有 self.play(run_time=...) 与 self.wait(...) 之和需与该镜头 estimated_duration_seconds 匹配（误差 ±1s 可接受）
- 镜头之间用 FadeOut/FadeIn 或 Transform 做过渡，避免画面突然硬切

【视觉优先】
- 多用 Circle、Square、Arrow、NumberLine、Axes、Graph、VGroup 等几何图形构建图示
- 公式用 MathTex，避免用 Text 堆砌大段说明文字
- 画面文字只保留关键词、数字、公式、简短标注，每帧不超过 15 个汉字
- 善用 Create、Write、GrowArrow、DrawBorderThenFill、Transform 等动效让图形活起来

【典型跨镜头示例】
# === 镜头 0（标题引入）===
title = Text("为什么天空是蓝色的？").scale(1.2)
self.play(Write(title), run_time=2)
self.wait(1)

# === 镜头 1（标题缩小，引入图示）===
self.play(title.animate.scale(0.5).to_edge(UP), run_time=1)
sun = Circle(radius=0.5, color=YELLOW).shift(LEFT * 4)
earth = Circle(radius=0.3, color=BLUE).shift(RIGHT * 3)
light_ray = Arrow(sun.get_right(), earth.get_left(), color=WHITE)
self.play(Create(sun), Create(earth), GrowArrow(light_ray), run_time=2)
self.wait(2)
self.play(FadeOut(light_ray), FadeOut(earth))
""",
        "remotion": """\
【Remotion 代码规范】

渲染引擎已生成外层结构，code 字段只写放入 <Sequence> 内部的 JSX 片段：

  export const VideoScene: React.FC = () => {
    const { fps } = useVideoConfig();
    return (
      <>
        {/* === 镜头 0 === */}
        <Sequence from={0} durationInFrames={scene0Frames}>
          <scene 0 的 code>
        </Sequence>
        {/* === 镜头 1 === */}
        <Sequence from={scene1StartFrame} durationInFrames={scene1Frames}>
          <scene 1 的 code>
        </Sequence>
      </>
    );
  };

禁止在 code 里写 export const VideoScene 外层定义。

【帧与时序规则】
- 在 code 片段内用 useCurrentFrame() 获取当前 <Sequence> 内的相对帧（从 0 开始）
- 动画用 interpolate(frame, [inputRange], [outputRange]) 或 spring({ frame, fps }) 驱动
- estimated_duration_seconds × fps（默认 30）= 该镜头 durationInFrames，渲染引擎自动计算，code 里不要硬编码绝对帧数
- 镜头间过渡用 interpolate + opacity 实现淡入淡出，或用 spring() 做弹性动效

【跨镜头共享元素】
- 跨多个镜头持续存在的元素（如背景、顶部标题栏）用 <Sequence from={0} durationInFrames={totalFrames}> 包裹，放在最外层
- 每个镜头的 code 只负责该镜头独有的内容

【视觉优先】
- 用 SVG 路径、几何图形、CSS animation/transform 构建图示，避免大段文字
- 文字只用于关键词、数字、公式标注，每帧不超过 15 个汉字
- 善用 spring() 做元素入场动效，interpolate 做连续属性变化（位置、缩放、透明度）

【典型示例】
// 镜头 0：标题淡入
const frame = useCurrentFrame();
const { fps } = useVideoConfig();
const opacity = interpolate(frame, [0, 20], [0, 1], { extrapolateRight: "clamp" });
return (
  <AbsoluteFill style={{ background: "#0a0a0a", justifyContent: "center", alignItems: "center" }}>
    <div style={{ opacity, fontSize: 56, color: "white", fontWeight: "bold" }}>
      为什么天空是蓝色的？
    </div>
  </AbsoluteFill>
);

// 镜头 1：散射图示动画
const { fps } = useVideoConfig();
const progress = spring({ frame, fps, config: { stiffness: 60, damping: 12 } });
const rayWidth = interpolate(progress, [0, 1], [0, 300]);
return (
  <AbsoluteFill style={{ background: "#0a0a0a" }}>
    <svg width="100%" height="100%" viewBox="0 0 1280 720">
      <circle cx={200} cy={360} r={60} fill="#FFD700" />
      <line x1={260} y1={360} x2={260 + rayWidth} y2={360}
            stroke="white" strokeWidth={3} />
    </svg>
  </AbsoluteFill>
);
""",
    }
    _ENGINE_CODE_PROMPT_FALLBACK = (
        "- code 字段填写适合所选渲染引擎的代码片段（非完整文件），"
        "所有镜头的 code 将被顺序拼合为单个执行单元。"
        "不处理音频，渲染引擎自动注入。"
    )

    def __init__(
        self,
        client: ChatClient,
        script_max_tokens: int = 8192,
        json_max_tokens: int = 4096,
    ):
        self.client = client
        self.script_max_tokens = script_max_tokens
        self.json_max_tokens = json_max_tokens

    @property
    def engine_name(self) -> str:
        return self.client.engine_name

    @property
    def model_name(self) -> str:
        return self.client.model_name

    async def generate_script(
        self,
        topic_title: str,
        topic_description: str,
        render_engine: str,
        rejection_context: dict | None = None,
    ) -> ScriptGenerationResult:
        engine_hint = self._ENGINE_CODE_PROMPTS.get(
            render_engine, self._ENGINE_CODE_PROMPT_FALLBACK
        )
        system_prompt = f"""\
你是知识视频脚本生成器。请严格输出 JSON object，不要输出 Markdown。

JSON 格式示例：
{{
  "scenes": [
    {{
      "scene_index": 0,
      "narration": "旁白文稿",
      "description": "画面描述",
      "code": "渲染代码片段",
      "estimated_duration_seconds": 12.5
    }}
  ],
  "fact_checks": [
    {{
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
    }}
  ]
}}

渲染引擎：{render_engine}
{engine_hint}

【代码拼合规则】
所有镜头的 code 字段将被渲染引擎按 scene_index 顺序拼合为单个执行单元，每段之间插入注释分隔符。
code 字段只写代码片段，不写外层结构（详见各引擎规范）。
音频由渲染引擎在每个镜头开始时自动注入，code 里不处理音频。

要求：
- scenes 是镜头数组，scene_index 从 0 连续递增。
- 每个镜头包含 narration、description、code、estimated_duration_seconds。
- fact_checks 覆盖脚本中的关键事实论断和可能争议点。
- 只能输出合法 JSON object。"""

        user_payload: dict = {
            "topic_title": topic_title,
            "topic_description": topic_description,
            "render_engine": render_engine,
        }
        if rejection_context:
            user_payload["rejection_context"] = rejection_context
            user_note = "（注意：这是一次重新生成，请参考 rejection_context 中的驳回原因修正问题）"
        else:
            user_note = ""

        content = await self.client.create_chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"请为以下选题生成知识视频脚本 JSON{user_note}：\n"
                    + json.dumps(user_payload, ensure_ascii=False),
                },
            ],
            response_format={"type": "json_object"},
            max_tokens=self.script_max_tokens,
        )
        payload = parse_json_object(content)
        scenes = payload.get("scenes")
        fact_checks = payload.get("fact_checks")
        if not isinstance(scenes, list) or not isinstance(fact_checks, list):
            raise ValueError("Script response must contain scenes and fact_checks arrays")
        return ScriptGenerationResult(scenes=scenes, fact_checks=fact_checks)

    _NARRATIVE_SYSTEM_PROMPT = """\
你是知识视频叙事脚本生成器。请严格输出 JSON object，不要输出 Markdown。

JSON 格式示例：
{
  "scenes": [
    {
      "scene_index": 0,
      "narration": "旁白文稿——控制节奏、娓娓道来",
      "description": "画面描述（明确标注进场/变形/退场/跨镜头衔接）",
      "estimated_duration_seconds": 8.0
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
}

【叙事要求】
- 整体娓娓道来，从一个反直觉的问题或现象切入，逐步建立知识体系
- 旁白（narration）负责讲解，每句话清晰有力，不空洞
- 镜头数量根据内容自然分配，通常 8-20 个镜头
- estimated_duration_seconds 根据旁白长度和画面复杂度估算（通常 5-12 秒/镜头）

【画面描述规范】
description 字段将直接用于后续渲染代码生成（由 code_generating 阶段处理），必须足够精确：
- 优先使用图形、公式、数轴、几何图示表达概念，而非纯文字说明
- 明确标注每个元素的进场方式（如：用 Create 绘制/用 Write 书写/用 FadeIn 淡入/用 GrowArrow 生长）
- 明确标注跨镜头复用：哪些元素保留给下一镜头、如何变形（Transform/ReplacementTransform/.animate）
- 明确标注退场：哪些元素在本镜头末尾 FadeOut/移出画面（不再使用的元素必须清场）
- 每帧实际显示的文字不超过 15 个汉字（关键词、数字、公式、简短标注）
- 可参考的 Manim 元素类型：Circle/Arrow/NumberLine/Axes/Graph/VGroup/MathTex/Text

【跨镜头衔接示例（description 写法）】
场景：标题在镜头 0 引入，镜头 1 缩小到顶部
- 镜头 0 description："黑色背景。用 Write 写出标题'...'. 结尾保留 title 对象供下一镜头使用。"
- 镜头 1 description："承接 title 对象，用 title.animate.scale(0.5).to_edge(UP) 移动到顶部。下方用 Create 绘制..."

要求：
- scenes 是镜头数组，scene_index 从 0 连续递增
- 每个镜头包含 narration、description、estimated_duration_seconds
- fact_checks 覆盖脚本中的关键事实论断和可能争议点
- 只能输出合法 JSON object\
"""

    async def generate_narrative(
        self,
        topic_title: str,
        topic_description: str,
        render_engine: str,
        rejection_context: dict | None = None,
    ) -> NarrativeResult:
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

        content = await self.client.create_chat_completion(
            messages=[
                {"role": "system", "content": self._NARRATIVE_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"请为以下选题生成知识视频叙事脚本 JSON{user_note}：\n"
                    + json.dumps(user_payload, ensure_ascii=False),
                },
            ],
            response_format={"type": "json_object"},
            max_tokens=self.script_max_tokens,
        )
        payload = parse_json_object(content)
        scenes = payload.get("scenes")
        fact_checks = payload.get("fact_checks")
        if not isinstance(scenes, list) or not isinstance(fact_checks, list):
            raise ValueError("Narrative response must contain scenes and fact_checks arrays")
        return NarrativeResult(scenes=scenes, fact_checks=fact_checks)

    async def generate_code(
        self,
        scenes: list[dict],
        render_engine: str,
    ) -> CodeGenerationResult:
        engine_hint = self._ENGINE_CODE_PROMPTS.get(
            render_engine, self._ENGINE_CODE_PROMPT_FALLBACK
        )
        system_prompt = f"""\
你是知识视频代码生成器。请严格输出 JSON object，不要输出 Markdown。

你将收到一个知识视频的所有镜头叙事脚本，需要为每个镜头生成渲染代码片段。

JSON 格式：
{{
  "codes": [
    "镜头 0 的代码片段",
    "镜头 1 的代码片段"
  ]
}}

codes 数组长度必须与输入 scenes 数组长度完全一致，按 scene_index 顺序对应。

渲染引擎：{render_engine}
{engine_hint}

【代码拼合规则】
所有镜头的 code 片段将被渲染引擎按顺序拼合为单个执行单元，每段之间插入注释分隔符。
音频由渲染引擎在每个镜头开始时自动注入，code 里不处理音频。

要求：
- 严格按照每个镜头的 description 实现动画逻辑
- 充分利用跨镜头变量复用（前面镜头声明的变量在后续镜头中可直接使用）
- 每个 code 片段不写外层结构（详见各引擎规范）
- 只能输出合法 JSON object\
"""
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
        return CodeGenerationResult(codes=codes)

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
- 只能输出合法 JSON object。\
"""
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
