# Prompt 系统重构 & 视频风格多元化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将硬编码在 `chat_provider.py` 中的提示词拆解为可管理的风格组件，支持创建项目时按维度自由组合，并将引擎技术规范迁移到 YAML 文件。

**Architecture:** 新增 `prompt_components` 表存储内容风格维度（叙事风格/节奏/配色/动画/镜头结构），`video_projects` 增加 `style_config` JSONB 字段存储各维度选择。引擎技术规范（Manim/Remotion 代码约束）迁移到 YAML 文件，运行时自动按 render_engine 注入。Workers 在执行任务时从 DB 查出各维度 prompt_text，通过 input_payload 传给 ChatAIProvider。

**Tech Stack:** Python/SQLAlchemy/Alembic（后端），FastAPI，PyYAML，React/TypeScript/TanStack Query（前端）

## Global Constraints

- Python 包管理用 `/Users/peng/.local/bin/uv run`，不用裸 `uv`
- 前端用 `PATH="/Users/peng/.nvm/versions/node/v24.11.0/bin:$PATH" pnpm`
- 不设数据库外键约束，应用层校验
- 现有 Manim/Remotion 规范文本必须完整迁移，不得丢失内容
- 测试运行：`cd backend && /Users/peng/.local/bin/uv run pytest tests/ -v`

---

## File Map

**新建：**
- `backend/app/engines/ai/engine_specs/manim.yaml` — Manim 引擎规范
- `backend/app/engines/ai/engine_specs/remotion.yaml` — Remotion 引擎规范
- `backend/app/models/prompt_component.py` — PromptComponent ORM 模型
- `backend/app/schemas/prompt_component.py` — Pydantic schemas
- `backend/app/api/prompt_components.py` — CRUD 路由
- `backend/alembic/versions/<hash>_add_prompt_components.py` — 迁移（含种子数据）
- `backend/alembic/versions/<hash>_add_style_config_to_projects.py` — 迁移
- `frontend/src/hooks/usePromptComponents.ts` — TanStack Query hooks
- `frontend/src/pages/StyleLibraryPage.tsx` — 风格库管理页

**修改：**
- `backend/app/engines/ai/chat_provider.py` — 从 YAML 加载规范，接受 `style_components` 参数
- `backend/app/models/project.py` — 新增 `style_config` JSONB 字段
- `backend/app/schemas/project.py` — `ProjectCreate` 增加 `style_config`
- `backend/app/api/projects.py` — 创建项目时保存 `style_config`
- `backend/app/workers/narrative_worker.py` — 从 payload 取 style_components 传给 provider
- `backend/app/workers/code_worker.py` — 同上
- `backend/app/workflows/activities.py` — 查 DB 解析 style_config，写入 input_payload
- `backend/app/models/__init__.py` — 导出 PromptComponent
- `backend/app/main.py` — 注册 prompt_components 路由
- `frontend/src/types/index.ts` — 新增 PromptComponent 类型，VideoProject 加 styleConfig
- `frontend/src/hooks/useProjects.ts` — useCreateProject 传 styleConfig
- `frontend/src/components/topics/CreateProjectDialog.tsx` — 风格选择器
- `frontend/src/App.tsx` — 新增 /style-library 路由
- `frontend/src/components/Layout.tsx` — 侧边栏导航新增风格库

---

## Task 1: 引擎规范迁移到 YAML + ChatAIProvider 重构

**Files:**
- Create: `backend/app/engines/ai/engine_specs/manim.yaml`
- Create: `backend/app/engines/ai/engine_specs/remotion.yaml`
- Modify: `backend/app/engines/ai/chat_provider.py`

**Interfaces:**
- Produces: `ChatAIProvider.generate_narrative(... style_components: dict[str, str] = {})` — 新增可选参数
- Produces: `ChatAIProvider.generate_code(... style_components: dict[str, str] = {})` — 新增可选参数
- Produces: `ChatAIProvider.repair_code(... style_components: dict[str, str] = {})` — 新增可选参数

- [ ] **Step 1: 创建 engine_specs 目录并写 manim.yaml**

```bash
mkdir -p backend/app/engines/ai/engine_specs
```

文件 `backend/app/engines/ai/engine_specs/manim.yaml`（将 `chat_provider.py` 中 `_NARRATIVE_ENGINE_HINTS["manim"]` 和 `_ENGINE_CODE_PROMPTS["manim"]` 的文本原样复制）：

```yaml
narrative_hint: |
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
  镜头 2："承接上镜图示。理性青短波分支放大高亮并周围扩散光环（强调动画），其余颜色分支同时淡化至低透明度。右侧错落入场辅助注释文字'蓝光波长最短'。旁白结束后标题和散射主图完成使命退场，保留高亮青色分支作为下镜视觉锚点。"

code_prompt: |
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
     axes.move_to(ORIGIN).shift(RIGHT * 0.5)

  3. y 轴标签天然向左偏移约 1 单位，整体 Axes 须向右平移至少 0.8 单位：
     axes.shift(RIGHT * 0.8)

  4. 轴标签用 font_size=22 以内，创建后检查 label.get_left()[0] ≥ -5.8、label.get_right()[0] ≤ 5.8

  5. 图形绘制范围必须在轴的 x_range/y_range 之内：
     graph = axes.plot(lambda x: 1/x, x_range=[0.1, 9.9])

  6. 如果同一画面有标题或其他元素，Axes 整体缩小或位移，确保与其他元素无重叠且各自在安全区内

  【文字元素防溢出规则】
  - 所有 Text / MathTex 在 .play(Write/FadeIn...) 前必须确认 get_left()[0] ≥ -5.8 且 get_right()[0] ≤ 5.8
  - 长文字必须先 .scale() 到合适大小再定位
  - .to_corner() / .to_edge() 自带 buff=0.5，安全；但 .move_to() / .shift() 到边缘位置时须手动验证不超界

  【禁用类名与替代方案（高频 NameError 根源）】
  - ❌ Polyline → 用 VMobject + set_points_as_corners 或多段 Line 组成 VGroup
  - ❌ GrowArrow → 改用 Create
  - ❌ DashedVMobject(obj) → 改用 DashedVMobject(vmobject, num_dashes=15)
  - ❌ Arc(delta_angle=...) → 改用 Arc(radius=0.6, start_angle=0, angle=PI)
  - ❌ Circle(opacity=0.5) → 改用 fill_opacity/stroke_opacity 参数或 .set_opacity()

  【坐标系规则（重要）】
  - Manim 所有"点"均为三维 (x, y, z)，z 通常为 0
  - 凡是传递坐标/顶点/路径点的地方，一律用 3 元素格式：[x, y, 0]
  - 严禁任何形式的 2D 坐标：[x, y]、np.array([x, y])
  - Axes 构造函数不支持 x_label / y_label 参数；用 axes.get_x_axis_label() / axes.get_y_axis_label()

  【字体大小规范】
  - 主标题：font_size=44
  - 节点标签/图形旁说明：font_size=32
  - 正文内容：font_size=28
  - 小标注：font_size=22
  - 禁止使用不加 font_size 的裸 Text()

  【动画节奏规范（大气感）】
  入场动画：
  - 核心图形：GrowFromCenter；图表类：Create
  - 文字标题：Write；说明性文字：FadeIn
  - 箭头：Create（GrowArrow 在当前版本有 bug，禁止使用）
  - 多元素错落入场：必须用 LaggedStart([...], lag_ratio=0.2)
  - 复杂图示：分三步——先节点，再连线，再标注

  强调动画：
  - Flash、Circumscribe、Indicate 突出关键节点
  - 关键数字/结论：Indicate 后保持高亮颜色

  退场动画：
  - 单个元素：FadeOut(element, run_time=0.5)
  - 多元素同时退场：FadeOut(VGroup(a, b, c), run_time=0.6)

  run_time 选择：
  - 简单入场：0.8s；标准动画：1.2s；关键变换：1.8–2.0s；退场：0.5s

  【文字渲染规则（重要）】
  - 所有中文、日文等非 ASCII 文字必须使用 Text()，禁止使用 MathTex() 或 Tex()
  - MathTex() / Tex() 仅用于纯英文/ASCII 数学公式
  - 违反此规则会导致 LaTeX 编译报错使视频生成失败

  【视觉优先】
  - 除纯标题或总结镜头外，每个镜头至少设计一个承载知识含义的图形动画
  - 画面文字只保留关键词、数字、公式、简短标注，每帧不超过 15 个汉字
  - 每个镜头的图形元素数量控制在 3–6 个
```

