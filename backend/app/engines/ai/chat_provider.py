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

【配色系统】
请严格遵循以下配色方案，所有颜色以十六进制表示：
# 背景
- 主背景（亮底）：#F7F3FF
# 正文
- 亮底上的文字：#1C1433
- 深底上的文字：#F7F3FF
- 辅助注释文字：#8E7DC0
# 核心概念色
- 偏差概念主体：#6C4FD4（认知紫）
- 子概念 / 举例说明：#A98EE8（浅紫）
# 语义强调色
- 认知陷阱 / 错误判断：#FF6B6B（红）
- 警示 / 引发注意：#FFB347（橙）
- 理性思维 / 纠偏方法：#4ECDC4（青）
- 正确结论 / 突破偏差：#44CF6C（绿）
- 情感驱动 / 系统1直觉：#FF9EBB（粉）
# 结构辅助色
- 坐标轴 / 网格（深底）：#4A3880
- 坐标轴 / 网格（亮底）：#D4C5F0
# 配色使用原则
1. 以亮底 #F7F3FF 为主场景
2. 红色专用于「偏差/错误」，绿色专用于「正确/结论」，不可混用
3. 橙色用于引发注意的过渡状态，不表示最终结论
4. 青色代表理性分析，与粉色（直觉）形成对比，可用于系统1/系统2的视觉对立
5. 主色饱和度高，确保手机竖屏小尺寸下依然清晰可辨

【视觉精致度规范（重要）】
构图与层次：
- 每个镜头须有明确的视觉层次：背景装饰层 → 主体图形层 → 文字标注层，三层分离，避免元素平铺堆叠
- 图形之间保持充足间距（shift 间距 ≥ 1.5 单位），避免拥挤感
- 半透明背景光晕：在主体元素后方放置 fill_opacity=0.12 的同色系大圆或矩形作衬底，提升视觉厚度
- 箭头统一 stroke_width=3，tip_length=0.2；避免默认粗箭头显得笨重
- 数据图表（Axes/Graph）搭配辅助网格线（DashedLine，opacity=0.25）提升专业感

精致细节：
- 标题镜头：主标题下方配一条细分隔线（Line，stroke_width=1.5，长度与文字同宽，同色系）
- 关键概念节点使用双圆：外圈 stroke_width=1.5、fill_opacity=0.1，内圈实心小圆叠加
- 箭头标注文字 font_size=22，偏移 ≥ 0.3 单位，不贴着箭头
- 多元素左右/上下对比布局时加一条垂直/水平分隔虚线（DashedLine，opacity=0.4）
- 数字或百分比变化用 DecimalNumber 动态滚动，不要静态文字

【动画节奏规范（大气感）】
入场动画：
- 核心图形：GrowFromCenter（弹性感首选）；图表类：Create
- 文字标题：Write；说明性文字：FadeIn（配合轻微向上偏移）
- 箭头：Create（GrowArrow 在当前版本有 bug，禁止使用）
- 多元素错落入场：必须用 LaggedStart([...], lag_ratio=0.2) 制造层次感，禁止所有元素同帧同时出现
- 复杂图示（节点+连线+标注）：分三步出现——先节点，再连线，再标注

强调动画（关键结论必须使用）：
- Flash、Circumscribe、Indicate 突出关键节点
- 关键数字/结论：Indicate 后保持高亮颜色，不要闪一下就恢复原色
- 两侧对比：AnimationGroup(Indicate(A), Indicate(B)) 同步触发，视觉冲击更强
- 避免只用静态颜色高亮

变换动画：
- 图形演变：ReplacementTransform（保持动画连续性）
- 属性变化（位置/缩放/颜色）：.animate 链式调用，如 .animate.scale(1.2).set_color(...)
- 分裂/聚合：VGroup.animate.arrange() 展示元素重组过程
- 禁止：消灭元素后重建同功能元素

退场动画：
- 单个元素：FadeOut(element, run_time=0.5)
- 多元素同时退场：FadeOut(VGroup(a, b, c), run_time=0.6)，整洁利落

run_time 选择：
- 简单入场：0.8s；标准动画：1.2s；关键变换/强调结论：1.8–2.0s；退场：0.5s
- LaggedStart 整体时长控制在 1.5–2.0s，lag_ratio=0.15–0.25

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
- 使用 LaggedStart 错落展示多元素，节点+连线+标注分三步入场，避免同帧全部出现
- 公式只展示理解结论不可缺少的关键公式，用 MathTex 配合图形直观解释；不要连续堆砌公式
- 画面文字只保留关键词、数字、公式、简短标注，每帧不超过 15 个汉字
- 每个镜头的图形元素数量控制在 3–6 个，宁可精少，不要密集平铺

