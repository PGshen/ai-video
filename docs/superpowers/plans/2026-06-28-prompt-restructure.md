# Prompt Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构 `chat_provider.py` 中的四个提示词常量，实现叙事/代码两阶段职责彻底分离，并引入新视觉规范系统（活力暖色、字体规范、画布安全区、动画节奏、退场清单）。

**Architecture:** 只修改 `ChatAIProvider` 类的四个字符串常量：`_NARRATIVE_ENGINE_HINTS["manim"]`、`_NARRATIVE_ENGINE_HINTS["remotion"]`、`_ENGINE_CODE_PROMPTS["manim"]`、`_ENGINE_CODE_PROMPTS["remotion"]`。叙事阶段 hint 重写为弱技术层（无类名/变量名），代码生成阶段 hint 接管全部渲染规范。

**Tech Stack:** Python 字符串常量，pytest

## Global Constraints

- 只改 `backend/app/engines/ai/chat_provider.py` 中的提示词字符串，不改函数签名、返回类型、数据库、前端
- 中文提示词，保持现有语言风格
- 测试命令：`cd backend && /Users/peng/.local/bin/uv run pytest tests/test_chat_provider_prompt.py -v`
- 新配色：草莓红 `#E8524A`、橘橙 `#F07D3E`、向日葵黄 `#F5C518`、天蓝 `#4BA3C3`、草绿 `#5BAD6F`、薰衣草紫 `#9B7EC8`、深炭灰 `#2C2C2C`、米白背景 `#F5F0E8`
- Manim 画布安全区：x ∈ [-6.0, 6.0]，y ∈ [-3.5, 3.5]
- 字体层级：主标题 44、节点标签 32、正文 28、小标注 22，禁止裸 `Text()` 不加 font_size

---

## File Map

| 文件 | 操作 | 内容 |
|---|---|---|
| `backend/app/engines/ai/chat_provider.py` | Modify | 重写 4 个字符串常量 |
| `backend/tests/test_chat_provider_prompt.py` | Modify | 更新断言匹配新 spec，新增覆盖新规则的测试 |

---

## Task 1: 更新测试文件以匹配新规范

**Files:**
- Modify: `backend/tests/test_chat_provider_prompt.py`

**Interfaces:**
- Produces: 可运行但当前会失败的测试，驱动 Task 2/3 的实现

- [ ] **Step 1: 运行现有测试，确认全部通过（建立基线）**

```bash
cd backend && /Users/peng/.local/bin/uv run pytest tests/test_chat_provider_prompt.py -v
```

预期：全部 PASS（当前代码未改动）

- [ ] **Step 2: 替换 `test_narrative_hints_require_graphics_key_formulas_and_macaron_palette`**

将该测试改为检查新配色和弱技术层规范：

```python
def test_narrative_hints_visual_style_and_content_rules():
    for prompt in ChatAIProvider._NARRATIVE_ENGINE_HINTS.values():
        # 新配色关键词（活力暖色）
        assert "#E8524A" in prompt or "#F07D3E" in prompt or "#4BA3C3" in prompt
        # 关键叙事规则保留
        assert "关键公式" in prompt
        assert "旁白结束" in prompt

    manim_prompt = ChatAIProvider._NARRATIVE_ENGINE_HINTS["manim"]
    # 弱技术层：有图形类型词汇但无类名
    assert "圆形" in manim_prompt or "箭头" in manim_prompt or "坐标轴" in manim_prompt
    assert "Circle" not in manim_prompt   # 禁止 Manim 类名
    assert "VGroup" not in manim_prompt
    assert ".animate" not in manim_prompt
    # 退场意图描述
    assert "退场" in manim_prompt
    assert "保留" in manim_prompt
```

- [ ] **Step 3: 新增代码生成阶段规范测试**

在同一文件末尾追加：