- [ ] **Step 2: 创建 remotion.yaml**

文件 `backend/app/engines/ai/engine_specs/remotion.yaml`（将 `_NARRATIVE_ENGINE_HINTS["remotion"]` 和 `_ENGINE_CODE_PROMPTS["remotion"]` 原样复制）：

```yaml
narrative_hint: |
  【Remotion 画面描述规范——弱技术层】
  description 字段只写画面意图，由代码生成阶段翻译为 React/TSX 动画代码。禁止在 description 中出现组件名、hook 名或代码语法。

  【可用图形词汇】
  SVG 图形：圆形（含双圆/光晕圆）、矩形（含圆角矩形容器）、路径、线条、多边形、径向渐变背景光晕
  连接关系：箭头（细/粗）、连线（实线/虚线）、路径生长动画
  文字层：标题、说明文字、数字标注、滚动数字、关键公式（文字描述）
  装饰元素：装饰细线、分隔线、背景辅助网格

  【配色参考】
  认知紫 #6C4FD4、浅紫 #A98EE8；错误红 #FF6B6B、警示橙 #FFB347；理性青 #4ECDC4、结论绿 #44CF6C；直觉粉 #FF9EBB；深炭 #1C1433；背景：淡紫白 #F7F3FF

  【跨镜头衔接说明】
  Remotion 每个 Sequence 是独立作用域。跨镜头持续存在的元素在 description 中注明"作为共享层延续"。

  【内容要求】
  - 除纯标题或总结镜头外，每个镜头至少包含一个承载知识含义的 SVG/CSS 图形动画
  - 先图形讲解，关键公式只在支撑核心结论时出现
  - 每帧文字不超过 15 个汉字
  - 图形元素数量控制在 3–6 个；多元素须描述"错落依次入场"

  【精致度要求】
  - 标题镜头：主标题下方配同色装饰线从中心向两侧伸展
  - 概念节点：建议"双圆节点（外圈半透明光晕+内圈实心）"或"带圆角矩形容器"
  - 连线/路径：描述"从左向右生长延伸"等动态过程
  - 强调结论：描述"弹性放大后回弹"或"周围扩散光环"
  - 数字变化：描述"数字从0滚动到X"而非静态显示

  【示例】
  镜头 0："淡紫白背景。中央主标题文字弹性入场（从下方轻微上移），下方认知紫装饰细线同步从中心向两侧伸展。整体保留至旁白结束。"
  镜头 1："背景和缩小后的标题作为共享层延续至顶部。画面中央 SVG：左侧警示橙双圆节点弹性入场代表太阳，稍后理性青细线从节点右侧向右生长延伸，末端弹性分裂成多条散射路径。图示保留至旁白结束。"

code_prompt: |
  【Remotion 代码规范】

  渲染引擎为每个镜头生成一个具名 React 组件（如 _Scene0、_Scene1），code 字段即该组件的函数体。
  禁止在 code 里写 export、const _SceneN、const VideoScene 等外层定义。

  可直接使用的 API（已由渲染引擎导入，无需 import）：
  AbsoluteFill、Sequence、Audio、staticFile、useCurrentFrame、useVideoConfig、interpolate、interpolateColors、spring

  画布尺寸：1280 × 720 px（16:9），坐标原点在左上角，x 向右，y 向下。
  SVG viewBox 统一使用 "0 0 1280 720"。

  【布局与坐标规范（重要）】
  定位原则——先声明位置常量，再从常量推导所有相关坐标：
  const L_CX = 280, L_CY = 360, BOX_W = 200, BOX_H = 160;
  const R_CX = 1000, R_CY = 360;
  const lineX1 = L_CX + BOX_W / 2;
  const lineX2 = R_CX - BOX_W / 2;

  常用布局参考：
  - 左右两列：左中心 x=320，右中心 x=960
  - 三列均分：x=213、640、1067
  - 上下两区：上中心 y=210，下中心 y=510
  - 全屏居中：cx=640，cy=360
  - 顶部标题栏：y=60，高度 80px；正文区：y=140–680

  【节点与连线对齐规则】
  节点和连线必须共享同一套坐标常量，禁止分别硬编码各自的 x/y。

  【帧与时序规则】
  - useCurrentFrame() 返回当前镜头内的相对帧（从 0 开始）
  - 渲染引擎自动注入 const _sceneDuration = N;（N = estimated_duration_seconds × fps），可直接使用
  - 禁止自行声明 durationInFrames
  - interpolate() 只能插值数字，禁止传入颜色字符串
  - 颜色过渡用 interpolateColors()
  - interpolate() 的 inputRange 必须严格单调递增

  【字体规范】
  - 主标题：fontSize: 56
  - 节点标签/图形说明：fontSize: 36
  - 正文内容：fontSize: 28
  - 小标注：fontSize: 22
  - 禁止使用无 fontSize 的裸 style 文字

  【动画节奏规范（大气感）】
  入场：spring({ frame, fps, config: { stiffness: 70, damping: 14 } }) 驱动 scale + opacity
  多元素错落：每个元素用 Math.max(0, frame - delay) 作为偏移帧，delay 间隔 4–6 帧
  连线/路径生长：interpolate(frame, [0, durationInFrames * 0.6], [0, totalLength]) 驱动 strokeDashoffset
  退场：interpolate(frame, [exitStart, exitStart+10], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })

  【文字渲染规则】
  - 中文使用 style={{ fontFamily: "PingFang SC, Microsoft YaHei, sans-serif" }}
  - 标题文字加 letterSpacing: 2；正文 letterSpacing: 0.5
```

- [ ] **Step 3: 重构 ChatAIProvider 从 YAML 加载规范**

修改 `backend/app/engines/ai/chat_provider.py`：

