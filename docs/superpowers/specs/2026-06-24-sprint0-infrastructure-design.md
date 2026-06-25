# Sprint 0 — 基础设施搭建设计文档

> 日期: 2026-06-24 | 配套文档: PRD v2.0 / TECH v4.0 | Sprint: 0

---

## 1. 范围定义

本 Sprint 交付「含 stub 路由的骨架」（选项 C）：

- docker-compose 一键启动所有基础设施服务
- PostgreSQL 完整 schema migration（全部 7 张表）
- FastAPI 骨架：所有 API endpoint stub + Pydantic schema 完整定义 + API Key 鉴权
- React + Vite 骨架：所有页面占位 + 路由接线 + TanStack Query hooks + 完整 TypeScript 类型
- BaseWorker 完整实现 + ScriptWorker/RenderWorker/CombinedWorker stub
- Temporal Workflow + Activity 骨架

**不在本 Sprint 范围：** 任何业务逻辑实现、AI 调用、TTS、渲染引擎。

---

## 2. 技术选型确认

| 层级 | 选型 |
|------|------|
| 前端构建 | Vite |
| Python 包管理 | uv |
| 鉴权方案 | API Key（X-API-Key 请求头 + 环境变量） |
| 应用服务启动方式 | 本地直接运行（不放入 docker-compose） |

---

## 3. 目录结构

```
ai-video/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── topics.py
│   │   │   ├── projects.py
│   │   │   ├── reviews.py
│   │   │   └── worker_tasks.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── topic.py
│   │   │   ├── project.py
│   │   │   ├── script_version.py
│   │   │   ├── video_asset.py
│   │   │   ├── worker_task.py
│   │   │   └── project_event.py
│   │   ├── schemas/
│   │   │   ├── topic.py
│   │   │   ├── project.py
│   │   │   ├── review.py
│   │   │   └── worker_task.py
│   │   ├── engines/
│   │   │   ├── render/base.py
│   │   │   ├── tts/base.py
│   │   │   └── ai/base.py
│   │   ├── workflows/
│   │   │   ├── video_production.py
│   │   │   └── activities.py
│   │   ├── workers/
│   │   │   ├── base.py
│   │   │   ├── script_worker.py
│   │   │   ├── render_worker.py
│   │   │   └── combined_worker.py
│   │   ├── db.py
│   │   ├── auth.py
│   │   └── main.py
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   │       └── 0001_initial_schema.py
│   ├── pyproject.toml
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── topics/
│   │   │   ├── projects/
│   │   │   ├── review/
│   │   │   └── ui/
│   │   ├── hooks/
│   │   │   ├── useTopics.ts
│   │   │   ├── useProjects.ts
│   │   │   └── useWorkerTasks.ts
│   │   ├── pages/
│   │   │   ├── TopicsPage.tsx
│   │   │   ├── ProjectsPage.tsx
│   │   │   ├── ProjectDetailPage.tsx
│   │   │   └── PerformancePage.tsx
│   │   ├── types/index.ts
│   │   ├── lib/api.ts
│   │   └── App.tsx
│   ├── package.json
│   └── .env.example
├── docker-compose.yml
├── .env.example
├── Makefile
└── CLAUDE.md
```

---

## 4. docker-compose 基础设施服务

应用服务（FastAPI、Worker、Vite）**不放入 docker-compose**，本地直接启动以获得热重载和断点调试能力。

| 服务 | 镜像 | 端口 |
|------|------|------|
| postgres | postgres:16 | 5432 |
| temporal | temporalio/auto-setup:latest | 7233 |
| temporal-ui | temporalio/ui:latest | 8080 |
| minio | minio/minio | 9000 / 9001 |

Temporal 使用同一个 PostgreSQL 实例，但使用独立的数据库名 `temporal`，应用使用 `video_workflow`。

### Makefile 命令

```makefile
make up            # docker-compose up -d
make down          # docker-compose down
make migrate       # cd backend && alembic upgrade head
make dev-backend   # uvicorn app.main:app --reload
make dev-worker    # python -m app.workers.combined_worker
make dev-frontend  # npm run dev（frontend 目录）
```

---

## 5. 数据库 Migration

单个 migration 文件 `0001_initial_schema.py` 建全 7 张表，顺序如下：

1. `topics` — composite_score 使用 PostgreSQL GENERATED ALWAYS 列
2. `video_projects`
3. `script_versions` — scenes / fact_checks 为 JSONB
4. `video_assets`
5. `worker_tasks`
6. `project_events` — BIGSERIAL 主键，追加不可变
7. `performance_records` — project_id UNIQUE

**关键约束：** 所有表不设外键约束，关联关系在应用层维护。

`composite_score` 计算公式：
```sql
(score_counterintuitive + score_defensibility + score_visual + score_freshness) / 4.0
```

---

## 6. FastAPI 骨架

### 6.1 鉴权

`app/auth.py` 实现 `verify_api_key` FastAPI Depends：

```python
def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
```

`/health` 端点不需要鉴权。

### 6.2 Stub 规范