```python
def test_manim_code_prompt_font_size_rules():
    prompt = ChatAIProvider._ENGINE_CODE_PROMPTS["manim"]
    assert "font_size" in prompt
    assert "44" in prompt   # 主标题
    assert "32" in prompt   # 节点标签
    assert "28" in prompt   # 正文
    assert "22" in prompt   # 小标注


def test_manim_code_prompt_canvas_safety_zone():
    prompt = ChatAIProvider._ENGINE_CODE_PROMPTS["manim"]
    assert "14.2" in prompt or "安全区" in prompt
    assert "-6.0" in prompt or "[-6" in prompt
    assert "3.5" in prompt or "[-3" in prompt


def test_manim_code_prompt_warm_color_palette():
    prompt = ChatAIProvider._ENGINE_CODE_PROMPTS["manim"]
    assert "#E8524A" in prompt   # 草莓红
    assert "#F07D3E" in prompt   # 橘橙
    assert "#4BA3C3" in prompt   # 天蓝
    assert "#2C2C2C" in prompt   # 深炭灰


def test_manim_code_prompt_animation_rhythm():
    prompt = ChatAIProvider._ENGINE_CODE_PROMPTS["manim"]
    assert "GrowFromCenter" in prompt
    assert "DrawBorderThenFill" in prompt
    assert "Flash" in prompt or "Circumscribe" in prompt


def test_manim_code_prompt_exit_checklist():
    prompt = ChatAIProvider._ENGINE_CODE_PROMPTS["manim"]
    assert "画布存量" in prompt
    assert "镜头开头" in prompt or "开头" in prompt
    assert "run_time=0.5" in prompt


def test_remotion_code_prompt_warm_colors():
    prompt = ChatAIProvider._ENGINE_CODE_PROMPTS["remotion"]
    assert "#E8524A" in prompt or "#F07D3E" in prompt
    assert "#4BA3C3" in prompt
    assert "#2C2C2C" in prompt


def test_remotion_code_prompt_canvas_size():
    prompt = ChatAIProvider._ENGINE_CODE_PROMPTS["remotion"]
    assert "1280" in prompt or "720" in prompt or "canvas" in prompt.lower() or "画布" in prompt
```

- [ ] **Step 4: 运行测试，确认新测试失败、旧测试仍通过**

```bash
cd backend && /Users/peng/.local/bin/uv run pytest tests/test_chat_provider_prompt.py -v
```

预期：
- 旧有测试：PASS
- 新增/修改测试：FAIL（因为常量还未改）

- [ ] **Step 5: Commit 测试**

```bash
git add backend/tests/test_chat_provider_prompt.py
git commit -m "test: update prompt tests to match new visual spec and 2-stage separation"
```

---

## Task 2: 重写叙事阶段 hints（`_NARRATIVE_ENGINE_HINTS`）

**Files:**
- Modify: `backend/app/engines/ai/chat_provider.py`（只改 `_NARRATIVE_ENGINE_HINTS` 字典）

**Interfaces:**
- Consumes: Task 1 定义的失败测试
- Produces: `_NARRATIVE_ENGINE_HINTS["manim"]` 和 `["remotion"]` 的新内容，满足 Task 1 测试

- [ ] **Step 1: 替换 `_NARRATIVE_ENGINE_HINTS["manim"]` 的全部内容**

将 `chat_provider.py` 中 `_NARRATIVE_ENGINE_HINTS` 字典的 `"manim"` 值替换为：

```python
        "manim": """\
【Manim 画面描述规范——弱技术层】
description 字段只写画面意图，由代码生成阶段翻译为 Manim 动画代码。禁止在 description 中出现 Manim 类名、变量名或代码语法。

【可用图形词汇】
几何图形：圆形、矩形、三角形、多边形、路径
连接关系：箭头、双向箭头、连线、虚线
数据图示：坐标轴、折线图、柱状图、散点、数轴、网格
文字内容：标题文字、说明标注、关键公式（用文字描述，如"E=mc² 公式"）

【配色参考（用颜色名描述，无需 Hex）】
- 暖色：草莓红、橘橙、向日葵黄
- 冷色辅助：天蓝、草绿、薰衣草紫
- 文字/轮廓：深炭灰；背景：米白（渲染器已设置）

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
```

- [ ] **Step 2: 替换 `_NARRATIVE_ENGINE_HINTS["remotion"]` 的全部内容**

```python
        "remotion": """\
【Remotion 画面描述规范——弱技术层】
description 字段只写画面意图，由代码生成阶段翻译为 React/TSX 动画代码。禁止在 description 中出现组件名、hook 名或代码语法。

【可用图形词汇】
SVG 图形：圆形、矩形、路径、线条、多边形
连接关系：箭头、连线
文字层：标题、说明文字、数字标注、关键公式（文字描述）

【配色参考（用颜色名描述，无需 Hex）】
暖色：草莓红、橘橙、向日葵黄；冷色辅助：天蓝、草绿；文字：深炭灰；背景：米白

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
```

- [ ] **Step 3: 运行测试，确认叙事相关测试通过**

```bash
cd backend && /Users/peng/.local/bin/uv run pytest tests/test_chat_provider_prompt.py -v -k "narrative"
```