```python
import json
import re
from collections.abc import AsyncIterator
from pathlib import Path

import yaml

from app.engines.ai.base import (
    BrainstormResult, ChatClient, CodeGenerationResult, CodeRepairResult,
    NarrativeResult, ScriptGenerationResult,
)

_SPECS_DIR = Path(__file__).parent / "engine_specs"


def _load_engine_specs() -> tuple[dict[str, str], dict[str, str]]:
    """Load narrative_hint and code_prompt from engine_specs/*.yaml."""
    narrative_hints: dict[str, str] = {}
    code_prompts: dict[str, str] = {}
    if _SPECS_DIR.exists():
        for yaml_file in _SPECS_DIR.glob("*.yaml"):
            engine_name = yaml_file.stem
            data = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
            if "narrative_hint" in data:
                narrative_hints[engine_name] = data["narrative_hint"]
            if "code_prompt" in data:
                code_prompts[engine_name] = data["code_prompt"]
    return narrative_hints, code_prompts


class ChatAIProvider:
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
    ):
        self.client = client
        self.script_max_tokens = script_max_tokens
        self.json_max_tokens = json_max_tokens
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
        engine_hint = self._narrative_engine_hints.get(render_engine, self._NARRATIVE_ENGINE_HINT_FALLBACK)

        parts = [
            "你是知识视频叙事脚本生成器。请严格输出 JSON object，不要输出 Markdown。",
            "",
            'JSON 格式示例：\n{{\n  "scenes": [\n    {{\n      "scene_index": 0,\n      "narration": "旁白文稿——控制节奏、娓娓道来",\n      "description": "画面描述（明确标注进场/变形/退场/跨镜头衔接）",\n      "estimated_duration_seconds": 8.0\n    }}\n  ],\n  "fact_checks": [\n    {{\n      "claim_text": "需要核查的具体论断",\n      "scene_index": 0,\n      "source_url": null,\n      "source_description": "建议核查来源或说明",\n      "confidence": "medium",\n      "is_hypothesis": false,\n      "assumptions": null,\n      "controversy": null,\n      "reviewer_verdict": null,\n      "reviewer_note": null\n    }}\n  ]\n}}',
            "",
        ]
        if narrative_style:
            parts.append(narrative_style)
        if pacing:
            parts.append(pacing)
        if scene_structure:
            parts.append(scene_structure)
        parts.append(engine_hint)
        parts += [
            "",
            "要求：",
            "- scenes 是镜头数组，scene_index 从 0 连续递增，数量在 15-20 个",
            "- 每个镜头包含 narration、description、estimated_duration_seconds",
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

        content = await self.client.create_chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"请为以下选题生成知识视频叙事脚本 JSON{user_note}：\n"
                    + json.dumps(user_payload, ensure_ascii=False)
                    + context_note,
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
```

- [ ] **Step 4: 确认 pyyaml 已安装**

```bash
cd backend && grep -i yaml pyproject.toml
```

若无，则：`/Users/peng/.local/bin/uv add pyyaml`

- [ ] **Step 5: 运行现有测试确认无回归**

```bash
cd backend && /Users/peng/.local/bin/uv run pytest tests/ -v
```

Expected: 所有测试通过（ChatAIProvider 接口向后兼容，style_components 默认为 None）

- [ ] **Step 6: 提交**

```bash
git add backend/app/engines/ai/engine_specs/ backend/app/engines/ai/chat_provider.py
git commit -m "refactor: extract engine specs to YAML, add style_components param to ChatAIProvider"
```

---

## Task 2: PromptComponent 数据库模型 + Migration + 种子数据

**Files:**
- Create: `backend/app/models/prompt_component.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/<hash>_add_prompt_components.py`（由 alembic 生成后手动填充）

**Interfaces:**
- Produces: `PromptComponent` ORM class，字段：id (UUID), category (str), name (str), description (str|None), prompt_text (str), is_builtin (bool), created_by (str|None), created_at, updated_at

- [ ] **Step 1: 创建 ORM 模型**

文件 `backend/app/models/prompt_component.py`：

```python
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Boolean, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base


def utcnow():
    return datetime.now(timezone.utc)


class PromptComponent(Base):
    __tablename__ = "prompt_components"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    category: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
```

- [ ] **Step 2: 在 `__init__.py` 导出**

修改 `backend/app/models/__init__.py`，添加：

```python
from app.models.prompt_component import PromptComponent  # noqa: F401
```

- [ ] **Step 3: 生成 migration**

```bash
cd backend && /Users/peng/.local/bin/uv run alembic revision --autogenerate -m "add_prompt_components"
```

记下生成的文件路径（如 `alembic/versions/xxxx_add_prompt_components.py`）。

- [ ] **Step 4: 在 migration 的 `upgrade()` 末尾追加种子数据**

打开生成的迁移文件，在 `upgrade()` 函数末尾（`op.create_table(...)` 之后）添加：

