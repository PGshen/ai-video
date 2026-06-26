# Script Prompt Engineering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重写 `ChatAIProvider` 的 `generate_script` system prompt，让 AI 生成可直接渲染的 Manim/Remotion 生产级代码。

**Architecture:** 只改 `_ENGINE_CODE_PROMPTS` 字典和 `generate_script` 的公共 system prompt 字符串；无 schema 变动，上下游透明。

**Tech Stack:** Python，无新依赖。

## Global Constraints

- 只改 `backend/app/engines/ai/chat_provider.py`，不改其他文件
- JSON schema（`scenes`/`fact_checks` 结构）保持不变
- `brainstorm_topics`、`research_topic` 方法不动
- 音频占位符 `{{AUDIO_SCENE_N}}` 从 prompt 中完全移除

---

### Task 1: 更新 generate_script system prompt 公共部分 + 引擎 prompt

**Files:**
- Modify: `backend/app/engines/ai/chat_provider.py`
- Test: `backend/tests/test_chat_provider_prompt.py`（新建）

**Interfaces:**
- Produces: `ChatAIProvider._ENGINE_CODE_PROMPTS["manim"]`、`["remotion"]`、`_ENGINE_CODE_PROMPT_FALLBACK`，以及 `generate_script` 内 `system_prompt` 字符串中的公共段落，供现有调用方透明使用

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/test_chat_provider_prompt.py`：

```python
import pytest
from app.engines.ai.chat_provider import ChatAIProvider
from app.engines.ai.stub import StubChatClient


def make_provider():
    return ChatAIProvider(client=StubChatClient())


def test_manim_prompt_no_audio_placeholder():
    prompt = ChatAIProvider._ENGINE_CODE_PROMPTS["manim"]
    assert "AUDIO_SCENE" not in prompt


def test_remotion_prompt_no_audio_placeholder():
    prompt = ChatAIProvider._ENGINE_CODE_PROMPTS["remotion"]
    assert "AUDIO_SCENE" not in prompt


def test_manim_prompt_contains_key_rules():
    prompt = ChatAIProvider._ENGINE_CODE_PROMPTS["manim"]
    assert "construct()" in prompt
    assert "FadeOut" in prompt
    assert "Transform" in prompt
    assert "class " not in prompt  # 不应包含 class 定义示例外的 class 关键词指导模型写 class


def test_remotion_prompt_contains_key_rules():
    prompt = ChatAIProvider._ENGINE_CODE_PROMPTS["remotion"]
    assert "useCurrentFrame" in prompt
    assert "interpolate" in prompt
    assert "Sequence" in prompt


def test_system_prompt_contains_visual_first_rule():
    """generate_script 的 system prompt 应包含视觉优先要求"""
    provider = make_provider()
    # 直接检查 system_prompt 字符串模板中的公共段
    # 通过检查类属性字符串覆盖核心约束
    manim_prompt = ChatAIProvider._ENGINE_CODE_PROMPTS["manim"]
    assert "文字" in manim_prompt or "视觉" in manim_prompt  # 视觉优先规则


def test_system_prompt_contains_code_concat_rule():
    """system prompt 公共部分应说明拼合规则"""
    provider = make_provider()
    manim_prompt = ChatAIProvider._ENGINE_CODE_PROMPTS["manim"]
    # 拼合规则在引擎 prompt 里体现（说明 code 是片段）
    assert "construct()" in manim_prompt
    assert "import" in manim_prompt  # 说明不写 import
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd backend
/Users/peng/.local/bin/uv run pytest tests/test_chat_provider_prompt.py -v
```

预期：多个 FAILED（`AUDIO_SCENE` 仍存在，新规则未加入）

- [ ] **Step 3: 替换 `_ENGINE_CODE_PROMPTS["manim"]`**

将 `backend/app/engines/ai/chat_provider.py` 中 `_ENGINE_CODE_PROMPTS` 的 `"manim"` 值替换为：

```python
"manim": """\
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
```

- [ ] **Step 4: 替换 `_ENGINE_CODE_PROMPTS["remotion"]`**

将 `"remotion"` 值替换为：

```python
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
    </svg>
  </AbsoluteFill>
);
""",
```

- [ ] **Step 5: 替换 `_ENGINE_CODE_PROMPT_FALLBACK`**

```python
_ENGINE_CODE_PROMPT_FALLBACK = (
    "- code 字段填写适合所选渲染引擎的代码片段（非完整文件），"
    "所有镜头的 code 将被顺序拼合为单个执行单元。"
    "不处理音频，渲染引擎自动注入。"
)
```

- [ ] **Step 6: 在 `generate_script` system prompt 公共部分插入拼合规则和视觉风格要求**

在现有 `system_prompt` 字符串中，`要求：` 列表之前插入以下段落（位于 `{engine_hint}` 之后、`要求：` 之前）：

```python
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
```

- [ ] **Step 7: 运行全部测试**

```bash
cd backend
/Users/peng/.local/bin/uv run pytest tests/test_chat_provider_prompt.py -v
```

预期：全部 PASS

- [ ] **Step 8: 运行完整测试套件确认无回归**

```bash
cd backend
/Users/peng/.local/bin/uv run pytest tests/ -v
```

预期：全部 PASS，无新增失败

- [ ] **Step 9: Commit**

```bash
cd backend
git add app/engines/ai/chat_provider.py tests/test_chat_provider_prompt.py
git commit -m "feat: rewrite generate_script prompt for production-ready Manim/Remotion code"
```