预期：`test_narrative_hints_visual_style_and_content_rules` PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/engines/ai/chat_provider.py
git commit -m "feat: rewrite narrative engine hints to weak-technical-layer description spec"
```

---

## Task 3: 重写 Manim 代码生成 prompt（`_ENGINE_CODE_PROMPTS["manim"]`）

**Files:**
- Modify: `backend/app/engines/ai/chat_provider.py`（只改 `_ENGINE_CODE_PROMPTS["manim"]`）

**Interfaces:**
- Consumes: Task 1 中 `test_manim_code_prompt_*` 系列失败测试
- Produces: 满足字体、画布、配色、动画节奏、退场清单全部测试的新 Manim 代码生成 prompt

- [ ] **Step 1: 将 `_ENGINE_CODE_PROMPTS["manim"]` 替换为新内容**

用以下内容完整替换（保留现有变量生命周期、坐标系、文字渲染规则，新增视觉规范系统）：

```python
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

【坐标系规则（重要）】
- Manim 内部所有点坐标均为三维 (x, y, z)，z 通常为 0
- 禁止使用 np.array([x, y]) 等二维坐标，必须写 np.array([x, y, 0])
- set_points_as_corners、set_anchors_and_handles 等方法参数必须是 shape (n, 3) 的数组
- Axes 构造函数不支持 x_label / y_label 参数；先创建 axes，再用 axes.get_x_axis_label(Text("横轴")) 和 axes.get_y_axis_label(Text("纵轴")) 创建标签

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
- 箭头：GrowArrow
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
self.play(GrowArrow(ray), run_time=0.8)
# 本镜头无需转场：保留图示，渲染器自动补齐剩余时长
""",
```

- [ ] **Step 2: 运行 Manim 代码生成相关测试**

```bash
cd backend && /Users/peng/.local/bin/uv run pytest tests/test_chat_provider_prompt.py -v -k "manim"
```

预期：`test_manim_code_prompt_font_size_rules`、`test_manim_code_prompt_canvas_safety_zone`、`test_manim_code_prompt_warm_color_palette`、`test_manim_code_prompt_animation_rhythm`、`test_manim_code_prompt_exit_checklist` 全部 PASS

- [ ] **Step 3: 运行全部测试，确认无回归**

```bash
cd backend && /Users/peng/.local/bin/uv run pytest tests/test_chat_provider_prompt.py -v
```

预期：全部 PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/engines/ai/chat_provider.py
git commit -m "feat: rewrite Manim code gen prompt with visual system, canvas safety, font spec, exit checklist"
```

---

## Task 4: 重写 Remotion 代码生成 prompt（`_ENGINE_CODE_PROMPTS["remotion"]`）

**Files:**
- Modify: `backend/app/engines/ai/chat_provider.py`（只改 `_ENGINE_CODE_PROMPTS["remotion"]`）

**Interfaces:**
- Consumes: Task 1 中 `test_remotion_code_prompt_warm_colors`、`test_remotion_code_prompt_canvas_size` 失败测试
- Produces: 满足 Remotion 相关测试的新 prompt

- [ ] **Step 1: 将 `_ENGINE_CODE_PROMPTS["remotion"]` 替换为新内容**

```python
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
```

- [ ] **Step 2: 运行全部测试**

```bash
cd backend && /Users/peng/.local/bin/uv run pytest tests/test_chat_provider_prompt.py -v
```

预期：全部 PASS

- [ ] **Step 3: 同时运行更广泛的测试套件，确认无回归**

```bash
cd backend && /Users/peng/.local/bin/uv run pytest tests/ -v --ignore=tests/test_manim_render_engine.py -x
```

预期：全部 PASS（test_manim_render_engine.py 涉及环境依赖，可跳过）

- [ ] **Step 4: Commit**

```bash
git add backend/app/engines/ai/chat_provider.py
git commit -m "feat: rewrite Remotion code gen prompt with warm color palette, canvas size, font spec, spring animations"
```

---

## Self-Review

**Spec coverage 检查：**
- ✅ 叙事阶段弱技术层（无类名/变量名）→ Task 2
- ✅ 弱技术层允许图形类型词汇 → Task 2
- ✅ 活力暖色配色系统 → Task 3、4
- ✅ 字体大小规范（4 层级）→ Task 3、4
- ✅ Manim 画布安全区 x∈[-6,6] y∈[-3.5,3.5] → Task 3
- ✅ Remotion 画布 1280×720 → Task 4
- ✅ 动画节奏规范（GrowFromCenter、Flash、spring）→ Task 3、4
- ✅ 退场检查清单（画布存量、开头清场、run_time=0.5）→ Task 3
- ✅ TDD：先写失败测试 → Task 1

**Placeholder 扫描：** 无 TBD、TODO、省略代码。

**Type consistency：** 无跨任务函数调用，仅字符串常量修改，无类型问题。