```python
    # Seed built-in components
    import uuid as _uuid
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)

    prompt_components_table = sa.table(
        "prompt_components",
        sa.column("id", sa.dialects.postgresql.UUID(as_uuid=True) if hasattr(sa, "dialects") else sa.String),
        sa.column("category", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("prompt_text", sa.Text),
        sa.column("is_builtin", sa.Boolean),
        sa.column("created_by", sa.String),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    seeds = [
        {
            "id": str(_uuid.uuid4()),
            "category": "narrative_style",
            "name": "反差心理学",
            "description": "从反直觉现象切入，揭示认知偏差，适合心理学/行为经济学类内容",
            "prompt_text": "【叙事风格：反差心理学】\n整体娓娓道来，从一个反直觉的问题或现象切入，引发认知冲突，逐步揭示背后的心理机制，结尾给出可操作的认知纠偏方法。\n旁白负责讲解，每句话清晰有力，不空洞，不重复画面文字。\n语气：平静而充满反思感，像一位向朋友分享洞见的智者。",
            "is_builtin": True,
            "created_by": None,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": str(_uuid.uuid4()),
            "category": "narrative_style",
            "name": "科普解说",
            "description": "客观严谨地解释科学原理，适合物理/化学/生物/天文类内容",
            "prompt_text": "【叙事风格：科普解说】\n以准确、通俗的语言解释科学原理。从日常现象出发，逐层深入到核心机制，通过类比和图示让复杂概念变得易懂。\n旁白语气：专业而不失亲切，像一位热情的科学老师。\n避免过度简化或歪曲事实，关键数据和结论须有据可查。",
            "is_builtin": True,
            "created_by": None,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": str(_uuid.uuid4()),
            "category": "narrative_style",
            "name": "故事叙事",
            "description": "以具体人物或事件为主线，通过叙事推进知识传递",
            "prompt_text": "【叙事风格：故事叙事】\n以一个具体的人物、事件或历史片段为切入点，通过叙事推进知识传递。\n旁白语气：有画面感和代入感，像讲故事而非授课。\n在故事发展过程中自然揭示知识点，结尾点明故事的启示或意义。",
            "is_builtin": True,
            "created_by": None,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": str(_uuid.uuid4()),
            "category": "pacing",
            "name": "标准节奏（2-3分钟）",
            "description": "15-20个镜头，每镜头30-50字旁白，适合大多数知识视频",
            "prompt_text": "【叙事节奏：标准】\n目标视频时长 2-3 分钟，需要 15-20 个镜头，每个镜头旁白约 30-50 字、时长 7-10 秒。\nestimated_duration_seconds 根据旁白字数和画面复杂度估算，不得少于 5 秒。\n先用直观图形和动态关系解释概念，再在确有必要时引入关键公式；公式服务于理解，不追求数量。",
            "is_builtin": True,
            "created_by": None,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": str(_uuid.uuid4()),
            "category": "pacing",
            "name": "快节奏（1分钟）",
            "description": "8-12个镜头，每镜头20-30字旁白，适合短视频/竖屏格式",
            "prompt_text": "【叙事节奏：快节奏】\n目标视频时长约 1 分钟，需要 8-12 个镜头，每个镜头旁白约 20-30 字、时长 4-6 秒。\nestimated_duration_seconds 不得少于 3 秒。\n精简内容，只保留最核心的一个知识点，去掉所有铺垫和延伸。开头直接切入结论，结尾一句话总结。",
            "is_builtin": True,
            "created_by": None,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": str(_uuid.uuid4()),
            "category": "scene_structure",
            "name": "问题-分析-结论",
            "description": "标准知识视频三段式结构",
            "prompt_text": "【镜头结构：问题-分析-结论】\n镜头 0-1：抛出问题或反直觉现象，引发好奇\n镜头 2-4：拆解问题，建立分析框架\n镜头 5-12：逐步展开分析，以图示和实例论证\n镜头 13-15+：给出结论和实际启示",
            "is_builtin": True,
            "created_by": None,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": str(_uuid.uuid4()),
            "category": "color_scheme",
            "name": "亮底紫色系（默认）",
            "description": "淡紫白背景 + 认知紫主色，适合心理学/思维类内容",
            "prompt_text": "【配色系统：亮底紫色系】\n背景主色（亮底）：#F7F3FF\n亮底上的文字：#1C1433；辅助注释：#8E7DC0\n核心概念色：认知紫 #6C4FD4、浅紫 #A98EE8\n语义强调：错误红 #FF6B6B、警示橙 #FFB347、理性青 #4ECDC4、结论绿 #44CF6C、直觉粉 #FF9EBB\n结构辅助：网格深底 #4A3880、网格亮底 #D4C5F0\n配色原则：红色专用于偏差/错误，绿色专用于正确/结论，不可混用。以亮底 #F7F3FF 为主场景，主色饱和度高，确保手机小尺寸下清晰可辨。",
            "is_builtin": True,
            "created_by": None,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": str(_uuid.uuid4()),
            "category": "color_scheme",
            "name": "暗底深蓝系",
            "description": "深色背景 + 科技蓝主色，适合科技/宇宙类内容",
            "prompt_text": "【配色系统：暗底深蓝系】\n背景主色（深底）：#0D1117\n深底上的文字：#E6EDF3；辅助注释：#8B949E\n核心概念色：科技蓝 #58A6FF、浅蓝 #79C0FF\n语义强调：错误红 #F85149、警示橙 #E3B341、成功绿 #3FB950、高亮青 #39D0E0\n结构辅助：网格线 #21262D\n配色原则：以深底 #0D1117 为主场景，配色模拟太空/科技感，避免过亮色块破坏沉浸感。",
            "is_builtin": True,
            "created_by": None,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": str(_uuid.uuid4()),
            "category": "animation_style",
            "name": "弹性大气感（默认）",
            "description": "弹簧动画+半透明光晕，精致细腻，适合科普和心理类视频",
            "prompt_text": "【视觉精致度规范：弹性大气感】\n构图与层次：每个镜头须有明确的视觉层次——背景装饰层 → 主体图形层 → 文字标注层，三层分离。\n图形之间保持充足间距（≥ 1.5 单位），避免拥挤感。\n半透明背景光晕：在主体元素后方放置 fill_opacity=0.12 的同色系大圆作衬底，提升视觉厚度。\n精致细节：标题镜头主标题下方配细分隔线；关键概念节点使用双圆结构（外圈半透明+内圈实心）。\n多元素用 LaggedStart 错落入场（lag_ratio=0.2），节点+连线+标注分三步出现，避免同帧全部出现。\n数字或百分比变化用 DecimalNumber 动态滚动，不要静态文字。",
            "is_builtin": True,
            "created_by": None,
            "created_at": now,
            "updated_at": now,
        },
        {
            "id": str(_uuid.uuid4()),
            "category": "animation_style",
            "name": "简洁干净",
            "description": "最小化装饰，内容优先，适合教学和工具类视频",
            "prompt_text": "【视觉精致度规范：简洁干净】\n构图：简洁为主，每帧只保留与当前叙事直接相关的元素，不加装饰光晕或背景纹理。\n元素之间保持充足间距（≥ 1.5 单位），避免拥挤感。\n图形优先线条和基本几何形状，不追求精致光效。\n动画：入场用简单 FadeIn 或 Create，不使用弹性动画；强调用 Indicate，不用 Flash 等华丽特效。\n整体视觉服务于内容清晰传达，不为视觉精致而增加复杂度。",
            "is_builtin": True,
            "created_by": None,
            "created_at": now,
            "updated_at": now,
        },
    ]

    op.bulk_insert(prompt_components_table, seeds)
```

**注意**：migration 文件顶部需要 `import sqlalchemy as sa`（alembic 自动生成时已有）。

- [ ] **Step 5: 运行 migration**

```bash
cd backend && /Users/peng/.local/bin/uv run alembic upgrade head
```

Expected: migration 成功，无报错

- [ ] **Step 6: 验证种子数据**

```bash
cd backend && /Users/peng/.local/bin/uv run python -c "
from app.db import get_sync_session_raw
from app.models.prompt_component import PromptComponent
db = get_sync_session_raw()
count = db.query(PromptComponent).count()
print(f'prompt_components count: {count}')
db.close()
"
```

Expected: `prompt_components count: 10`

- [ ] **Step 7: 提交**

```bash
git add backend/app/models/prompt_component.py backend/app/models/__init__.py backend/alembic/versions/
git commit -m "feat: add PromptComponent model and seed built-in style components"
```

---

## Task 3: VideoProject 增加 style_config + Migration

**Files:**
- Modify: `backend/app/models/project.py`
- Create: `backend/alembic/versions/<hash>_add_style_config_to_projects.py`

**Interfaces:**
- Produces: `VideoProject.style_config: dict` — JSONB，默认 `{}`，结构 `{category: component_id_str}`

- [ ] **Step 1: 在 VideoProject 添加字段**

在 `backend/app/models/project.py` 的 `narrative_context` 字段之后添加：

```python
    style_config: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
```

- [ ] **Step 2: 生成 migration**

```bash
cd backend && /Users/peng/.local/bin/uv run alembic revision --autogenerate -m "add_style_config_to_projects"
```

- [ ] **Step 3: 运行 migration**

```bash
cd backend && /Users/peng/.local/bin/uv run alembic upgrade head
```

Expected: 无报错

- [ ] **Step 4: 提交**

```bash
git add backend/app/models/project.py backend/alembic/versions/
git commit -m "feat: add style_config JSONB field to video_projects"
```

---

## Task 4: PromptComponent API 路由 + Schemas

**Files:**
- Create: `backend/app/schemas/prompt_component.py`
- Create: `backend/app/api/prompt_components.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/schemas/__init__.py`