每个 endpoint handler 返回：
```python
{"status": "TODO", "endpoint": "POST /api/topics"}
```
同时声明完整的 Pydantic request/response schema，字段与技术方案附录类型一致。

### 6.3 完整 API 清单

```
GET    /health                              → {"status": "ok"}（无鉴权）

GET    /api/topics                          → TopicListResponse
POST   /api/topics                          → TopicResponse
PATCH  /api/topics/{id}                     → TopicResponse
POST   /api/topics/brainstorm               → BrainstormResponse

GET    /api/projects                        → ProjectListResponse
POST   /api/projects                        → ProjectResponse
GET    /api/projects/{id}                   → ProjectDetailResponse
POST   /api/projects/{id}/review            → ReviewResponse
GET    /api/projects/{id}/script-versions   → ScriptVersionListResponse
GET    /api/projects/{id}/events            → EventListResponse
POST   /api/projects/{id}/performance       → PerformanceResponse
GET    /api/projects/{id}/preview-url       → PreviewUrlResponse

GET    /api/worker-tasks                    → WorkerTaskListResponse
```

---

## 7. 前端骨架

### 7.1 路由

```
/                         → redirect /topics
/topics                   → TopicsPage
/projects                 → ProjectsPage
/projects/:id             → ProjectDetailPage
/projects/:id/performance → PerformancePage
```

左侧导航栏渲染「选题池」「项目列表」两个链接，点击跳转。

### 7.2 页面 Stub

每个 Page 组件：页面 `<h1>` 标题 + `<p>TODO: {页面名}</p>` 占位。

### 7.3 API 层

`lib/api.ts`：封装 `fetch`，从 `VITE_API_KEY` 注入 `X-API-Key`，从 `VITE_API_BASE_URL` 读基础 URL。

### 7.4 Hooks

`useTopics` / `useProjects` / `useWorkerTasks`：TanStack Query `useQuery` 骨架，已接 `api.ts`，返回空数组占位。

### 7.5 类型定义

`types/index.ts` 完整包含技术方案附录 13 的所有 TypeScript 类型：`Topic`、`VideoProject`、`Scene`、`ScriptVersion`、`FactCheckItem`、`ReviewRequest`、`WorkerTask`、`VideoAsset`、`ProjectEvent`、`PerformanceRecord`、`RejectionContext`。

### 7.6 Shadcn 组件

初始化 shadcn/ui，Sprint 1 必用组件：`Button`、`Card`、`Badge`、`Dialog`、`Table`、`Input`、`Select`。

---

## 8. Worker 框架

### 8.1 BaseWorker（完整实现）

按技术方案 6.1 完整实现：

- `_claim_next_task()`：`SELECT ... FOR UPDATE SKIP LOCKED` 原子认领，过滤 `supported_task_types`
- `_process_task()`：执行 → 成功回写 → 发成功 Signal；失败时检查重试次数，未达上限重置为 `pending`，达上限发失败 Signal
- `_send_signal()`：通过 Temporal Client 发 Signal
- `run()`：轮询主循环，无任务时 sleep `poll_interval`（默认 2s）

### 8.2 Stub Workers

- `ScriptWorker`：`supported_task_types = ["generate_script"]`，`_execute` raise NotImplementedError
- `RenderWorker`：`supported_task_types = ["render_video"]`，`_execute` raise NotImplementedError
- `CombinedWorker`：`supported_task_types = ["generate_script", "render_video"]`，开发用

### 8.3 Temporal Workflow 骨架

`VideoProductionWorkflow`：`@workflow.defn` + `@workflow.run` 声明，`raise NotImplementedError`。

Activity 函数（`submit_script_generation_task`、`submit_video_generation_task`、`update_project_status`、`check_and_increment_retry`）：`@activity.defn` 声明，`raise NotImplementedError`。

---

## 9. 环境变量

`.env.example`（根目录）：
```env
# 数据库
DATABASE_URL=postgresql+asyncpg://app:password@localhost:5432/video_workflow
DB_PASSWORD=password

# Temporal
TEMPORAL_ADDRESS=localhost:7233
TEMPORAL_DB_PASSWORD=temporal_password

# MinIO / S3
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin

# 鉴权
API_KEY=dev-api-key-change-in-prod

# AI（Sprint 2 使用）
ANTHROPIC_API_KEY=
```

`frontend/.env.example`：
```env
VITE_API_BASE_URL=http://localhost:8000
VITE_API_KEY=dev-api-key-change-in-prod
```

---

## 10. 验收标准

Sprint 0 完成的判定条件：

1. `make up` 成功启动 postgres / temporal / temporal-ui / minio，无报错
2. `make migrate` 成功建全 7 张表
3. `make dev-backend` 启动，`GET /health` 返回 `{"status": "ok"}`
4. 所有 13 个 API endpoint 返回正确 HTTP 状态码和 stub payload
5. `make dev-frontend` 启动，4 个页面路由可访问，左侧导航可跳转
6. `make dev-worker` 启动 CombinedWorker，无报错（轮询循环运行，无任务时 sleep）
