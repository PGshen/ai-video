# Sprint 2 设计文档：脚本生成 + 内容审核

> 日期：2026-06-26 | 状态：已批准

---

## 范围

Sprint 2 交付物：

1. **ScriptWorker**：调用 AI 生成镜头数组 + 事实核查表，存入 `script_versions`，发送 Temporal Signal 回调
2. **后端 API 扩展**：`GET /api/projects/{id}/script` 新端点；`POST /api/projects/{id}/review` 支持逐条事实核查标注
3. **前端 ProjectDetailPage**：镜头浏览 + 精细事实核查审核 UI（逐条 verdict + 整体通过/驳回/废弃）

不在本 Sprint 范围：视频渲染、RenderWorker、视频审核 UI。

---

## § 1：后端 — ScriptWorker 实现

### 1.1 `submit_script_generation_task` Activity 补全

当前实现创建 `WorkerTask` 时 `input_payload` 为空。需要补全：从 `topics` 表读取 `topic_title`、`topic_description`（通过 `project.topic_id` 关联），写入 `input_payload`：

```json
{
  "topic_title": "...",
  "topic_description": "...",
  "render_engine": "manim",
  "rejection_context": null
}
```

驳回重生成时，`rejection_context` 填入上一次审核的驳回信息（从 `project_events` 最近一条 `review_rejected` 事件读取）。

### 1.2 `ScriptWorker._execute` 实现流程

```
1. 读 task.input_payload → topic_title, topic_description, render_engine, rejection_context
2. get_ai_provider().generate_script(...) → ScriptGenerationResult(scenes, fact_checks)
3. 查 script_versions 中当前项目最大 version_number，自增
4. INSERT script_versions（scenes JSONB, fact_checks JSONB, ai_model, version_number）
5. UPDATE video_projects.current_script_version_id
6. UPDATE worker_task: status=completed, output_payload={script_version_id, scene_count, fact_check_count}
7. 发 Temporal Signal: script_generated → {success: true, script_version_id}
```

失败时：`status=failed`，`output_payload={error_message}`，发 Signal `{success: false, error}`。

### 1.3 `ChatAIProvider.generate_script` — 按引擎定制 prompt

System prompt 由公共部分 + 引擎特定部分拼合：

**公共部分**：JSON 格式要求、scenes/fact_checks 结构定义、输出约束（只输出合法 JSON object）

**引擎特定部分**（注入 system prompt 的 code 字段说明）：

- `manim`：Python Manim 代码，继承 `Scene` 类，`construct()` 方法，在需要音频的位置使用 `{{AUDIO_SCENE_N}}` 占位符
- `remotion`：React/TypeScript Remotion 组件，`useCurrentFrame`/`useVideoConfig` hook，音频通过 `<Audio>` 组件注入
- 未知引擎：通用兜底，只说明 code 字段用途

实现方式：在 `ChatAIProvider` 内维护 `_ENGINE_CODE_PROMPTS: dict[str, str]`，`generate_script` 拼合时按 `render_engine` 查找。

---

## § 2：后端 API 扩展

### 2.1 新增 `GET /api/projects/{id}/script`

返回当前项目 `current_script_version_id` 对应的脚本版本完整内容：

```python
class ScriptVersionDetail(BaseModel):
    id: UUID
    version_number: int
    scenes: list[dict]       # Scene[] JSONB
    fact_checks: list[dict]  # FactCheckItem[] JSONB
    ai_model: str | None
    created_at: datetime
```

404 当项目不存在或 `current_script_version_id` 为 None（脚本尚未生成）。

### 2.2 扩展 `POST /api/projects/{id}/review`

`ReviewRequest` 新增可选字段：

```python
class FactCheckVerdictItem(BaseModel):
    index: int
    verdict: Literal["approved", "rejected", "needs_revision"]
    note: str | None = None

class ReviewRequest(BaseModel):
    gate: Literal["script", "video"]
    verdict: Literal["approved", "rejected", "abandoned"]
    rejection_type: str | None = None
    rejection_detail: str | None = None
    target_stage: str | None = None
    fact_check_verdicts: list[FactCheckVerdictItem] | None = None  # 新增
```

Handler 逻辑扩展：当 `gate == "script"` 且 `fact_check_verdicts` 非空时，先从 DB 读取 `current_script_version`，按 `index` 更新 `fact_checks` JSONB 中对应条目的 `reviewer_verdict`/`reviewer_note`，再发 Temporal Signal。