**Interfaces:**
- Produces: `GET /api/prompt-components?category=xxx` → `PromptComponentListResponse`
- Produces: `POST /api/prompt-components` → `PromptComponentResponse`
- Produces: `PUT /api/prompt-components/{id}` → `PromptComponentResponse`（内置组件返回 403）
- Produces: `DELETE /api/prompt-components/{id}` → 204（内置组件返回 403）
- Produces: `POST /api/prompt-components/{id}/duplicate` → `PromptComponentResponse`

- [ ] **Step 1: 创建 schemas**

文件 `backend/app/schemas/prompt_component.py`：

```python
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from typing import Optional
from datetime import datetime
from uuid import UUID


class PromptComponentBase(BaseModel):
    category: str
    name: str
    description: Optional[str] = None
    prompt_text: str


class PromptComponentCreate(PromptComponentBase):
    pass


class PromptComponentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    prompt_text: Optional[str] = None


class PromptComponentResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    id: UUID
    category: str
    name: str
    description: Optional[str]
    prompt_text: str
    is_builtin: bool
    created_by: Optional[str]
    created_at: datetime
    updated_at: datetime


class PromptComponentListResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    items: list[PromptComponentResponse]
    total: int
```

- [ ] **Step 2: 创建 API 路由**

文件 `backend/app/api/prompt_components.py`：

```python
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth import verify_api_key
from app.db import get_async_session
from app.models.prompt_component import PromptComponent
from app.schemas.prompt_component import (
    PromptComponentCreate, PromptComponentUpdate,
    PromptComponentResponse, PromptComponentListResponse,
)

router = APIRouter(prefix="/api/prompt-components", tags=["prompt-components"])


def _to_response(pc: PromptComponent) -> PromptComponentResponse:
    return PromptComponentResponse(
        id=pc.id,
        category=pc.category,
        name=pc.name,
        description=pc.description,
        prompt_text=pc.prompt_text,
        is_builtin=pc.is_builtin,
        created_by=pc.created_by,
        created_at=pc.created_at,
        updated_at=pc.updated_at,
    )


@router.get("", response_model=PromptComponentListResponse)
async def list_prompt_components(
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_api_key),
):
    stmt = select(PromptComponent).order_by(PromptComponent.is_builtin.desc(), PromptComponent.name)
    if category:
        stmt = stmt.where(PromptComponent.category == category)
    result = await db.execute(stmt)
    items = result.scalars().all()
    return PromptComponentListResponse(items=[_to_response(pc) for pc in items], total=len(items))


@router.post("", response_model=PromptComponentResponse, status_code=201)
async def create_prompt_component(
    body: PromptComponentCreate,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_api_key),
):
    pc = PromptComponent(
        id=uuid.uuid4(),
        category=body.category,
        name=body.name,
        description=body.description,
        prompt_text=body.prompt_text,
        is_builtin=False,
    )
    db.add(pc)
    await db.commit()
    await db.refresh(pc)
    return _to_response(pc)


@router.put("/{component_id}", response_model=PromptComponentResponse)
async def update_prompt_component(
    component_id: uuid.UUID,
    body: PromptComponentUpdate,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_api_key),
):
    pc = await db.get(PromptComponent, component_id)
    if pc is None:
        raise HTTPException(status_code=404, detail="Component not found")
    if pc.is_builtin:
        raise HTTPException(status_code=403, detail="Cannot modify built-in components")
    if body.name is not None:
        pc.name = body.name
    if body.description is not None:
        pc.description = body.description
    if body.prompt_text is not None:
        pc.prompt_text = body.prompt_text
    await db.commit()
    await db.refresh(pc)
    return _to_response(pc)


@router.delete("/{component_id}", status_code=204)
async def delete_prompt_component(
    component_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_api_key),
):
    pc = await db.get(PromptComponent, component_id)
    if pc is None:
        raise HTTPException(status_code=404, detail="Component not found")
    if pc.is_builtin:
        raise HTTPException(status_code=403, detail="Cannot delete built-in components")
    await db.delete(pc)
    await db.commit()


@router.post("/{component_id}/duplicate", response_model=PromptComponentResponse, status_code=201)
async def duplicate_prompt_component(
    component_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_api_key),
):
    pc = await db.get(PromptComponent, component_id)
    if pc is None:
        raise HTTPException(status_code=404, detail="Component not found")
    new_pc = PromptComponent(
        id=uuid.uuid4(),
        category=pc.category,
        name=f"{pc.name}（副本）",
        description=pc.description,
        prompt_text=pc.prompt_text,
        is_builtin=False,
    )
    db.add(new_pc)
    await db.commit()
    await db.refresh(new_pc)
    return _to_response(new_pc)
```

- [ ] **Step 3: 注册路由到 main.py**

在 `backend/app/main.py` 中找到其他 router 的 include 位置，添加：

```python
from app.api.prompt_components import router as prompt_components_router
app.include_router(prompt_components_router)
```

- [ ] **Step 4: 手动测试 API**

启动后端后：

```bash
curl -s -H "X-API-Key: $API_KEY" http://localhost:8000/api/prompt-components | python3 -m json.tool | head -30
```

Expected: 返回包含 10 个内置组件的 JSON

- [ ] **Step 5: 提交**

```bash
git add backend/app/schemas/prompt_component.py backend/app/api/prompt_components.py backend/app/main.py
git commit -m "feat: add prompt_components CRUD API"
```

---

## Task 5: Workers 和 Activities 传递 style_components

**Files:**
- Modify: `backend/app/workflows/activities.py`
- Modify: `backend/app/workers/narrative_worker.py`
- Modify: `backend/app/workers/code_worker.py`
- Modify: `backend/app/schemas/project.py`
- Modify: `backend/app/api/projects.py`

**Interfaces:**
- Consumes: `PromptComponent` model（Task 2）
- Consumes: `VideoProject.style_config` dict（Task 3）
- Consumes: `ChatAIProvider.generate_narrative(style_components=...)` （Task 1）
- Consumes: `ChatAIProvider.generate_code(style_components=...)` （Task 1）

- [ ] **Step 1: 更新 `submit_narrative_task` activity**

在 `backend/app/workflows/activities.py` 中，在现有 import 区添加：

```python
from app.models.prompt_component import PromptComponent
```

修改 `submit_narrative_task` 函数，在 `task = WorkerTask(...)` 之前添加 style_components 查询：

```python
        # Resolve style_config to prompt texts
        style_config = project.style_config or {}
        style_components: dict[str, str] = {}
        for category, component_id in style_config.items():
            try:
                comp_uuid = uuid.UUID(str(component_id))
                comp = db.get(PromptComponent, comp_uuid)
                if comp:
                    style_components[category] = comp.prompt_text
            except (ValueError, TypeError):
                pass
```

然后在 `input_payload` 中添加 `"style_components": style_components`：

```python
        task = WorkerTask(
            project_id=project.id,
            task_type="generate_narrative",
            engine=project.render_engine,
            status="pending",
            input_payload={
                "topic_title": topic.title if topic else "",
                "topic_description": topic.description if topic else "",
                "render_engine": project.render_engine,
                "rejection_context": rejection_context,
                "narrative_context": project.narrative_context or [],
                "style_components": style_components,
            },
            temporal_workflow_id=f"video-production-{project_id}",
            signal_name="narrative_generated",
            max_retries=3,
        )
```

