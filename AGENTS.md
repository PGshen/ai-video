# AI 知识视频生产工作流平台

## 项目概述

面向自媒体创作者的 AI 驱动知识视频端到端生产工作流系统。技术方案见 `docs/TECH_技术实现方案.md`，产品需求见 `docs/PRD_产品需求文档.md`。

## 快速启动

```bash
# 1. 启动基础设施（postgres / temporal / minio）
make up

# 2. 数据库迁移
make migrate

# 3. 启动后端（新终端）
make dev-backend   # → http://localhost:8000

# 4. 启动 Worker（新终端）
make dev-worker

# 5. 启动前端（新终端）
make dev-frontend  # → http://localhost:5173
```

## 目录结构

```
backend/          Python FastAPI 后端
  app/
    api/          FastAPI routers（路由层，仅调度，不含业务逻辑）
    models/       SQLAlchemy ORM 模型（7 张表）
    schemas/      Pydantic request/response schemas
    engines/      可插拔引擎层（render / tts / ai）
    workflows/    Temporal workflow + activities
    workers/      BaseWorker + ScriptWorker + RenderWorker
    config.py     Pydantic settings（从 .env 读取）
    auth.py       API Key 验证 Depends
    db.py         async engine（FastAPI）+ sync engine（Worker）
    main.py       FastAPI 应用入口
  alembic/        DB migrations
  tests/          pytest 测试

frontend/         React + Vite 前端
  src/
    types/        TypeScript 类型定义（与后端 schema 对应）
    lib/api.ts    fetch 封装，自动注入 X-API-Key
    hooks/        TanStack Query hooks
    pages/        页面组件
    components/   UI 组件
      ui/         shadcn/ui 组件
```

## 关键约束

- **不设数据库外键约束**：表间关联在应用层维护，`_id` 字段仅是命名约定
- **状态权威来源是 Temporal**：`video_projects.status` 是镜像，用于前端快速查询
- **镜头是最小原子单位**：脚本以 `scenes[]` 数组组织，每个镜头有独立 narration/code
- **渲染时整体提交**：所有镜头代码合并后一次性提交给渲染引擎（镜头间存在依赖）
- **两道人工审核闸门不可跳过**：`script_review`（闸门①）和 `video_review`（闸门②）

## 技术选型

| 层级 | 选型 |
|------|------|
| Python 包管理 | uv |
| 前端构建 | Vite 5 |
| 鉴权 | X-API-Key 请求头（环境变量 API_KEY） |
| 异步任务 | Temporal（工作流）+ worker_tasks 表（任务轮询）|

## 已知偏差与注意事项

### Tailwind v4（intentional）
`shadcn@4.11` 初始化时自动安装 Tailwind v4，这是预期行为而非错误。前端 `tailwind.config.js` 不存在是正常的——Tailwind v4 通过 `frontend/src/index.css` 中的 `@import "tailwindcss"` 配置，无需独立配置文件。**不要降级到 Tailwind v3。**

### BaseWorker `db.merge(task)` 问题（Sprint 2 修复）
`backend/app/workers/base_worker.py` 中 `BaseWorker._persist_task()` 使用了 `db.merge(task)`（SQLAlchemy Session merge）。在 Sprint 0 阶段 Worker 未真正连接数据库，该行为不影响当前测试。Sprint 2 真正接入数据库写入时需要改为 `db.add(task)` + `db.flush()` 或改用 upsert 语义，否则在无主键的新对象上 merge 行为未定义。

## 环境变量

后端从 `backend/.env` 读取（参考 `backend/.env.example`）。
前端从 `frontend/.env` 读取（参考 `frontend/.env.example`）。

## 命令行工具路径（沙箱环境）

Codex 沙箱的 `PATH` 不包含 `~/.local/bin` 和 nvm shims，必须使用绝对路径：

```bash
# Python / uv
/Users/peng/.local/bin/uv run pytest tests/ -v
/Users/peng/.local/bin/uv run python ...

# Node / pnpm（需先把 node 加入 PATH）
PATH="/Users/peng/.nvm/versions/node/v24.11.0/bin:$PATH" pnpm build
PATH="/Users/peng/.nvm/versions/node/v24.11.0/bin:$PATH" pnpm install
```

不要使用裸命令 `uv` / `pnpm` / `npm`，会返回 "command not found"。

## 测试

```bash
cd backend
/Users/peng/.local/bin/uv run pytest tests/ -v
```

## 当前 Sprint 状态

- **Sprint 0（已完成）**：基础设施骨架，所有 API 返回 stub
- **Sprint 1（已完成）**：选题池 + 项目状态机（Temporal Workflow 空壳跑通）
- **Sprint 2**：脚本生成 + 内容审核
- **Sprint 3**：视频生成 + 视频审核
