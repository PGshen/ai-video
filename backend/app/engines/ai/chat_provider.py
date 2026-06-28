import json
import re
from collections.abc import AsyncIterator

from app.engines.ai.base import (
    BrainstormResult, ChatClient, CodeGenerationResult, CodeRepairResult,
    NarrativeResult, ScriptGenerationResult,
)


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
- 元素默认可跨镜头保留；镜头边界不等于清场点，不要为了结束当前镜头而机械 FadeOut
- 仅当元素完成叙事作用、即将被新内容替代或会遮挡后续重点时，才在合适的转场时机用 FadeOut / ReplacementTransform 退场
- 若下一镜头复用某元素（变形/移动/替换），用 Transform / ReplacementTransform / .animate，不要重新声明同名变量
- 禁止在不同镜头中对同一逻辑元素重复声明同名变量

【动画时序规则】
- 用 self.wait(n) 控制停留时长，单位秒
- 每个镜头 code 的所有 self.play(run_time=...) 与 self.wait(...) 之和需与该镜头 estimated_duration_seconds 匹配（误差 ±1s 可接受）
- 镜头之间用 FadeOut/FadeIn 或 Transform 做过渡，避免画面突然硬切
- 关键图形和结论必须至少保留到对应旁白讲完；禁止旁白尚未结束就清空画面
- 渲染器会自动补齐镜头剩余时长。如果本镜头没有必要的退场或转场，代码末尾保持最终画面即可，不要添加 FadeOut 清场

【坐标系规则（重要）】
- Manim 内部所有点坐标均为三维 (x, y, z)，z 通常为 0
- 禁止使用 np.array([x, y]) 等二维坐标，必须写 np.array([x, y, 0])
- set_points_as_corners、set_anchors_and_handles 等方法参数必须是 shape (n, 3) 的数组
- 若用 numpy 构建路径点，形如 [[x1,y1,0], [x2,y2,0], ...]，不可省略 z 分量
- Axes 构造函数不支持 x_label / y_label 参数；先创建 axes，再用 axes.get_x_axis_label(Text("横轴")) 和 axes.get_y_axis_label(Text("纵轴")) 创建标签，并将标签与坐标轴一起播放和清场

【视觉优先】
- 除纯标题或总结镜头外，每个镜头至少设计一个承载知识含义的图形动画；多用 Circle、Square、Arrow、NumberLine、Axes、Graph、VGroup 等构建关系、过程、对比或变化
- 优先让已有图形移动、缩放、变形、连线、分裂或聚合来推进讲解，避免只摆放静态文字和装饰性图形
- 公式只展示理解结论不可缺少的关键公式，用 MathTex 配合图形直观解释；不要连续堆砌公式、推导步骤或符号墙
- 画面文字只保留关键词、数字、公式、简短标注，每帧不超过 15 个汉字
- 善用 Create、Write、GrowArrow、DrawBorderThenFill、Transform 等动效让图形活起来

【配色风格——偏深马卡龙】
- 米白背景上使用饱和度适中、明度略压低的马卡龙色，保证柔和但不发灰、不幼稚
- 主色推荐：雾霾蓝 #6688A6、鼠尾草绿 #6F9275、陶土粉 #C87878、蜜桃橙 #D49362、薰衣草紫 #8B7EAA、芥末黄 #C6A04A
- 正文与轮廓使用深灰 #30343B；同一画面控制在 1 个主色、1 个辅助色和 1 个强调色，避免彩虹式混用

【典型跨镜头示例】
# === 镜头 0（标题引入）===
title = Text("为什么天空是蓝色的？").scale(1.2)
self.play(Write(title), run_time=2)

# === 镜头 1（标题缩小，引入图示）===
self.play(title.animate.scale(0.5).to_edge(UP), run_time=1)
sun = Circle(radius=0.5, color=ManimColor("#D49362")).shift(LEFT * 4)
earth = Circle(radius=0.3, color=ManimColor("#6688A6")).shift(RIGHT * 3)
light_ray = Arrow(sun.get_right(), earth.get_left(), color=ManimColor("#30343B"))
self.play(Create(sun), Create(earth), GrowArrow(light_ray), run_time=2)
# 本镜头无需转场：保留图示，渲染器自动补齐旁白剩余时长
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
- 镜头边界不等于清场点；关键元素保持到对应旁白结束，仅在叙事转折、替换或遮挡新重点时淡出

【视觉优先】
- 除纯标题或总结镜头外，每个镜头至少设计一个承载知识含义的 SVG/CSS 图形动画，用路径、位置、大小、连接或形变讲清关系和过程
- 公式只展示理解核心结论不可缺少的关键公式，并与图形配合；避免连续推导和公式堆砌
- 文字只用于关键词、数字、公式标注，每帧不超过 15 个汉字
- 善用 spring() 做元素入场动效，interpolate 做连续属性变化（位置、缩放、透明度）
- 使用偏深马卡龙色：雾霾蓝 #6688A6、鼠尾草绿 #6F9275、陶土粉 #C87878、蜜桃橙 #D49362、薰衣草紫 #8B7EAA、芥末黄 #C6A04A；正文用 #30343B，背景用 #F5F0E8

