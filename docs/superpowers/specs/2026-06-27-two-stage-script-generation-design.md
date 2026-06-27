# 两阶段脚本生成设计

> 日期：2026-06-27 | 状态：已批准

---

## 背景与目标

当前脚本生成是单阶段：一次 AI 调用同时产出旁白、画面描述和渲染代码。实际效果是脚本质量差、代码可用性低——叙事结构和画面设计没有独立打磨的机会。

目标：拆分为两阶段，先由 AI 生成高质量叙事脚本（旁白 + 画面描述），人工审核并可内联编辑后，再由 AI 一次性生成所有镜头的渲染代码。

---

## § 1 状态机

移除旧状态 `script_generating`、`script_failed`，新增四个状态：

```
draft
  └─► narrative_generating   ← NarrativeWorker：AI 生成叙事脚本
        │  失败/超限 → narrative_failed → abandoned
        └─► narrative_review       ← 人工审核，可内联编辑旁白和描述
              │  驳回 → 回到 narrative_generating（AI 重新生成）
              │  废弃 → abandoned
              └─► code_generating        ← CodeWorker：AI 生成所有镜头代码
                    │  失败/超限 → code_failed → abandoned
                    └─► script_review        ← 现有门，完整脚本审核
                          │  驳回（target_stage="code"）      → 回到 code_generating
                          │  驳回（target_stage="narrative"） → 回到 narrative_generating
                          │  废弃 → abandoned
                          └─► video_generating → video_review → published
```

---

## § 2 数据模型

### 新表 `narrative_versions`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | |
| project_id | UUID | |
| version_number | Integer | 同项目自增，从 1 起 |
| scenes | JSONB | `[{scene_index, narration, description, estimated_duration_seconds}]` |
| fact_checks | JSONB | 同现有 script_versions 结构 |
| ai_model | VARCHAR(50) | |
| rejection_context | JSONB | 驳回重生成时携带的上下文 |
| created_at | TIMESTAMPTZ | |

### `video_projects` 表新增列

`current_narrative_version_id UUID` — 指向当前叙事版本，CodeWorker 从这里读取 scenes。

### `script_versions` 表不变

继续存完整脚本（narration + description + code + fact_checks）。fact_checks 由 CodeWorker 从叙事版本复制，不重新调 AI。

### 前端 TypeScript 新增类型

```typescript
interface NarrativeScene {
  scene_index: number;
  narration: string;
  description: string;
  estimated_duration_seconds: number | null;
}

interface NarrativeVersion {
  id: string;
  version_number: number;
  scenes: NarrativeScene[];
  fact_checks: FactCheckItem[];
  ai_model: string | null;
  created_at: string;
}
```

---

## § 3 后端：Workers + AI Provider

### NarrativeWorker

- task_type: `generate_narrative`
- 读 `input_payload`：`topic_title`, `topic_description`, `render_engine`, `rejection_context`
- 调 `provider.generate_narrative(...)` → `NarrativeResult(scenes, fact_checks)`
- 写 `narrative_versions`，更新 `project.current_narrative_version_id`
- 通知 Temporal signal `narrative_generated`

### CodeWorker

- task_type: `generate_code`
- 读 `project.current_narrative_version_id` → 取出全部 scenes（含人工编辑后内容）
- 调 `provider.generate_code(scenes, render_engine)` → 每个镜头的 code 字符串列表
- 将 narrative scenes + code 合并，连同 fact_checks 写入新 `ScriptVersion`
- 更新 `project.current_script_version_id`
- 通知 Temporal signal `code_generated`

### 删除 ScriptWorker

`combined_worker` 中移除 `ScriptWorker` 注册。

### AI Provider 新增两个方法

**`generate_narrative(topic_title, topic_description, render_engine, rejection_context)`**

输出格式：
```json
{
  "scenes": [
    {
      "scene_index": 0,
      "narration": "旁白文稿",
      "description": "画面描述（明确标注元素进场、变形、退场及跨镜头衔接）",
      "estimated_duration_seconds": 8.0
    }
  ],
  "fact_checks": [...]
}
```

Prompt 要求：
- 整体娓娓道来，有吸引力，知识讲解有层次感
- `description` 字段服务于后续代码生成：优先使用图形、公式、数轴、几何图示；明确标注元素进场方式（Create/Write/FadeIn）、变形（Transform/ReplacementTransform）、退场（FadeOut）及跨镜头衔接（哪些元素保留给下一镜头）
- 避免大段文字堆砌，每帧实际显示文字不超过 15 个汉字

**`generate_code(scenes, render_engine)`**

输入：完整 scenes 数组（含 narration + description）及 render_engine。

一次调用生成所有镜头 code 片段，沿用现有 `_ENGINE_CODE_PROMPTS` 规范（Manim 变量生命周期、跨镜头衔接、Remotion 帧规则等）。