【文字渲染规则（重要）】
- 所有中文、日文等非 ASCII 文字必须使用 Text()，禁止使用 MathTex() 或 Tex()
- MathTex() / Tex() 仅用于纯英文/ASCII 数学公式（如 r"E=mc^2"、r"\frac{{1}}{{2}}"）
- 中英文混排时，中文用 Text()，公式用 MathTex()，再用 VGroup 组合
- 违反此规则会导致 LaTeX 编译报错使视频生成失败

【典型跨镜头示例】
# === 镜头 0（标题引入）===
# 画布存量：空
title = Text("为什么天空是蓝色的？", font_size=44, color=ManimColor("#1C1433"))
self.play(Write(title), run_time=1.5)
self.wait(1)

# === 镜头 1（标题缩小，引入图示）===
# 画布存量：title
# title → 保留，缩小移至顶部
self.play(title.animate.scale(0.6).to_edge(UP), run_time=0.8)
sun = Circle(radius=0.5, color=ManimColor("#FFB347"), fill_opacity=1).shift(LEFT * 4)
earth = Circle(radius=0.3, color=ManimColor("#4ECDC4"), fill_opacity=1).shift(RIGHT * 3)
ray = Arrow(sun.get_right(), earth.get_left(), color=ManimColor("#6C4FD4"), buff=0.1)
self.play(GrowFromCenter(sun), GrowFromCenter(earth), run_time=1.0)
self.play(Create(ray), run_time=0.8)
# 本镜头无需转场：保留图示，渲染器自动补齐剩余时长
""",
        "remotion": """\
【Remotion 代码规范】

渲染引擎为每个镜头生成一个具名 React 组件（如 _Scene0、_Scene1），code 字段即该组件的函数体。
禁止在 code 里写 export、const _SceneN、const VideoScene 等外层定义——这些由渲染引擎自动生成。

画布尺寸：1280 × 720 px（16:9），所有元素坐标和尺寸以此为基准，禁止超出边界。
SVG viewBox 统一使用 "0 0 1280 720"。

【布局与坐标规范（重要）】
坐标系：原点在左上角，x 向右，y 向下；画布中心为 (640, 360)。

定位原则——先声明位置常量，再从常量推导所有相关坐标：
```
// ✅ 正确：先定义盒子中心，再推导连线端点
const L_CX = 280, L_CY = 360, BOX_W = 200, BOX_H = 160;
const R_CX = 1000, R_CY = 360;
// 连线从左盒右边缘 → 右盒左边缘，完全由常量推导
const lineX1 = L_CX + BOX_W / 2;
const lineX2 = R_CX - BOX_W / 2;

// ❌ 错误：凭感觉写魔法数字，导致连线对不上元素
<line x1={420} y1={360} x2={700} y2={340} />  // 700 远未到右盒
```

常用布局参考（不超出边界）：
- 左右两列：左中心 x=320，右中心 x=960，各留 ≥80px 边距
- 三列均分：x=213、640、1067
- 上下两区：上中心 y=210，下中心 y=510
- 全屏居中：cx=640，cy=360
- 顶部标题栏：y=60，高度 80px；正文区：y=140–680

连线/曲线必须从元素位置常量计算，禁止凭感觉估算 x/y 魔法数字。
带弯曲的连线用 SVG `<path d="M {x1} {y1} Q {midX} {controlY} {x2} {y2}" />`，控制点 midX=(x1+x2)/2。

【帧与时序规则】
- code 片段在 React 组件函数体内执行，可直接调用 Hooks：useCurrentFrame()、useVideoConfig()
- useCurrentFrame() 返回当前镜头内的相对帧（从 0 开始）
- 渲染引擎自动注入 const durationInFrames = N;（N = estimated_duration_seconds × fps），可直接使用
- 动画用 interpolate(frame, [inputRange], [outputRange]) 或 spring({ frame, fps }) 驱动
- 镜头间过渡用 interpolate + opacity 实现淡入淡出，或用 spring() 做弹性动效