【典型示例】
// 镜头 0：标题淡入
const frame = useCurrentFrame();
const { fps } = useVideoConfig();
const opacity = interpolate(frame, [0, 20], [0, 1], { extrapolateRight: "clamp" });
return (
  <AbsoluteFill style={{ background: "#F5F0E8", justifyContent: "center", alignItems: "center" }}>
    <div style={{ opacity, fontSize: 56, color: "#30343B", fontWeight: "bold" }}>
      为什么天空是蓝色的？
    </div>
  </AbsoluteFill>
);

// 镜头 1：散射图示动画
const { fps } = useVideoConfig();
const progress = spring({ frame, fps, config: { stiffness: 60, damping: 12 } });
const rayWidth = interpolate(progress, [0, 1], [0, 300]);
return (
  <AbsoluteFill style={{ background: "#F5F0E8" }}>
    <svg width="100%" height="100%" viewBox="0 0 1280 720">
      <circle cx={200} cy={360} r={60} fill="#D49362" />
      <line x1={260} y1={360} x2={260 + rayWidth} y2={360}
            stroke="#6688A6" strokeWidth={3} />
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

    _NARRATIVE_ENGINE_HINTS: dict[str, str] = {
        "manim": """\
【Manim 画面描述规范——弱技术层】
description 字段只写画面意图，由代码生成阶段翻译为 Manim 动画代码。禁止在 description 中出现 Manim 类名、变量名或代码语法。

【可用图形词汇】
几何图形：圆形、矩形、三角形、多边形、路径
连接关系：箭头、双向箭头、连线、虚线
数据图示：坐标轴、折线图、柱状图、散点、数轴、网格
文字内容：标题文字、说明标注、关键公式（用文字描述，如"E=mc² 公式"）

【配色参考】
颜色名与 Hex 对照（description 中用颜色名即可，代码生成阶段再转 Hex）：
- 草莓红 #E8524A、橘橙 #F07D3E、向日葵黄 #F5C518（暖色系）
- 天蓝 #4BA3C3、草绿 #5BAD6F、薰衣草紫 #9B7EC8（冷色辅助）
- 深炭灰 #2C2C2C（文字/轮廓）；背景：米白（渲染器已设置）

【跨镜头衔接描述方式】
- "承接上镜[元素描述]，[动作意图]" —— 元素延续
- "[元素]保留至旁白结束" —— 不退场
- "[元素]替换为[新元素]" —— 视觉替换
- "[元素]完成使命后退场" —— 叙事驱动退场

【退场时机原则】
- 仅当元素完成叙事使命、即将被新内容替代或会遮挡后续重点时才退场
- 只描述退场意图，不写退场代码
- 若无退场需要，写"图示保留至旁白结束"

【内容要求】
- 除纯标题或总结镜头外，每个镜头至少包含一个承载知识含义的图形动画
- 优先用位置、大小、连接、分裂、聚合或形变推进讲解，避免只摆放静态文字
- 先用直观图形讲清概念，只在支撑核心结论时引入关键公式，不堆砌推导
- 每帧文字不超过 15 个汉字

【示例】
镜头 0："米白背景。中央出现主标题文字，动态写入。保留至旁白结束，延续到下一镜头。"
镜头 1："承接上镜标题，缩小移至顶部保留。左侧出现橙色圆形代表太阳，草莓红箭头从太阳向右延伸，末端散射成多条分支，展示光的散射过程。图示保留至旁白结束。"
镜头 2："承接上镜图示。蓝色短波分支高亮放大，其余颜色分支淡化。右侧出现标注文字'蓝光波长最短'。标题和散射图示完成使命后退场，保留高亮蓝色分支作为下镜视觉锚点。"\
""",
        "remotion": """\
【Remotion 画面描述规范——弱技术层】
description 字段只写画面意图，由代码生成阶段翻译为 React/TSX 动画代码。禁止在 description 中出现组件名、hook 名或代码语法。

【可用图形词汇】
SVG 图形：圆形、矩形、路径、线条、多边形
连接关系：箭头、连线
文字层：标题、说明文字、数字标注、关键公式（文字描述）

【配色参考】
颜色名与 Hex 对照（description 中用颜色名即可）：
草莓红 #E8524A、橘橙 #F07D3E、向日葵黄 #F5C518；天蓝 #4BA3C3、草绿 #5BAD6F；深炭灰 #2C2C2C；背景：米白

【跨镜头衔接说明】
Remotion 每个 Sequence 是独立作用域。跨镜头持续存在的元素（背景、顶部标题栏）在 description 中注明"作为共享层延续"。

【内容要求】
- 除纯标题或总结镜头外，每个镜头至少包含一个承载知识含义的 SVG/CSS 图形动画
- 先图形讲解，关键公式只在支撑核心结论时出现，不堆砌推导
- 每帧文字不超过 15 个汉字

【示例】
镜头 0："米白背景。中央主标题文字弹性入场，保留至旁白结束。"
镜头 1："背景和缩小后的标题作为共享层延续。中央 SVG：左侧橘橙圆形代表太阳，天蓝线条向右延伸后分裂成多条散射路径，图示保留至旁白结束。"\
""",
    }
    _NARRATIVE_ENGINE_HINT_FALLBACK = (
        "description 字段将用于后续渲染代码生成，必须精确描述每个元素的进场、变形、退场及跨镜头衔接关系。"
    )

    _NARRATIVE_SYSTEM_PROMPT_TEMPLATE = """\
你是知识视频叙事脚本生成器。请严格输出 JSON object，不要输出 Markdown。

JSON 格式示例：
{{
  "scenes": [
    {{
      "scene_index": 0,
      "narration": "旁白文稿——控制节奏、娓娓道来",
      "description": "画面描述（明确标注进场/变形/退场/跨镜头衔接）",
      "estimated_duration_seconds": 8.0
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

【叙事要求】
- 整体娓娓道来，从一个反直觉的问题或现象切入，逐步建立知识体系，结尾给出有价值的启示
- 旁白（narration）负责讲解，每句话清晰有力，不空洞，不重复画面文字
- 目标视频时长 2-3 分钟，需要 15-20 个镜头，每个镜头旁白约 30-50 字、时长 7-10 秒
- estimated_duration_seconds 根据旁白字数和画面复杂度估算，不得少于 5 秒
- 先用直观图形和动态关系解释概念，再在确有必要时引入关键公式；公式服务于理解，不追求数量和完整推导

【内容节奏】
- 镜头 0-1：抛出问题/反直觉现象，吸引注意
- 镜头 2-5：建立基础知识框架，引入关键概念
- 镜头 6-14：逐步深入，以动态图示和实例展开论证，只在关键节点使用必要公式
- 镜头 15+：总结升华，给出启示或应用价值

{engine_hint}

要求：
- scenes 是镜头数组，scene_index 从 0 连续递增，数量在 15-20 个
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
        engine_hint = self._NARRATIVE_ENGINE_HINTS.get(
            render_engine, self._NARRATIVE_ENGINE_HINT_FALLBACK
        )
        system_prompt = self._NARRATIVE_SYSTEM_PROMPT_TEMPLATE.format(
            engine_hint=engine_hint
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

        content = await self.client.create_chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
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

【音画同步规则】
每个镜头 JSON 包含 duration_seconds 字段，代表该镜头旁白音频的时长（秒）。
动画总时长（所有 run_time 与 self.wait 之和）必须 ≤ duration_seconds。
渲染引擎会在每个镜头末尾自动补齐剩余时间，因此禁止在镜头末尾添加用于补齐音频时长的 self.wait()。
动画节奏需要的 self.wait()（如两个动画之间的停顿）照常使用。
若某镜头 duration_seconds 为 null，则不作时长约束，由你自行估算合适时长。

【文字渲染规则（重要）】
- 所有中文、日文等非 ASCII 文字必须使用 Text()，禁止使用 MathTex() 或 Tex()
- MathTex() / Tex() 仅用于纯英文/ASCII 数学公式（如 r"E=mc^2"、r"\frac{{1}}{{2}}"）
- 中英文混排时，中文用 Text()，公式用 MathTex()，再用 VGroup 组合
- 违反此规则会导致 LaTeX 编译报错使视频生成失败

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

    async def repair_code(
        self,
        scenes: list[dict],
        render_engine: str,
        error_message: str,
    ) -> CodeRepairResult:
        engine_hint = self._ENGINE_CODE_PROMPTS.get(
            render_engine, self._ENGINE_CODE_PROMPT_FALLBACK
        )
        system_prompt = f"""\
你是知识视频渲染代码修复专家。请严格输出 JSON object，不要输出 Markdown。

你会收到一次整体渲染失败的完整错误信息，以及按执行顺序排列的全部镜头。所有镜头代码会被拼合后一次性执行，因此报错位置可能只是症状，真正原因可能在更早的镜头。

你的任务：
1. 结合错误信息审查全部镜头，定位直接错误、上游根因和可能由同类写法引发后续失败的镜头。
2. 尽可能在这一次响应中修复全部可能有错误的镜头，不要只修错误栈直接指向的第一个镜头。
3. 保持旁白、画面意图、镜头顺序和跨镜头变量关系；只修改需要修复的代码。
4. repairs 仅列出需要修改的镜头；每个 scene_index 必须来自输入且不得重复。
5. code 必须是可直接替换原镜头 code 的完整代码片段，不能是 diff、伪代码或省略内容。
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
{engine_hint}

只能输出合法 JSON object。\
"""
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
            normalized.append(
                {
                    "scene_index": scene_index,
                    "code": code,
                    "explanation": explanation,
                }
            )
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
