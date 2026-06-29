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
- scene 0 声明的变量在 scene 1、2... 中仍在作用域内，可直接引用
- 元素默认可跨镜头保留；镜头边界不等于清场点，不要为了结束当前镜头而机械 FadeOut
- 仅当元素完成叙事作用、即将被新内容替代或会遮挡后续重点时，才在合适的转场时机用 FadeOut 退场
- 若下一镜头复用某元素（变形/移动/替换），用 Transform / ReplacementTransform / .animate，不要重新声明同名变量
- 禁止在不同镜头中对同一逻辑元素重复声明同名变量

【画布安全区（重要）】
- Manim 默认画布：14.2 × 8 单位（宽×高），坐标原点在中心
- 安全区：x ∈ [-6.0, 6.0]，y ∈ [-3.5, 3.5]，距边缘至少 0.3 单位缓冲
- 所有元素创建后必须确认坐标在安全区内，禁止超出此范围
- 多元素布局用 VGroup(...).arrange() 或明确 .shift() 定位，不依赖默认位置叠加
- 大型 VGroup 用 .scale_to_fit_width(11) 限制最大宽度

【坐标轴（Axes）专项安全规则——高频溢出场景】
Axes 是最容易导致内容溢出的对象，必须遵守以下规则：

1. 必须显式设置 x_length 和 y_length，禁止使用默认尺寸：
   axes = Axes(x_range=[0,10,1], y_range=[0,1,0.2], x_length=9, y_length=5)

2. 创建后必须立即用 .move_to(ORIGIN) 或 .shift() 定位，不依赖默认位置：
   axes.move_to(ORIGIN).shift(RIGHT * 0.5)  # 为左侧 y 轴标签留出空间

3. y 轴标签天然向左偏移约 1 单位，整体 Axes 须向右平移至少 0.8 单位，防止标签溢出左边缘：
   axes.shift(RIGHT * 0.8)  # y 轴标签最终 x 位置 ≈ axes 左边缘 x - 1.2，必须 ≥ -6.0

4. 轴标签用 font_size=22 以内，创建后检查 label.get_left()[0] ≥ -5.8、label.get_right()[0] ≤ 5.8

5. 图形（Graph/ParametricFunction）绘制范围必须在轴的 x_range/y_range 之内，不要超出轴域：
   graph = axes.plot(lambda x: 1/x, x_range=[0.1, 9.9])  # 严格在 x_range 内

6. 如果同一画面有标题或其他元素，Axes 整体缩小或位移，确保与其他元素无重叠且各自在安全区内

【文字元素防溢出规则】
- 所有 Text / MathTex 在 .play(Write/FadeIn...) 前必须确认 get_left()[0] ≥ -5.8 且 get_right()[0] ≤ 5.8
- 长文字必须先 .scale() 到合适大小再定位，不要先定位再期望 font_size 自动控制宽度
- 跨镜头保留的文字（如标题）在移动到新位置后同样必须满足安全区约束
- .to_corner() / .to_edge() 自带 buff=0.5，安全；但 .move_to() / .shift() 到边缘位置时须手动验证不超界

【坐标系规则（重要）——高频报错根源】
- Manim 所有"点"均为三维 (x, y, z)，z 通常为 0；这是全局约束，无例外
- 凡是传递坐标/顶点/路径点的地方，一律用 3 元素格式：[x, y, 0] 或 np.array([x, y, 0])
  涵盖但不限于：Polygon 顶点、set_points_as_corners、set_anchors_and_handles、Dot 位置、Line 端点、任何接受 Point3D 的参数
- 严禁任何形式的 2D 坐标：[x, y]、np.array([x, y]) 均会导致 shape broadcast 错误
  错误示范：Dot(point=[1, 2])、move_to([1, 2])、Line([0,0], [1,1])、.shift(np.random.uniform(-1,1,2))
  正确示范：Dot(point=[1, 2, 0])、move_to([1, 2, 0])、Line([0,0,0], [1,1,0])、.shift(np.append(np.random.uniform(-1,1,2), 0))
- np.random.uniform / np.random.randn 等随机向量默认是 2D，用于 shift/move_to 前必须补 z=0
- set_points_as_corners、set_anchors_and_handles 等方法参数必须是 shape (n, 3) 的数组
- Axes 构造函数不支持 x_label / y_label 参数；先创建 axes，再用 axes.get_x_axis_label(Text("横轴")) 和 axes.get_y_axis_label(Text("纵轴")) 创建标签
- NumberLine/Axes 的 number_to_point() 返回 3D numpy 数组，不是标量；需要取宽度时必须用 [0] 分量：width = (nl.number_to_point(b) - nl.number_to_point(a))[0]，禁止直接把 number_to_point() 的差值传给 width/height 参数