【跨镜头共享元素】
- 跨多个镜头持续存在的元素（背景、顶部标题栏）用 <Sequence from={0} durationInFrames={totalFrames}> 包裹，放在最外层
- 每个镜头的 code 只负责该镜头独有的内容
- 镜头边界不等于清场点；关键元素保持到对应旁白结束，仅在叙事转折或替换时淡出

【配色系统】
请严格遵循以下配色方案，所有颜色以十六进制表示：
# 背景
- 主背景（亮底）：#F7F3FF
# 正文
- 亮底上的文字：#1C1433
- 深底上的文字：#F7F3FF
- 辅助注释文字：#8E7DC0
# 核心概念色
- 偏差概念主体：#6C4FD4（认知紫）
- 子概念 / 举例说明：#A98EE8（浅紫）
# 语义强调色
- 认知陷阱 / 错误判断：#FF6B6B（红）
- 警示 / 引发注意：#FFB347（橙）
- 理性思维 / 纠偏方法：#4ECDC4（青）
- 正确结论 / 突破偏差：#44CF6C（绿）
- 情感驱动 / 系统1直觉：#FF9EBB（粉）
# 结构辅助色
- 坐标轴 / 网格（深底）：#4A3880
- 坐标轴 / 网格（亮底）：#D4C5F0
# 配色使用原则
1. 以亮底 #F7F3FF 为主场景
2. 红色专用于「偏差/错误」，绿色专用于「正确/结论」，不可混用
3. 橙色用于引发注意的过渡状态，不表示最终结论
4. 青色代表理性分析，与粉色（直觉）形成对比，可用于系统1/系统2的视觉对立
5. 主色饱和度高，确保手机竖屏小尺寸下依然清晰可辨

【字体规范】
- 主标题：fontSize: 56
- 节点标签/图形说明：fontSize: 36
- 正文内容：fontSize: 28
- 小标注：fontSize: 22
- 禁止使用无 fontSize 的裸 style 文字

【视觉精致度规范（重要）】
构图与层次：
- 每个镜头须有明确的视觉层次：背景装饰层 → 主体 SVG 图形层 → 文字标注层，三层分离
- 元素之间保持充足间距（≥ 40px），避免拥挤感
- 背景光晕效果：在核心元素后方叠加一个半透明径向渐变圆（opacity: 0.12），提升视觉厚度
  示例：<circle cx={640} cy={360} r={200} fill="#6C4FD4" opacity={0.1} />
- 箭头使用 SVG <defs><marker> 自定义箭头头部，strokeWidth=2.5，避免默认粗箭头
- 数据图表类镜头添加辅助网格线（strokeDasharray="4 6"，opacity=0.2）

精致细节：
- 标题下方配装饰线：<line> 宽度与文字等宽，strokeWidth=1.5，同色系
- 关键节点使用双圆叠加：外圈半透明（opacity=0.15），内圈实心
- 标注文字使用 fontSize=20，偏移文字中心 ≥ 12px，不贴着图形边缘
- 多元素对比布局加垂直/水平分隔线（strokeDasharray="6 4"，opacity=0.35）

【动画节奏规范（大气感）】
入场（弹性为主）：
- 主体图形：spring({ frame, fps, config: { stiffness: 70, damping: 14 } }) 驱动 scale + opacity
- 文字标题：spring({ stiffness: 80, damping: 12 }) 驱动 translateY（从 +30px）+ opacity
- 多元素错落入场：每个元素用 Math.max(0, frame - delay) 作为偏移帧，delay 间隔 4–6 帧，制造层次感
- 连线/路径生长：interpolate(frame, [0, durationInFrames * 0.6], [0, totalLength]) 驱动 strokeDashoffset

强调动画：
- 关键结论：scale spring 放大至 1.15 后回弹（stiffness: 200, damping: 10）
- 颜色切换：interpolate(frame, [highlightStart, highlightStart+8], [0, 1]) 驱动颜色插值
- 数字滚动：interpolate(frame, [0, durationInFrames*0.7], [startVal, endVal], { extrapolateRight: "clamp" }) 配合 Math.round

退场：
- interpolate(frame, [exitStart, exitStart+10], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })
- 退场时配合轻微下移（translateY 从 0 → +15px）增加动感

避免：所有动画都用 opacity 线性；元素突然出现无任何过渡；缺乏弹性感

【视觉优先】
- 除纯标题或总结镜头外，每个镜头至少包含一个承载知识含义的 SVG/CSS 图形动画
- 用路径生长、位置移动、大小缩放、连接关系或形变动画推进讲解，避免静态文字页
- 公式只保留支撑核心结论的关键公式，配合图形解释，避免公式堆砌
- 每帧文字不超过 15 个汉字

