# Prompt 系统重构 & 视频风格多元化

**日期：** 2026-07-01  
**状态：** 待实现

---

## 背景与目标

当前所有 AI 提示词（叙事风格、配色系统、动画节奏、引擎技术规范）硬编码在 `backend/app/engines/ai/chat_provider.py` 中，只针对反差心理学视频类型，无法在不修改代码的情况下支持其他视频风格。

**目标：**
1. 将内容风格类提示词迁移到数据库，支持创作者在 UI 中自由管理
2. 将引擎技术规范迁移到 YAML 配置文件，按 render_engine 自动注入
3. 创建项目时按维度自由组合风格组件
4. 系统内置初始风格组件集，同时支持创作者新建自定义组件

---

## 数据模型

### 新增表：`prompt_components`

```sql
CREATE TABLE prompt_components (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category    VARCHAR(30)  NOT NULL,   -- 见下方 Category 枚举
    name        VARCHAR(100) NOT NULL,
    description TEXT,
    prompt_text TEXT         NOT NULL,
    is_builtin  BOOLEAN      NOT NULL DEFAULT false,
    created_by  VARCHAR(100),            -- 预留，当前单用户可为 null
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);
```

**Category 枚举（初始）：**

| category | 含义 | 示例值 |
|---|---|---|
| `narrative_style` | 叙事风格 | 反差心理学、科普解说、故事叙事 |
| `pacing` | 叙事节奏 | 慢节奏娓娓道来、快节奏信息密集 |
| `scene_structure` | 镜头结构 | 标准知识视频结构、问题-分析-结论 |
| `color_scheme` | 配色系统 | 亮底紫色系、暗底深蓝系 |
| `animation_style` | 动画风格 | 弹性大气感、简洁干净 |

Category 为开放字符串，新增维度无需改表结构，只增数据行。

### `video_projects` 表新增字段

```sql
ALTER TABLE video_projects
    ADD COLUMN style_config JSONB NOT NULL DEFAULT '{}';
```

`style_config` 结构（每个 key 是 category，value 是 component UUID）：

```json
{
  "narrative_style": "uuid-of-component",
  "color_scheme": "uuid-of-component",
  "animation_style": "uuid-of-component",
  "pacing": "uuid-of-component",
  "scene_structure": "uuid-of-component"
}
```

- 每个 category 都是可选的，未指定时使用系统兜底文本
- 不设数据库外键约束（与项目整体约束一致），应用层校验组件存在性

---

## 引擎技术规范（YAML 文件）

```
backend/app/engines/ai/engine_specs/
    manim.yaml
    remotion.yaml
```

文件内容：现有 `_ENGINE_CODE_PROMPTS` 和 `_NARRATIVE_ENGINE_HINTS` 中对应引擎的文本，分别提取到 YAML 的 `code_prompt` 和 `narrative_hint` 两个 key 下。

```yaml
# manim.yaml 示例结构
narrative_hint: |
  【Manim 画面描述规范——弱技术层】
  ...
code_prompt: |
  【Manim 代码规范】
  ...
```

`ChatAIProvider` 初始化时读取 `engine_specs/` 目录下所有 YAML，替换现有的 `_ENGINE_CODE_PROMPTS` 和 `_NARRATIVE_ENGINE_HINTS` dict。

---

## Prompt 组合逻辑

### 叙事脚本生成（`generate_narrative`）

system prompt 拼合顺序：

```
[固定骨架]         你是知识视频叙事脚本生成器…JSON格式要求…

[narrative_style]  narrative_style 组件 prompt_text（或默认文本）
[pacing]           pacing 组件 prompt_text（或默认文本）
[scene_structure]  scene_structure 组件 prompt_text（或默认文本）

[引擎叙事规范]     engine_specs/{render_engine}.yaml → narrative_hint
```

### 代码生成（`generate_code` / `repair_code`）

system prompt 拼合顺序：

```
[固定骨架]         你是知识视频代码生成器…JSON格式要求…

[color_scheme]     color_scheme 组件 prompt_text（或默认文本）
[animation_style]  animation_style 组件 prompt_text（或默认文本）

[引擎代码规范]     engine_specs/{render_engine}.yaml → code_prompt
```

### 默认兜底文本

`ChatAIProvider` 保留一份硬编码的默认文本 dict（每个 category 各一条），当项目 `style_config` 未指定某 category 时使用。当前反差心理学相关文本迁移为内置组件 + 对应 category 的默认兜底文本。

### 接口变更

`generate_narrative` 和 `generate_code` 增加参数 `style_components: dict[str, str]`，值为各 category 对应的 `prompt_text`（由上层 activity 从 DB 查询后传入，provider 层不直接访问 DB）。

---

## 后端 API

### prompt_components CRUD

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/prompt-components` | 列表，支持 `?category=` 过滤 |
| POST | `/api/prompt-components` | 新建组件 |
| PUT | `/api/prompt-components/{id}` | 更新（内置组件不允许修改） |
| DELETE | `/api/prompt-components/{id}` | 删除（内置组件不允许删除） |
| POST | `/api/prompt-components/{id}/duplicate` | 复制为自定义 |

### 项目创建/更新

`POST /api/projects` 和 `PUT /api/projects/{id}` 的 request schema 增加 `style_config` 字段（可选 JSONB）。

---

## 前端

### 创建项目弹窗（扩展）

在现有表单（render_engine、tts_voice、aspect_ratio）之后增加"视频风格"分组，每个 category 展示为一个带搜索的下拉选择器。

- 选项来源：`GET /api/prompt-components?category=xxx`
- 可选"系统默认"（不传该 category）
- 每个选项显示 name + description tooltip

### 风格库管理页（新增）

- 路由：`/style-library`
- 导航：侧边栏新增"风格库"入口
- 布局：左侧 category tab 切换，右侧卡片列表
- 操作：
  - 新建自定义组件（填 name / description / prompt_text）
  - 编辑自定义组件
  - 删除自定义组件（二次确认）
  - 内置组件只读，显示"复制为自定义"按钮
- prompt_text 使用多行文本框，支持预览（原始文本，非渲染）

---

## 数据初始化

新增 Alembic migration：
1. 创建 `prompt_components` 表
2. 为 `video_projects` 添加 `style_config` 列
3. 插入种子数据：将现有 `chat_provider.py` 中的各维度文本拆解为内置组件行（is_builtin=true）

---

## 不在本次范围内

- 多用户隔离（created_by 字段预留但不校验）
- 组件版本历史
- 组件共享/发布功能
- 提示词效果 A/B 测试