【字体大小规范（重要）】
- 主标题（视频大标题）：font_size=44
- 节点标签/图形旁说明：font_size=32
- 正文内容（关键词、数字）：font_size=28
- 小标注（公式辅助说明）：font_size=22
- 禁止使用不加 font_size 的裸 Text()（默认值过大，导致布局失控）

【配色系统——活力暖色扁平】
背景：米白 #F5F0E8（渲染器已全局设置，代码无需处理）
主色（暖色）：草莓红 #E8524A、橘橙 #F07D3E、向日葵黄 #F5C518
辅助色（冷色）：天蓝 #4BA3C3、草绿 #5BAD6F
强调色：薰衣草紫 #9B7EC8
文字/轮廓：深炭灰 #2C2C2C
同一画面控制在 1 个主色 + 1 个辅色 + 1 个强调色，避免彩虹式混色
禁止：荧光色、高饱和原色（纯红/纯蓝/纯绿）、纯白文字（白底白字不可见）

【动画节奏规范】
入场动画（按优先级）：
- 图形：GrowFromCenter（弹性感首选）或 DrawBorderThenFill
- 文字：Write
- 箭头：Create（GrowArrow 在当前版本有 bug，禁止使用）
- 次要/背景元素：FadeIn（非首选）

强调动画（关键结论必须使用）：
- Flash、Circumscribe、Indicate 突出关键节点
- 避免只用静态颜色高亮

变换动画：
- 图形演变：ReplacementTransform
- 属性变化（位置/缩放/颜色）：.animate
- 禁止：消灭元素后重建同功能元素

退场动画：FadeOut(element, run_time=0.5)，统一 0.5s

run_time 选择：
- 简单入场：0.8s；标准动画：1.0–1.5s；复杂变换：2.0s；退场：0.5s

【退场检查清单（每个镜头必须执行）】
每个镜头代码开头，隐式维护画布存量列表，对每个存活元素判断：
- 本镜头继续引用或保留 → 不退场，直接使用
- 已完成使命且本镜头不再出现 → 本镜头开头 FadeOut(run_time=0.5)
- 位置与本镜头新元素重叠 → 本镜头开头 FadeOut 或 ReplacementTransform
- 背景性持续元素（如顶部标题） → 保留，除非叙事需要替换

退场动画统一放在本镜头开头（先清场，再出新内容）。

代码注释格式：
# === 镜头 N ===
# 画布存量：[元素列表]
# [元素] → 退场/保留，原因：[一句话]

【动画时序规则】
- 用 self.wait(n) 控制停留时长，单位秒
- 每个镜头 code 的所有 self.play(run_time=...) 与 self.wait(...) 之和需与该镜头 estimated_duration_seconds 匹配（误差 ±1s 可接受）
- 关键图形和结论必须至少保留到对应旁白讲完；禁止旁白尚未结束就清空画面
- 渲染器会自动补齐镜头剩余时长。如果本镜头没有必要的退场或转场，代码末尾保持最终画面即可，不要添加 FadeOut 清场

【视觉优先】
- 除纯标题或总结镜头外，每个镜头至少设计一个承载知识含义的图形动画
- 多用 Circle、Square、Arrow、NumberLine、Axes、Graph、VGroup 构建关系、过程、对比或变化
- 优先让已有图形移动、缩放、变形、连线、分裂或聚合来推进讲解，避免只摆放静态文字
- 公式只展示理解结论不可缺少的关键公式，用 MathTex 配合图形直观解释；不要连续堆砌公式
- 画面文字只保留关键词、数字、公式、简短标注，每帧不超过 15 个汉字

【文字渲染规则（重要）】
- 所有中文、日文等非 ASCII 文字必须使用 Text()，禁止使用 MathTex() 或 Tex()
- MathTex() / Tex() 仅用于纯英文/ASCII 数学公式（如 r"E=mc^2"、r"\frac{{1}}{{2}}"）
- 中英文混排时，中文用 Text()，公式用 MathTex()，再用 VGroup 组合
- 违反此规则会导致 LaTeX 编译报错使视频生成失败

【典型跨镜头示例】
# === 镜头 0（标题引入）===
# 画布存量：空
title = Text("为什么天空是蓝色的？", font_size=44, color=ManimColor("#2C2C2C"))
self.play(Write(title), run_time=1.5)
self.wait(1)

# === 镜头 1（标题缩小，引入图示）===
# 画布存量：title
# title → 保留，缩小移至顶部
self.play(title.animate.scale(0.6).to_edge(UP), run_time=0.8)
sun = Circle(radius=0.5, color=ManimColor("#F07D3E"), fill_opacity=1).shift(LEFT * 4)
earth = Circle(radius=0.3, color=ManimColor("#4BA3C3"), fill_opacity=1).shift(RIGHT * 3)
ray = Arrow(sun.get_right(), earth.get_left(), color=ManimColor("#E8524A"), buff=0.1)
self.play(GrowFromCenter(sun), GrowFromCenter(earth), run_time=1.0)
self.play(Create(ray), run_time=0.8)
# 本镜头无需转场：保留图示，渲染器自动补齐剩余时长
""",
        "remotion": """\