【文字渲染规则】
- 所有文字用 <div> 或 <text>（SVG），统一设置 fontFamily 为无衬线体
- 中文避免使用系统默认 serif 字体，推荐 style={{ fontFamily: "PingFang SC, Microsoft YaHei, sans-serif" }}
- 标题文字加 letterSpacing: 2 提升精致感；正文 letterSpacing: 0.5

【典型示例】
// 镜头 0：标题精致入场（弹性 + 装饰线）
const frame = useCurrentFrame();
const { fps } = useVideoConfig();
const titleSpring = spring({ frame, fps, config: { stiffness: 80, damping: 12 } });
const titleOpacity = interpolate(titleSpring, [0, 1], [0, 1]);
const titleY = interpolate(titleSpring, [0, 1], [30, 0]);
const lineSpring = spring({ frame: Math.max(0, frame - 8), fps, config: { stiffness: 60, damping: 14 } });
const lineWidth = interpolate(lineSpring, [0, 1], [0, 360]);
return (
  <AbsoluteFill style={{ background: "#F7F3FF", justifyContent: "center", alignItems: "center", flexDirection: "column", gap: 16 }}>
    <div style={{ opacity: titleOpacity, transform: `translateY(${titleY}px)`, fontSize: 56, color: "#1C1433", fontWeight: "bold", fontFamily: "PingFang SC, Microsoft YaHei, sans-serif", letterSpacing: 2 }}>
      为什么天空是蓝色的？
    </div>
    <svg width={lineWidth} height={3} style={{ overflow: "visible" }}>
      <line x1={0} y1={1.5} x2={lineWidth} y2={1.5} stroke="#6C4FD4" strokeWidth={1.5} />
    </svg>
  </AbsoluteFill>
);

