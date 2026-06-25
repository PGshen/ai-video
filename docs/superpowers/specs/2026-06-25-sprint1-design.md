# Sprint 1 设计文档：选题池 + 项目状态机

**日期：** 2026-06-25  
**范围：** 后端 API 实现、Temporal Workflow 空壳、前端选题页 + 项目页  
**不含：** AI 脚本生成（Sprint 2）、视频渲染（Sprint 3）、`brainstorm` 真实 LLM 调用（Sprint 2）

---

## 1. 后端 API

### 1.1 选题池 `/api/topics`

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/topics` | 列表查询，支持 `?status=` 筛选；返回 `TopicListResponse` |
| POST | `/api/topics` | 创建选题，写 `topics` 表；`source` 由请求体传入 |
| PATCH | `/api/topics/{id}` | 更新打分（4 维）、status、tags；`composite_score` 由 DB Computed 列自动计算 |
| POST | `/api/topics/brainstorm` | **Sprint 1 stub**：返回硬编码 3 条假候选选题，结构与 `TopicResponse` 一致 |

**`PATCH /api/topics/{id}` 实现要点：**
- 只更新请求体中非 `None` 的字段（partial update）
- 打分字段映射：`scores.counterintuitive` → `score_counterintuitive`，其余同理
- 更新后返回完整 `TopicResponse`（含 `composite_score`）

### 1.2 项目 `/api/projects`

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/projects` | 列表查询，支持 `?status=` 筛选；返回 `ProjectListResponse` |
| POST | `/api/projects` | 创建项目 + 启动 Temporal Workflow（见下方流程） |
| GET | `/api/projects/{id}` | 返回 `ProjectDetailResponse`（含 script_version、video_asset，Sprint 1 两者均为 null） |
| POST | `/api/projects/{id}/review` | 向 Temporal 发 Signal |

**`POST /api/projects` 流程：**
1. 写 `video_projects` 表，status = `draft`
2. 调 `temporal_client.start_workflow(VideoProductionWorkflow, project_id, id=f"video-production-{project_id}")`
3. 回写 `temporal_workflow_id` 到记录
4. 返回 `ProjectResponse`

**`POST /api/projects/{id}/review` Signal 路由：**
```
gate == "script" → workflow.signal("script_review", payload)
gate == "video"  → workflow.signal("video_review", payload)
```
payload 结构透传 `ReviewRequest` 字段（verdict、rejection_type 等）。

---

## 2. Temporal Workflow

### 2.1 VideoProductionWorkflow

按技术方案 §4.2 伪代码实现完整状态机结构（Phase 1 脚本循环 → Phase 2 视频循环 → Phase 3 发布）。Signal handler 全部注册。

### 2.2 Activities 实现程度

| Activity | Sprint 1 实现 |
|----------|--------------|
| `update_project_status` | **完整实现**：更新 `video_projects.status` + 插 `project_events` 记录 |
| `submit_script_generation_task` | 插一条 `worker_tasks` 记录（不会被处理，Sprint 2 接管） |
| `submit_video_generation_task` | 插一条 `worker_tasks` 记录（Sprint 3 接管） |
| `check_and_increment_retry` | 查 `retry_count`，自增后返回 `count < 3` |

### 2.3 Worker 进程

`combined_worker.py` 同时注册 Workflow + Activity，通过 `make dev-worker` 启动。

**Sprint 1 验收：** `POST /api/projects` 后，Temporal UI（:8080）能看到 workflow 实例处于等待 `script_generated` Signal 的挂起状态；`video_projects.status` = `script_generating`。

---

## 3. 前端

### 3.1 新增 shadcn 组件

需通过 `npx shadcn add` 安装：`sheet`、`radio-group`、`label`、`textarea`、`separator`、`scroll-area`

### 3.2 选题页 `TopicsPage`

**布局：**
- 顶部栏：页面标题 + `新增选题` 按钮 + 状态筛选 Select
- 主体：Table

**Table 列：**
| 列 | 说明 |
|----|------|
| 标题 | 可点击，打开打分 Sheet |
| 来源 | badge（manual / ai_brainstorm / audience / competitor） |
| 综合评分 | 数字 badge，颜色：≥4 绿、≥2.5 黄、<2.5 红；未打分显示「-」 |
| 状态 | badge（pending / stocked / in_production / used / abandoned） |
| 标签 | 最多显示 3 个 badge，超出省略 |
| 创建时间 | 相对时间（如「2 天前」） |
| 操作 | `打分` 按钮（打开 Sheet）|

**新增选题 Dialog：**
- 字段：标题（必填）、描述（Textarea）、来源（Select）、标签（逗号分隔输入，前端 split 成数组）
- 提交调 `POST /api/topics`

**打分 Sheet（右侧）：**
- 选题标题（只读，大字）、描述（只读）
- 4 个维度各一行：维度名 + RadioGroup（5 个选项 1-5，横排圆点样式）
- 状态下拉 Select
- 标签编辑输入框
- 底部两个按钮：`保存` + `从此选题创建项目`
- 保存调 `PATCH /api/topics/{id}`

**创建项目 Dialog（从打分 Sheet 底部触发）：**
- topic_id 自动带入（不展示）
- 字段：渲染引擎（Select：manim / remotion）、TTS Voice（Select：预设几个值）、画幅比例（Select：landscape / portrait）
- 提交调 `POST /api/projects`，成功后跳转到项目页

### 3.3 项目页 `ProjectsPage`

**布局：**
- 顶部栏：页面标题 + 状态筛选 Select（无创建入口）
- 主体：Table

**Table 列：**
| 列 | 说明 |
|----|------|
| 关联选题标题 | 后端 `ProjectResponse` 扩展 `topic_title: str` 字段，直接返回，无需前端 join |
| 状态 | badge，配色与状态语义对应 |
| 渲染引擎 | 文本 |
| 画幅比例 | 文本 |
| 创建时间 | 相对时间 |
| 操作 | `详情` 按钮（打开 Sheet）|

**详情 Sheet（右侧）：**
- 项目基本信息（topic、engine、voice、ratio）
- 状态时间线：展示 `project_events` 列表，每条含时间、事件类型、from→to 状态
- 脚本版本区（Sprint 1 显示「尚未生成」占位）

### 3.4 数据获取

- `useTopics`：`GET /api/topics`，支持 `status` 参数
- `useCreateTopic`、`useUpdateTopic` mutation
- `useProjects`：`GET /api/projects`，支持 `status` 参数
- `useCreateProject` mutation
- `useProject(id)`：`GET /api/projects/{id}`（详情 Sheet 用）
- `useProjectEvents(id)`：`GET /api/projects/{id}/events`

---

## 4. 不在 Sprint 1 范围内

- `POST /api/topics/brainstorm` 真实 LLM 调用（Sprint 2 实现）
- `GET /api/projects/{id}/script-versions` 列表页（Sprint 2）
- 脚本审核 UI（Sprint 2）
- 视频预览和视频审核（Sprint 3）
- `GET /api/projects/{id}/preview-url`（Sprint 3）
- 表现数据录入（Sprint 4）