【Remotion 代码规范】

渲染引擎已生成外层结构，code 字段只写放入 <Sequence> 内部的 JSX 片段。禁止在 code 里写 export const VideoScene 外层定义。

画布尺寸：1280 × 720 px（16:9），所有元素坐标和尺寸以此为基准，禁止超出边界。
SVG viewBox 统一使用 "0 0 1280 720"。

【帧与时序规则】
- 在 code 片段内用 useCurrentFrame() 获取当前 <Sequence> 内的相对帧（从 0 开始）
- 动画用 interpolate(frame, [inputRange], [outputRange]) 或 spring({ frame, fps }) 驱动
- estimated_duration_seconds × fps（默认 30）= 该镜头 durationInFrames，渲染引擎自动计算，code 里不要硬编码绝对帧数
- 镜头间过渡用 interpolate + opacity 实现淡入淡出，或用 spring() 做弹性动效

【跨镜头共享元素】
- 跨多个镜头持续存在的元素（背景、顶部标题栏）用 <Sequence from={0} durationInFrames={totalFrames}> 包裹，放在最外层
- 每个镜头的 code 只负责该镜头独有的内容
- 镜头边界不等于清场点；关键元素保持到对应旁白结束，仅在叙事转折或替换时淡出

【配色系统——活力暖色扁平】
背景：米白 #F5F0E8
主色（暖色）：草莓红 #E8524A、橘橙 #F07D3E、向日葵黄 #F5C518
辅助色（冷色）：天蓝 #4BA3C3、草绿 #5BAD6F
强调色：薰衣草紫 #9B7EC8
文字：深炭灰 #2C2C2C
同一画面最多 1 主色 + 1 辅色 + 1 强调色

【字体规范】
- 主标题：fontSize: 56
- 节点标签/图形说明：fontSize: 36
- 正文内容：fontSize: 28
- 小标注：fontSize: 22
- 禁止使用无 fontSize 的裸 style 文字

【动画节奏规范】
入场：spring({ frame, fps, config: { stiffness: 80, damping: 12 } }) 做弹性入场（opacity、translateY、scale）
线性变化：interpolate(frame, [in, out], [from, to], { extrapolateRight: "clamp" })
退场：interpolate(frame, [exitStart, exitEnd], [1, 0]) 实现淡出
强调：scale spring 放大后回弹（stiffness: 200, damping: 10）
避免：所有动画都用 opacity 线性，缺乏弹性感

【视觉优先】
- 除纯标题或总结镜头外，每个镜头至少包含一个承载知识含义的 SVG/CSS 图形动画
- 用路径、位置、大小、连接或形变展示关系和过程，避免静态文字页
- 公式只保留支撑核心结论的关键公式，配合图形解释，避免公式堆砌
- 每帧文字不超过 15 个汉字

【文字渲染规则】
- 所有文字用 <div> 或 <text>（SVG），统一设置 fontFamily 为无衬线体
- 中文避免使用系统默认 serif 字体，推荐 style={{ fontFamily: "PingFang SC, Microsoft YaHei, sans-serif" }}

【典型示例】
// 镜头 0：标题弹性入场
const frame = useCurrentFrame();
const { fps } = useVideoConfig();
const progress = spring({ frame, fps, config: { stiffness: 80, damping: 12 } });
const opacity = interpolate(progress, [0, 1], [0, 1]);
const translateY = interpolate(progress, [0, 1], [30, 0]);
return (
  <AbsoluteFill style={{ background: "#F5F0E8", justifyContent: "center", alignItems: "center" }}>
    <div style={{
      opacity,
      transform: `translateY(${translateY}px)`,
      fontSize: 56,
      color: "#2C2C2C",
      fontWeight: "bold",
      fontFamily: "PingFang SC, Microsoft YaHei, sans-serif"
    }}>
      为什么天空是蓝色的？
    </div>
  </AbsoluteFill>
);

// 镜头 1：散射图示动画
const frame = useCurrentFrame();
const { fps } = useVideoConfig();
const rayProgress = spring({ frame, fps, config: { stiffness: 60, damping: 14 } });
const rayLength = interpolate(rayProgress, [0, 1], [0, 400]);
return (
  <AbsoluteFill style={{ background: "#F5F0E8" }}>
    <svg width="100%" height="100%" viewBox="0 0 1280 720">
      <circle cx={240} cy={360} r={60} fill="#F07D3E" />
      <line x1={300} y1={360} x2={300 + rayLength} y2={360}
            stroke="#4BA3C3" strokeWidth={4} />
      <line x1={300 + rayLength * 0.7} y1={360}
            x2={300 + rayLength * 0.7 + rayLength * 0.3 * 0.7} y2={320}
            stroke="#E8524A" strokeWidth={3} opacity={interpolate(rayProgress, [0.5, 1], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })} />
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