- [ ] **Step 2: 更新 `submit_code_task` activity**

同样在 `submit_code_task` 中，在 `task = WorkerTask(...)` 之前添加相同的 style_components 查询逻辑，并在 `input_payload` 中添加 `"style_components": style_components`：

```python
        style_config = project.style_config or {}
        style_components: dict[str, str] = {}
        for category, component_id in style_config.items():
            try:
                comp_uuid = uuid.UUID(str(component_id))
                comp = db.get(PromptComponent, comp_uuid)
                if comp:
                    style_components[category] = comp.prompt_text
            except (ValueError, TypeError):
                pass

        task = WorkerTask(
            project_id=project.id,
            task_type="generate_code",
            engine=project.render_engine,
            status="pending",
            input_payload={
                "render_engine": project.render_engine,
                "style_components": style_components,
            },
            temporal_workflow_id=f"video-production-{project_id}",
            signal_name="code_generated",
            max_retries=3,
        )
```

- [ ] **Step 3: 更新 NarrativeWorker**

在 `backend/app/workers/narrative_worker.py` 的 `_execute` 方法中，从 payload 取出 style_components：

```python
        style_components: dict[str, str] = payload.get("style_components") or {}
```

然后传给 provider：

```python
        result = await provider.generate_narrative(
            topic_title=topic_title,
            topic_description=topic_description,
            render_engine=render_engine,
            rejection_context=rejection_context,
            narrative_context=narrative_context,
            style_components=style_components,
        )
```

- [ ] **Step 4: 更新 CodeWorker**

在 `backend/app/workers/code_worker.py` 的 `_execute` 方法中，从 payload 取出 style_components：

```python
        style_components: dict[str, str] = payload.get("style_components") or {}
```

然后传给 provider（找到 `result = await provider.generate_code(...)` 这行）：

```python
            result = await provider.generate_code(
                scenes=scenes,
                render_engine=render_engine,
                style_components=style_components,
            )
```

- [ ] **Step 5: 更新 ProjectCreate schema**

在 `backend/app/schemas/project.py` 的 `ProjectCreate` 中添加 `style_config`：

```python
class ProjectCreate(BaseModel):
    topic_id: UUID
    render_engine: str
    tts_voice: str
    aspect_ratio: str
    narrative_context: list[dict] = []
    style_config: dict = {}
```

- [ ] **Step 6: 更新 projects API 的创建端点**

在 `backend/app/api/projects.py` 中找到 `POST /api/projects` 端点，在创建 `VideoProject` 时加上 `style_config=body.style_config`：

```python
    project = VideoProject(
        topic_id=body.topic_id,
        status="draft",
        render_engine=body.render_engine,
        tts_voice=body.tts_voice,
        aspect_ratio=body.aspect_ratio,
        narrative_context=body.narrative_context,
        style_config=body.style_config,
    )
```

- [ ] **Step 7: 运行测试**

```bash
cd backend && /Users/peng/.local/bin/uv run pytest tests/ -v
```

Expected: 所有测试通过

- [ ] **Step 8: 提交**

```bash
git add backend/app/workflows/activities.py backend/app/workers/narrative_worker.py backend/app/workers/code_worker.py backend/app/schemas/project.py backend/app/api/projects.py
git commit -m "feat: pass style_components through activities and workers to AI provider"
```

---

## Task 6: 前端 TS 类型 + usePromptComponents Hook

**Files:**
- Modify: `frontend/src/types/index.ts`
- Create: `frontend/src/hooks/usePromptComponents.ts`
- Modify: `frontend/src/hooks/useProjects.ts`

**Interfaces:**
- Produces: `PromptComponent` TypeScript interface
- Produces: `usePromptComponents(category?: string)` hook
- Produces: `useCreatePromptComponent()`, `useUpdatePromptComponent()`, `useDeletePromptComponent()`, `useDuplicatePromptComponent()` hooks
- Produces: `useCreateProject()` mutation 接受 `styleConfig?: Record<string, string>` 参数

- [ ] **Step 1: 在 types/index.ts 添加类型**

在 `frontend/src/types/index.ts` 中 `// ═══ 视频项目 ═══` 之前添加：

```typescript
// ═══ 风格组件 ═══
export interface PromptComponent {
  id: string;
  category: string;
  name: string;
  description: string | null;
  promptText: string;
  isBuiltin: boolean;
  createdBy: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface PromptComponentListResponse {
  items: PromptComponent[];
  total: number;
}
```

在 `VideoProject` interface 中添加（找到 `narrativeContext` 字段之后）：

```typescript
  styleConfig: Record<string, string>;
```

- [ ] **Step 2: 创建 usePromptComponents.ts**

文件 `frontend/src/hooks/usePromptComponents.ts`：

```typescript
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { PromptComponent, PromptComponentListResponse } from "@/types";

export function usePromptComponents(category?: string) {
  return useQuery<PromptComponentListResponse>({
    queryKey: ["prompt-components", category],
    queryFn: () =>
      api.get<PromptComponentListResponse>(
        `/api/prompt-components${category ? `?category=${category}` : ""}`
      ),
  });
}

export function useCreatePromptComponent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { category: string; name: string; description?: string; promptText: string }) =>
      api.post<PromptComponent>("/api/prompt-components", {
        category: data.category,
        name: data.name,
        description: data.description,
        prompt_text: data.promptText,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["prompt-components"] });
    },
  });
}

export function useUpdatePromptComponent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...data }: { id: string; name?: string; description?: string; promptText?: string }) =>
      api.put<PromptComponent>(`/api/prompt-components/${id}`, {
        name: data.name,
        description: data.description,
        prompt_text: data.promptText,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["prompt-components"] });
    },
  });
}

export function useDeletePromptComponent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete(`/api/prompt-components/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["prompt-components"] });
    },
  });
}

export function useDuplicatePromptComponent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      api.post<PromptComponent>(`/api/prompt-components/${id}/duplicate`, {}),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["prompt-components"] });
    },
  });
}
```

- [ ] **Step 3: 更新 useCreateProject 接受 styleConfig**

在 `frontend/src/hooks/useProjects.ts` 的 `useCreateProject` mutation 中，在 `mutationFn` 参数类型里添加 `styleConfig?: Record<string, string>`，并在请求体中添加 `style_config: data.styleConfig ?? {}`：

```typescript
export function useCreateProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      topicId: string;
      renderEngine: string;
      ttsVoice: string;
      aspectRatio: string;
      narrativeContext: { text: string }[];
      styleConfig?: Record<string, string>;
    }) =>
      api.post<VideoProject>("/api/projects", {
        topic_id: data.topicId,
        render_engine: data.renderEngine,
        tts_voice: data.ttsVoice,
        aspect_ratio: data.aspectRatio,
        narrative_context: data.narrativeContext,
        style_config: data.styleConfig ?? {},
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["projects"] });
      qc.invalidateQueries({ queryKey: ["topics"] });
    },
  });
}
```

- [ ] **Step 4: 构建检查**

```bash
cd frontend && PATH="/Users/peng/.nvm/versions/node/v24.11.0/bin:$PATH" pnpm build 2>&1 | tail -20
```

Expected: build 成功，无 TypeScript 错误

- [ ] **Step 5: 提交**

```bash
git add frontend/src/types/index.ts frontend/src/hooks/usePromptComponents.ts frontend/src/hooks/useProjects.ts
git commit -m "feat: add PromptComponent types and hooks"
```

---

## Task 7: CreateProjectDialog 增加风格选择器

**Files:**
- Modify: `frontend/src/components/topics/CreateProjectDialog.tsx`

**Interfaces:**
- Consumes: `usePromptComponents(category)` hook（Task 6）
- Consumes: `useCreateProject()` with `styleConfig` param（Task 6）

- [ ] **Step 1: 更新 CreateProjectDialog**

完整替换 `frontend/src/components/topics/CreateProjectDialog.tsx`：

```tsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { useCreateProject } from "@/hooks/useProjects";
import { usePromptComponents } from "@/hooks/usePromptComponents";
import type { Topic } from "@/types";