---

## § 3：前端 — ProjectDetailPage

### 3.1 页面布局

```
┌─────────────────────────────────────────────────────┐
│ 顶部状态栏：项目名 | 状态 badge | 已驳回 N 次（>0时）  │
├────────────────────┬────────────────────────────────┤
│ 左：镜头列表        │ 右：事实核查表                  │
│ (ScrollArea)       │ (ScrollArea)                   │
│                    │                                │
│ [镜头 0]           │ [核查条目 0]                    │
│   description      │   claim_text                   │
│   narration        │   confidence badge             │
│   duration         │   source_description           │
│   code (折叠)       │   ● approved ○ rejected ...   │
│                    │   reviewer_note textarea        │
│ [镜头 1] ...       │ [核查条目 1] ...               │
├────────────────────┴────────────────────────────────┤
│ 底部操作栏（仅 script_review 状态可见）               │
│ [通过（全部已标注才可点）] [驳回重生成] [废弃项目]      │
└─────────────────────────────────────────────────────┘
```

### 3.2 状态展示（非 script_review 状态）

| 项目状态 | 提示内容 |
|----------|----------|
| `script_generating` | 「AI 正在生成脚本…」+ spinner |
| `script_review` | 显示完整审核 UI |
| `script_failed` | 「脚本生成失败」+ 错误信息 |
| `video_generating` / `video_review` / 其他 | 对应状态提示，不显示脚本审核操作 |

### 3.3 事实核查表交互

- 每条 `FactCheckItem` 渲染为独立卡片
- RadioGroup 三选一：`approved` / `needs_revision` / `rejected`
- `reviewer_note` textarea 在选 `rejected` 或 `needs_revision` 时展开
- React state 维护所有标注（`Map<index, {verdict, note}>`）
- 「通过」按钮 disabled 条件：任意一条 fact_check 尚无 verdict
- 驳回次数 `>= 3` 时隐藏「驳回重生成」按钮，只保留「通过」和「废弃」

### 3.4 提交逻辑

```typescript
// 通过
POST /api/projects/{id}/review
{
  gate: "script",
  verdict: "approved",
  fact_check_verdicts: [{ index: 0, verdict: "approved", note: null }, ...]
}

// 驳回重生成
{
  gate: "script",
  verdict: "rejected",
  rejection_detail: "...",
  fact_check_verdicts: [...]
}

// 废弃
{
  gate: "script",
  verdict: "abandoned"
}
```

---

## § 4：数据库迁移 & TypeScript Types

### 4.1 DB 迁移

无新表。`script_versions` 和 `worker_tasks` 已在 Sprint 1 建好。只需确认 `input_payload` 写入逻辑正确（Activity 层代码补全，非 schema 变更）。

### 4.2 前端 TypeScript Types 新增/修改

```typescript
// types/index.ts 新增/补全
export type FactCheckVerdict = "approved" | "rejected" | "needs_revision";

export interface FactCheckItem {
  claim_text: string;
  scene_index: number;
  source_url: string | null;
  source_description: string;
  confidence: "high" | "medium" | "low";
  is_hypothesis: boolean;
  assumptions: string | null;
  controversy: string | null;
  reviewer_verdict: FactCheckVerdict | null;  // 补全
  reviewer_note: string | null;               // 补全
}

export interface Scene {
  scene_index: number;
  narration: string;
  description: string;
  code: string;
  estimated_duration_seconds: number;
}

export interface ScriptVersionDetail {
  id: string;
  version_number: number;
  scenes: Scene[];
  fact_checks: FactCheckItem[];
  ai_model: string | null;
  created_at: string;
}

export interface FactCheckVerdictItem {
  index: number;
  verdict: FactCheckVerdict;
  note: string | null;
}
```

---

## 决策记录

| 决策 | 选择 | 原因 |
|------|------|------|
| 事实核查标注持久化时机 | 前端本地 state，提交时批量写入 | 实现最简，Sprint 2 阶段刷新丢失可接受 |
| 驳回次数上限 | 3 次（与后端 max_retries 对齐） | 避免无限循环；超限后只保留「通过」和「废弃」 |
| 废弃操作 | 前端增加「废弃」按钮，`verdict: "abandoned"` | Workflow 已有 abandoned 分支，无需后端改动 |
| generate_script prompt | 按 render_engine 定制 code 字段说明 | 不同引擎代码结构差异大，通用 prompt 质量差 |