输出格式：
```json
{
  "codes": ["scene 0 的 code 片段", "scene 1 的 code 片段", ...]
}
```

---

## § 4 API

### 新端点

`GET /api/projects/{id}/narrative` — 返回 `current_narrative_version_id` 对应叙事版本完整内容，404 若未生成。

### 扩展 `POST /api/projects/{id}/review`

```python
class EditedNarrativeScene(BaseModel):
    scene_index: int
    narration: str
    description: str
    estimated_duration_seconds: float | None = None

class ReviewRequest(BaseModel):
    gate: Literal["narrative", "script", "video"]
    verdict: Literal["approved", "rejected", "abandoned"]
    rejection_detail: str | None = None
    target_stage: str | None = None                               # script gate 驳回时指定回退目标
    fact_check_verdicts: list[FactCheckVerdictItem] | None = None # script gate 用
    edited_scenes: list[EditedNarrativeScene] | None = None       # narrative gate 用
```

**`gate="narrative"` + `verdict="approved"` 处理逻辑：**
1. 若 `edited_scenes` 非空，UPDATE `narrative_version.scenes`（覆盖为编辑后内容）
2. 发 Temporal signal `narrative_review {verdict: "approved"}`

**`gate="script"` 驳回时：**
- `target_stage="narrative"`（默认） → Workflow 回到 `narrative_generating`
- `target_stage="code"` → Workflow 回到 `code_generating`

---

## § 5 Temporal Workflow 改造

### 新增 signal handlers

```python
@workflow.signal
async def narrative_generated(self, payload: dict): ...

@workflow.signal
async def narrative_review(self, payload: dict): ...

@workflow.signal
async def code_generated(self, payload: dict): ...
```

### 删除 signal handlers

删除 `script_generated`（原单阶段用）。

### 主流程 `run()` 结构

```python
async def run(self, project_id: str) -> None:
    need_narrative = True
    while True:
        if need_narrative:
            result = await self._generate_and_review_narrative(project_id)
            if result == "abandoned":
                await self._update_status(project_id, "abandoned")
                return
            # result == "approved"，继续进入代码生成

        result = await self._generate_code_and_review_script(project_id)
        if result == "approved":
            break
        elif result == "back_to_narrative":
            need_narrative = True
            continue
        elif result == "back_to_code":
            need_narrative = False
            continue
        elif result == "abandoned":
            await self._update_status(project_id, "abandoned")
            return

    # Phase 2: 视频生成（不变）
    ...
```

### 删除旧 activities

删除 `submit_script_generation_task`，新增 `submit_narrative_task` 和 `submit_code_task`。

---

## § 6 前端

### 新状态展示

| 项目状态 | 展示内容 |
|----------|----------|
| `narrative_generating` | 「AI 正在生成叙事脚本…」+ spinner |
| `narrative_review` | NarrativeReviewPanel（见下） |
| `code_generating` | 「AI 正在生成动画代码…」+ spinner |
| `script_review` | 现有完整脚本审核 UI（不变） |
| `narrative_failed` / `code_failed` | 错误提示 + 重试按钮（废弃） |

### 新组件 NarrativeReviewPanel

**布局（左右分栏）：**
- 左：ScrollArea，每个镜头卡片含可编辑 `narration`（textarea）和 `description`（textarea），`estimated_duration_seconds` 只读展示
- 右：ScrollArea，fact_checks 只读展示（verdict 标注在 script_review 门进行）
- 底部操作栏：「确认通过（进入代码生成）」/「驳回重新生成叙事」/「废弃项目」

**提交逻辑：**
```typescript
// 通过（含编辑内容）
POST /api/projects/{id}/review
{
  gate: "narrative",
  verdict: "approved",
  edited_scenes: [{ scene_index: 0, narration: "...", description: "..." }, ...]
}
```

### script_review 门调整

驳回时增加回退目标选择：
```typescript
{
  gate: "script",
  verdict: "rejected",
  rejection_detail: "...",
  target_stage: "narrative" | "code"  // 默认 "narrative"
}
```

---

## 决策记录

| 决策 | 选择 | 原因 |
|------|------|------|
| 叙事和代码分表 | 两张表（narrative_versions + script_versions） | 语义清晰，无数据模糊；开发阶段无迁移成本 |
| Worker 拆分 | NarrativeWorker + CodeWorker，删除 ScriptWorker | 职责单一，便于独立测试和监控 |
| 代码生成粒度 | 一次调用生成所有镜头 code | AI 能看到完整上下文，保证跨镜头变量连贯性 |
| 叙事审核内联编辑 | 支持 | 避免因小改动重跑 AI，节省时间和 token |
| 旧状态 | 直接删除 script_generating/script_failed | 开发阶段无数据包袱，保留只增加维护成本 |
| script_review 驳回回退目标 | 可选 narrative 或 code，默认 narrative | 灵活性，避免在叙事已好的情况下强制重跑 |