// 镜头 1：两列对比 + 曲线连接（布局常量推导示例）
const frame = useCurrentFrame();
const { fps } = useVideoConfig();
// ① 先声明所有位置常量
const BOX_W = 220, BOX_H = 160, CY = 360;
const L_CX = 280, R_CX = 1000;
// ② 连线端点从常量推导，绝不猜数字
const lineX1 = L_CX + BOX_W / 2;
const lineX2 = R_CX - BOX_W / 2;
const midX = (lineX1 + lineX2) / 2;
const sp = spring({ frame, fps, config: { stiffness: 60, damping: 14 } });
const progress = interpolate(sp, [0, 1], [0, 1]);
const boxSpring = spring({ frame: Math.max(0, frame - 4), fps, config: { stiffness: 70, damping: 14 } });
return (
  <AbsoluteFill style={{ background: "#F7F3FF" }}>
    <svg width="100%" height="100%" viewBox="0 0 1280 720">
      {/* 左盒 */}
      <rect x={L_CX - BOX_W/2} y={CY - BOX_H/2} width={BOX_W} height={BOX_H}
            rx={12} fill="#A98EE820" stroke="#6C4FD4" strokeWidth={2}
            opacity={interpolate(boxSpring, [0,1],[0,1])} />
      <text x={L_CX} y={CY + 8} textAnchor="middle" fontSize={28}
            fill="#1C1433" fontFamily="PingFang SC, sans-serif">18岁前</text>
      {/* 右盒 */}
      <rect x={R_CX - BOX_W/2} y={CY - BOX_H/2} width={BOX_W} height={BOX_H}
            rx={12} fill="#4ECDC420" stroke="#4ECDC4" strokeWidth={2}
            opacity={interpolate(boxSpring, [0,1],[0,1])} />
      <text x={R_CX} y={CY + 8} textAnchor="middle" fontSize={28}
            fill="#1C1433" fontFamily="PingFang SC, sans-serif">18岁后</text>
      {/* 曲线：端点完全由常量推导 */}
      <path d={`M ${lineX1} ${CY} Q ${midX} ${CY - 80} ${interpolate(progress, [0,1],[lineX1, lineX2])} ${CY}`}
            fill="none" stroke="#FFB347" strokeWidth={3} strokeDasharray="8 5" />
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
- 认知紫 #6C4FD4（核心概念）、浅紫 #A98EE8（子概念/举例）
- 错误红 #FF6B6B（陷阱/错误）、警示橙 #FFB347（引发注意）
- 理性青 #4ECDC4（纠偏/分析）、结论绿 #44CF6C（正确结论）、直觉粉 #FF9EBB（情感/系统1）
- 深炭 #1C1433（文字/轮廓）；背景：淡紫白 #F7F3FF

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
- 优先用位置移动、大小缩放、连线生长、分裂、聚合或形变推进讲解，避免只摆放静态文字
- 先用直观图形讲清概念，只在支撑核心结论时引入关键公式，不堆砌推导
- 每帧文字不超过 15 个汉字
- 图形元素数量控制在 3–6 个，精而有层次；多元素须错落入场，不要同时全部出现

【精致度要求】
- 标题镜头：主标题下方配装饰细线，主题色渐显
- 概念节点：建议双圆（外圈半透明光晕 + 内圈实心）或带圆角矩形容器，不要裸文字
- 连线/箭头：描述粗细（"细箭头"/"粗连线"）和方向感（"从左向右延伸"）
- 强调结论时：描述"放大高亮"或"周围扩散光环"，让代码生成阶段能对应 Indicate/Flash

【示例】
镜头 0："淡紫白背景。中央主标题文字逐字写入，下方同步出现认知紫装饰细线从中心向两侧伸展。整体保留至旁白结束，延续到下一镜头。"
镜头 1："承接上镜标题，缩小移至顶部保留。画面中央：左侧出现警示橙双圆节点（外圈半透明光晕）代表太阳，错落入场后认知紫细箭头从太阳右侧向右生长延伸，末端分裂成多条散射分支，展示光的散射过程。图示保留至旁白结束。"
镜头 2："承接上镜图示。理性青短波分支放大高亮并周围扩散光环（强调动画），其余颜色分支同时淡化至低透明度。右侧错落入场辅助注释文字'蓝光波长最短'。旁白结束后标题和散射主图完成使命退场，保留高亮青色分支作为下镜视觉锚点。"\
""",
        "remotion": """\
【Remotion 画面描述规范——弱技术层】
description 字段只写画面意图，由代码生成阶段翻译为 React/TSX 动画代码。禁止在 description 中出现组件名、hook 名或代码语法。

【可用图形词汇】
SVG 图形：圆形（含双圆/光晕圆）、矩形（含圆角矩形容器）、路径、线条、多边形、径向渐变背景光晕
连接关系：箭头（细/粗）、连线（实线/虚线）、路径生长动画
文字层：标题、说明文字、数字标注、滚动数字、关键公式（文字描述）
装饰元素：装饰细线、分隔线、背景辅助网格

【配色参考】
颜色名与 Hex 对照（description 中用颜色名即可）：
认知紫 #6C4FD4、浅紫 #A98EE8；错误红 #FF6B6B、警示橙 #FFB347；理性青 #4ECDC4、结论绿 #44CF6C；直觉粉 #FF9EBB；深炭 #1C1433；背景：淡紫白 #F7F3FF

【跨镜头衔接说明】
Remotion 每个 Sequence 是独立作用域。跨镜头持续存在的元素（背景、顶部标题栏）在 description 中注明"作为共享层延续"。

【内容要求】
- 除纯标题或总结镜头外，每个镜头至少包含一个承载知识含义的 SVG/CSS 图形动画
- 先图形讲解，关键公式只在支撑核心结论时出现，不堆砌推导
- 每帧文字不超过 15 个汉字
- 图形元素数量控制在 3–6 个，精而有层次；多元素须描述"错落依次入场"

【精致度要求】
- 标题镜头：主标题下方配同色装饰线从中心向两侧伸展
- 概念节点：建议"双圆节点（外圈半透明光晕+内圈实心）"或"带圆角矩形容器"
- 连线/路径：描述"从左向右生长延伸"等动态过程，而非"出现一条线"
- 强调结论：描述"弹性放大后回弹"或"周围扩散光环"
- 数字变化：描述"数字从0滚动到X"而非静态显示

【示例】
镜头 0："淡紫白背景。中央主标题文字弹性入场（从下方轻微上移），下方认知紫装饰细线同步从中心向两侧伸展。整体保留至旁白结束。"
镜头 1："背景和缩小后的标题作为共享层延续至顶部。画面中央 SVG：左侧警示橙双圆节点（外圈半透明光晕）弹性入场代表太阳，稍后理性青细线从节点右侧向右生长延伸，末端弹性分裂成多条散射路径，展示光的散射过程。图示保留至旁白结束。"\
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
