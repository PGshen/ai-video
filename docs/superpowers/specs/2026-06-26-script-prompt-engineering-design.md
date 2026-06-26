# 脚本生成 Prompt 工程优化设计

> 日期：2026-06-26 | 状态：已批准

---

## 背景与目标

当前 `ChatAIProvider.generate_script` 的 system prompt 对渲染引擎的约束过于简略：
- Manim/Remotion 各只有 3-4 行说明 + 一个最小示例
- 没有说明镜头代码的拼合规则和变量生命周期
- 没有视觉优先的内容风格要求

目标：重写 `_ENGINE_CODE_PROMPTS`，让 AI 生成可直接渲染的生产级代码。

---

## 架构约定（两引擎共用）

渲染 Worker 的拼合行为：

1. 所有 `scenes[i].code` 按 `scene_index` 顺序拼接
2. 每段前插入注释 `# === 镜头 N ===`（Manim）或 `{/* === 镜头 N === */}`（Remotion）
3. 拼接结果作为单个执行单元运行
4. 音频由渲染引擎在每个镜头开始时自动注入，`code` 里不处理音频

这个约定必须在 system prompt 公共部分明确告知模型。

---

## §1 公共 system prompt 新增内容

在现有 JSON 格式说明和 `scenes`/`fact_checks` 结构之后，加入：

```
【代码拼合规则】
所有镜头的 code 字段将被渲染引擎按 scene_index 顺序拼合为单个执行单元。
每段之间插入注释分隔符。code 字段只写代码片段，不写外层结构（详见各引擎规范）。
音频由渲染引擎自动注入，code 里不处理音频。

【内容风格要求】
- 优先用图形、图示、数学公式、几何动画表达概念，而非大段文字
- 画面上的文字只保留必要的：关键词、数字、公式、简短标注（每帧不超过 15 个汉字或等效量）
- 旁白（narration）负责讲解，画面负责视觉化，两者分工，不要让画面重复旁白内容
```

---

## §2 Manim prompt

替换现有 `_ENGINE_CODE_PROMPTS["manim"]`：

```
【Manim 代码规范】

渲染引擎已生成外层结构，code 字段只写 construct() 方法体内的代码片段：

  from manim import *
  class VideoScene(Scene):
      def construct(self):
          # === 镜头 0 ===
          <scene 0 的 code>
          # === 镜头 1 ===
          <scene 1 的 code>
          ...

禁止在 code 里写 class 定义、def construct、import 语句。

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
- 公式用 MathTex，避免用 Text 堆砌大段说明
- 善用 Create、Write、GrowArrow、DrawBorderThenFill、Transform 等动效让图形"活"起来

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
self.play(FadeOut(light_ray), FadeOut(earth))  # 镜头 1 结束清场，保留 sun 供镜头 2 使用
```

---

## §3 Remotion prompt

替换现有 `_ENGINE_CODE_PROMPTS["remotion"]`：

```
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
- 文字只用于关键词、数字、公式标注
- 善用 spring() 做元素入场动效，interpolate 做连续属性变化（位置、缩放、透明度、颜色）

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
const frame = useCurrentFrame();
const { fps } = useVideoConfig();
const progress = spring({ frame, fps, config: { stiffness: 60, damping: 12 } });
const rayWidth = interpolate(progress, [0, 1], [0, 300]);
return (
  <AbsoluteFill style={{ background: "#0a0a0a" }}>
    <svg width="100%" height="100%" viewBox="0 0 1280 720">
      <circle cx={200} cy={360} r={60} fill="#FFD700" />
      <line x1={260} y1={360} x2={260 + rayWidth} y2={360}
            stroke="white" strokeWidth={3} />
      {/* 散射粒子等图形动画 */}
    </svg>
  </AbsoluteFill>
);
```

---

## §4 实现方式

### 改动范围

唯一改动文件：`backend/app/engines/ai/chat_provider.py`

1. **`_ENGINE_CODE_PROMPTS["manim"]`**：完整替换为 §2 内容
2. **`_ENGINE_CODE_PROMPTS["remotion"]`**：完整替换为 §3 内容
3. **`_ENGINE_CODE_PROMPT_FALLBACK`**：更新为通用兜底说明（说明 code 是片段、不处理音频）
4. **`generate_script` system prompt 公共部分**：在现有 JSON 格式说明后插入 §1 的代码拼合规则和内容风格要求

### 不改动

- JSON schema（`scenes`/`fact_checks` 结构不变）
- `ScriptWorker`、Temporal workflow、API 路由（prompt 改动对上下游透明）
- `brainstorm_topics`、`research_topic` 方法（无关）

---

## 决策记录

| 决策 | 选择 | 原因 |
|------|------|------|
| 代码目标质量 | 可直接渲染的生产代码 | 减少人工修复成本，审核时只需审内容不需修代码 |
| 场景结构 | 整个视频一个 Scene / Composition | 镜头间有变量依赖，多 Scene 会断裂；PRD 设计如此 |
| 音频处理 | code 不写，渲染引擎注入 | 简化 AI 任务；渲染引擎统一管理音画同步 |
| 视觉风格约束 | 写入 system prompt | 知识视频的核心价值在图示动画，文字堆砌无差异化 |
| prompt 方案 | 内联教学型（方案 A） | 改动最小，只改字符串；可直接测试效果 |