interface Props {
  topic: Topic;
  open: boolean;
  onClose: () => void;
  onCreated?: () => void;
  contextSnippets?: string[];
}

const STYLE_CATEGORIES = [
  { key: "narrative_style", label: "叙事风格" },
  { key: "pacing", label: "叙事节奏" },
  { key: "scene_structure", label: "镜头结构" },
  { key: "color_scheme", label: "配色系统" },
  { key: "animation_style", label: "动画风格" },
] as const;

function StyleSelect({
  category,
  label,
  value,
  onChange,
}: {
  category: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  const { data } = usePromptComponents(category);
  const items = data?.items ?? [];

  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger>
          <SelectValue placeholder="系统默认" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="">系统默认</SelectItem>
          {items.map((item) => (
            <SelectItem key={item.id} value={item.id}>
              <span>{item.name}</span>
              {item.isBuiltin && (
                <span className="ml-1 text-xs text-muted-foreground">内置</span>
              )}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {value && items.find((i) => i.id === value)?.description && (
        <p className="text-xs text-muted-foreground">
          {items.find((i) => i.id === value)?.description}
        </p>
      )}
    </div>
  );
}

export function CreateProjectDialog({ topic, open, onClose, onCreated, contextSnippets = [] }: Props) {
  const [renderEngine, setRenderEngine] = useState("manim");
  const [ttsVoice, setTtsVoice] = useState("zizi");
  const [aspectRatio, setAspectRatio] = useState("landscape");
  const [styleConfig, setStyleConfig] = useState<Record<string, string>>({});
  const [selectedSnippets, setSelectedSnippets] = useState<Set<number>>(
    () => new Set(contextSnippets.map((_, i) => i))
  );
  const createProject = useCreateProject();
  const navigate = useNavigate();

  function toggleSnippet(i: number) {
    setSelectedSnippets((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
  }

  function setStyleCategory(category: string, value: string) {
    setStyleConfig((prev) => {
      if (!value) {
        const next = { ...prev };
        delete next[category];
        return next;
      }
      return { ...prev, [category]: value };
    });
  }

  const handleSubmit = () => {
    const narrativeContext = contextSnippets
      .filter((_, i) => selectedSnippets.has(i))
      .map((text) => ({ text }));
    createProject.mutate(
      { topicId: topic.id, renderEngine, ttsVoice, aspectRatio, narrativeContext, styleConfig },
      {
        onSuccess: (_project) => {
          onCreated?.();
          onClose();
          navigate("/projects");
        },
      }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>从选题创建项目</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div className="rounded-md bg-muted px-3 py-2 text-sm text-muted-foreground">
            {topic.title}
          </div>

          {/* 基础配置 */}
          <div className="space-y-1.5">
            <Label>渲染引擎</Label>
            <Select value={renderEngine} onValueChange={(v) => v && setRenderEngine(v)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="manim">Manim</SelectItem>
                <SelectItem value="remotion">Remotion</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>TTS 音色</Label>
            <Select value={ttsVoice} onValueChange={(v) => v && setTtsVoice(v)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="zizi">zizi</SelectItem>
                <SelectItem value="echo">Echo</SelectItem>
                <SelectItem value="fable">Fable</SelectItem>
                <SelectItem value="onyx">Onyx</SelectItem>
                <SelectItem value="nova">Nova</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>画幅比例</Label>
            <Select value={aspectRatio} onValueChange={(v) => v && setAspectRatio(v)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="landscape">横屏 16:9</SelectItem>
                <SelectItem value="portrait">竖屏 9:16</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* 风格配置 */}
          <div className="space-y-3 pt-1">
            <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              视频风格
            </Label>
            {STYLE_CATEGORIES.map(({ key, label }) => (
              <StyleSelect
                key={key}
                category={key}
                label={label}
                value={styleConfig[key] ?? ""}
                onChange={(v) => setStyleCategory(key, v)}
              />
            ))}
          </div>

          {/* 研究上下文 */}
          {contextSnippets.length > 0 && (
            <div className="space-y-2">
              <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                研究上下文（选择带入叙事生成）
              </Label>
              <div className="space-y-1.5 max-h-40 overflow-y-auto">
                {contextSnippets.map((snippet, i) => (
                  <div key={i} className="flex items-start gap-2">
                    <Checkbox
                      id={`snippet-${i}`}
                      checked={selectedSnippets.has(i)}
                      onCheckedChange={() => toggleSnippet(i)}
                      className="mt-0.5 shrink-0"
                    />
                    <label
                      htmlFor={`snippet-${i}`}
                      className="text-xs text-muted-foreground line-clamp-2 cursor-pointer"
                    >
                      {snippet}
                    </label>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>取消</Button>
          <Button onClick={handleSubmit} disabled={createProject.isPending}>
            {createProject.isPending ? "创建中..." : "创建项目"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 2: 构建检查**

```bash
cd frontend && PATH="/Users/peng/.nvm/versions/node/v24.11.0/bin:$PATH" pnpm build 2>&1 | tail -20
```

Expected: 无 TypeScript 错误

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/topics/CreateProjectDialog.tsx
git commit -m "feat: add style dimension selectors to CreateProjectDialog"
```

---

## Task 8: 风格库管理页 + 路由

**Files:**
- Create: `frontend/src/pages/StyleLibraryPage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/Layout.tsx`

**Interfaces:**
- Consumes: `usePromptComponents`, `useCreatePromptComponent`, `useUpdatePromptComponent`, `useDeletePromptComponent`, `useDuplicatePromptComponent`（Task 6）

- [ ] **Step 1: 创建 StyleLibraryPage**

文件 `frontend/src/pages/StyleLibraryPage.tsx`：

```tsx
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import {
  usePromptComponents,
  useCreatePromptComponent,
  useUpdatePromptComponent,
  useDeletePromptComponent,
  useDuplicatePromptComponent,
} from "@/hooks/usePromptComponents";
import type { PromptComponent } from "@/types";

const CATEGORIES = [
  { key: "narrative_style", label: "叙事风格" },
  { key: "pacing", label: "叙事节奏" },
  { key: "scene_structure", label: "镜头结构" },
  { key: "color_scheme", label: "配色系统" },
  { key: "animation_style", label: "动画风格" },
] as const;

interface ComponentFormData {
  name: string;
  description: string;
  promptText: string;
}

function ComponentCard({
  component,
  onEdit,
}: {
  component: PromptComponent;
  onEdit: (c: PromptComponent) => void;
}) {
  const deleteComp = useDeletePromptComponent();
  const duplicateComp = useDuplicatePromptComponent();

  return (
    <Card className="flex flex-col">
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-sm font-medium">{component.name}</CardTitle>
          {component.isBuiltin && (
            <span className="text-xs text-muted-foreground bg-muted px-1.5 py-0.5 rounded shrink-0">内置</span>
          )}
        </div>
        {component.description && (
          <CardDescription className="text-xs">{component.description}</CardDescription>
        )}
      </CardHeader>
      <CardContent className="flex-1 pb-2">
        <pre className="text-xs text-muted-foreground bg-muted rounded p-2 max-h-24 overflow-y-auto whitespace-pre-wrap font-mono">
          {component.promptText.slice(0, 200)}{component.promptText.length > 200 ? "…" : ""}
        </pre>
      </CardContent>
      <CardFooter className="gap-2 pt-2">
        {component.isBuiltin ? (
          <Button
            size="sm"
            variant="outline"
            className="flex-1"
            onClick={() => duplicateComp.mutate(component.id)}
            disabled={duplicateComp.isPending}
          >
            复制为自定义
          </Button>
        ) : (
          <>
            <Button size="sm" variant="outline" className="flex-1" onClick={() => onEdit(component)}>
              编辑
            </Button>
            <Button
              size="sm"
              variant="destructive"
              onClick={() => {
                if (confirm(`确认删除「${component.name}」？`)) {
                  deleteComp.mutate(component.id);
                }
              }}
              disabled={deleteComp.isPending}
            >
              删除
            </Button>
          </>
        )}
      </CardFooter>
    </Card>
  );
}

function ComponentFormDialog({
  open,
  onClose,
  category,
  editing,
}: {
  open: boolean;
  onClose: () => void;
  category: string;
  editing: PromptComponent | null;
}) {
  const [form, setForm] = useState<ComponentFormData>({
    name: editing?.name ?? "",
    description: editing?.description ?? "",
    promptText: editing?.promptText ?? "",
  });
  const createComp = useCreatePromptComponent();
  const updateComp = useUpdatePromptComponent();

  const handleSubmit = () => {
    if (!form.name.trim() || !form.promptText.trim()) return;
    if (editing) {
      updateComp.mutate(
        { id: editing.id, name: form.name, description: form.description, promptText: form.promptText },
        { onSuccess: onClose }
      );
    } else {
      createComp.mutate(
        { category, name: form.name, description: form.description, promptText: form.promptText },
        { onSuccess: onClose }
      );
    }
  };

  const isPending = createComp.isPending || updateComp.isPending;

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{editing ? "编辑组件" : "新建组件"}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div className="space-y-1.5">
            <Label>名称</Label>
            <Input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
          </div>
          <div className="space-y-1.5">
            <Label>说明（可选）</Label>
            <Input
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
            />
          </div>
          <div className="space-y-1.5">
            <Label>提示词内容</Label>
            <Textarea
              value={form.promptText}
              onChange={(e) => setForm((f) => ({ ...f, promptText: e.target.value }))}
              rows={10}
              className="font-mono text-xs"
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>取消</Button>
          <Button onClick={handleSubmit} disabled={isPending || !form.name.trim() || !form.promptText.trim()}>
            {isPending ? "保存中…" : "保存"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function StyleLibraryPage() {
  const [activeCategory, setActiveCategory] = useState(CATEGORIES[0].key as string);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<PromptComponent | null>(null);
  const { data, isLoading } = usePromptComponents(activeCategory);
  const items = data?.items ?? [];

  const openCreate = () => { setEditing(null); setDialogOpen(true); };
  const openEdit = (c: PromptComponent) => { setEditing(c); setDialogOpen(true); };

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">风格库</h1>
        <Button onClick={openCreate}>新建组件</Button>
      </div>

      {/* Category tabs */}
      <div className="flex gap-2 flex-wrap">
        {CATEGORIES.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setActiveCategory(key)}
            className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors ${
              activeCategory === key
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground hover:bg-muted/80"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Component cards */}
      {isLoading ? (
        <p className="text-sm text-muted-foreground">加载中…</p>
      ) : items.length === 0 ? (
        <p className="text-sm text-muted-foreground">暂无组件，点击「新建组件」创建</p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map((item) => (
            <ComponentCard key={item.id} component={item} onEdit={openEdit} />
          ))}
        </div>
      )}

      <ComponentFormDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        category={activeCategory}
        editing={editing}
      />
    </div>
  );
}
```

- [ ] **Step 2: 添加路由**

在 `frontend/src/App.tsx` 中找到路由定义区域，添加：

```tsx
import { StyleLibraryPage } from "@/pages/StyleLibraryPage";
// ...在 <Routes> 内添加:
<Route path="/style-library" element={<StyleLibraryPage />} />
```

- [ ] **Step 3: 在 Layout 添加导航入口**

在 `frontend/src/components/Layout.tsx` 中，找到侧边栏导航链接列表，添加风格库链接（与 Projects、Topics 同级）：

```tsx
<NavLink to="/style-library">风格库</NavLink>
```

（具体实现参考文件中现有 NavLink 的写法）

- [ ] **Step 4: 构建检查**

```bash
cd frontend && PATH="/Users/peng/.nvm/versions/node/v24.11.0/bin:$PATH" pnpm build 2>&1 | tail -20
```

Expected: 无错误

- [ ] **Step 5: 提交**

```bash
git add frontend/src/pages/StyleLibraryPage.tsx frontend/src/App.tsx frontend/src/components/Layout.tsx
git commit -m "feat: add style library management page with CRUD"
```

---

## 自检：Spec 覆盖对照

| Spec 要求 | 实现位置 |
|---|---|
| prompt_components 表 | Task 2 |
| category 字段区分维度 | Task 2 Step 1 |
| is_builtin 区分内置/用户 | Task 2 Step 1 |
| video_projects.style_config JSONB | Task 3 |
| 引擎规范迁移到 YAML | Task 1 Step 1-2 |
| ChatAIProvider 从 YAML 加载 | Task 1 Step 3 |
| style_components 参数传入 generate_narrative | Task 1 Step 3, Task 5 Step 3 |
| style_components 参数传入 generate_code | Task 1 Step 3, Task 5 Step 4 |
| GET/POST/PUT/DELETE /api/prompt-components | Task 4 |
| POST /api/prompt-components/{id}/duplicate | Task 4 Step 2 |
| 内置组件不允许修改/删除（403） | Task 4 Step 2 |
| 创建项目时传 style_config | Task 5 Step 5-6 |
| 默认兜底文本 | Task 1 Step 3（_DEFAULT_STYLE_COMPONENTS） |
| 前端 PromptComponent 类型 | Task 6 Step 1 |
| 创建项目弹窗风格选择器 | Task 7 |
| 风格库管理页 /style-library | Task 8 |
| 内置组件只读+复制为自定义 | Task 8 Step 1 |
| 种子数据（10 个内置组件） | Task 2 Step 4 |
