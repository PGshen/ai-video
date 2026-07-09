# AI 知识视频生产工作流平台

面向自媒体创作者的 AI 驱动知识视频端到端生产工作流系统。平台把「选题发现 -> 叙事生成与审核 -> 代码生成与审核 -> TTS 与视频渲染 -> 成片审核 -> 发布与数据回流」组织为可追溯、可重试、带人工闸门的持久化工作流。

本项目当前处于 Sprint 2/3 演进阶段：基础设施、选题池、项目状态机、叙事生成、代码生成、内容审核、AI 模型配置、风格库、调用记录和 Remotion/Manim 渲染能力已具备骨架或实现。

## 核心特性

- 选题池管理：手动录入、AI 头脑风暴、研究资料沉淀、四维评分与状态流转。
- 视频项目状态机：以 Temporal Workflow 为权威状态源，数据库状态用于前端快速查询。
- 分阶段内容生产：先生成叙事版本并审核，再生成渲染代码并审核。
- 镜头级结构化内容：视频以 `scenes[]` 组织，每个镜头包含旁白、画面描述、代码、节拍和时长信息。
- 事实核查表：关键论断附带来源、置信度、假设条件、争议点和审核结论。
- 可插拔引擎：AI Provider、TTS Engine、Render Engine 均通过接口抽象接入。
- 人工审核闸门：`narrative_review`、`code_review`、`video_review` 三道闸门不可跳过。
- 产物存储与回放：音频、视频和渲染产物通过 MinIO/S3 管理。
- 运营配置：支持 AI 模型配置、Prompt 组件、风格模板、AI 调用记录与成本追踪。

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 前端 | React 19、TypeScript、Vite、Tailwind CSS v4、shadcn/ui、TanStack Query |
| 后端 | Python 3.12、FastAPI、SQLAlchemy、Alembic、Pydantic |
| 工作流 | Temporal Python SDK |
| 数据库 | PostgreSQL 16 |
| 对象存储 | MinIO / S3 |
| AI | DeepSeek、OpenRouter、Gemini、Doubao 等可插拔 Provider |
| TTS | Volcengine TTS，可扩展其他引擎 |
| 渲染 | Manim、Remotion |

## 目录结构

```text
.
├── backend/                 # FastAPI 后端
│   ├── app/
│   │   ├── api/             # 路由层
│   │   ├── models/          # SQLAlchemy ORM 模型
│   │   ├── schemas/         # Pydantic Schema
│   │   ├── engines/         # AI / TTS / Render 可插拔引擎
│   │   ├── services/        # 业务服务与校验逻辑
│   │   ├── workflows/       # Temporal Workflow 与 Activities
│   │   ├── workers/         # 叙事、代码、渲染 Worker
│   │   ├── config.py        # 后端配置
│   │   └── main.py          # FastAPI 入口
│   ├── alembic/             # 数据库迁移
│   ├── tests/               # 后端测试
│   └── sql/                 # 初始化 SQL
├── frontend/                # React + Vite 前端
│   └── src/
│       ├── pages/           # 页面
│       ├── components/      # 业务组件与 UI 组件
│       ├── hooks/           # TanStack Query hooks
│       ├── lib/             # API 与工具函数
│       └── types/           # 前后端共享语义的 TS 类型
├── remotion-template/       # Remotion 渲染模板
├── temporal-config/         # Temporal 本地配置
├── docs/                    # PRD、技术方案与迭代设计文档
├── docker-compose.yml       # 本地基础设施 + backend/worker/frontend 容器
├── backend/Dockerfile       # 后端/Worker 镜像（含 manim 系统依赖）
└── Makefile                 # 常用开发命令
```

## 环境要求

- Docker / Docker Compose

`backend`、`worker`、`frontend` 都是 `docker-compose.yml` 里的常规服务，依赖（Python 3.12 / uv / manim 的系统库、Node 22 / pnpm）都装在容器镜像和容器卷里，**宿主机不需要安装 Python / uv / Node / pnpm**。这也是为了兼容老旧 glibc 的宿主机（例如 CentOS 7）——较新版本的 Node 与部分 Python 原生扩展（manim 的 `glcontext`/`moderngl`）都要求 glibc ≥ 2.28，装不上。

如果宿主机 glibc 较新（Mac、较新的 Linux 发行版）且已经装好 `uv` / Node 24+ / pnpm 10+，也可以不走容器、直接在宿主机跑 `uv run` / `pnpm` 命令，两种方式不冲突。在 Codex 沙箱环境中运行命令时，`PATH` 可能不包含 `uv` 和 `pnpm`，需要使用绝对路径或显式注入 Node 路径：

```bash
~/.local/bin/uv run pytest tests/ -v
PATH="$HOME/.nvm/versions/node/v24.11.0/bin:$PATH" pnpm build
```

## 环境变量

后端配置文件位于 `backend/.env`，可从示例复制：

```bash
cp backend/.env.example backend/.env
```

常用后端变量：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql+asyncpg://app:password@localhost:5432/video_workflow` | FastAPI 异步数据库连接 |
| `DATABASE_SYNC_URL` | `postgresql+psycopg2://app:password@localhost:5432/video_workflow` | Worker 同步数据库连接 |
| `TEMPORAL_ADDRESS` | `localhost:7233` | Temporal 服务地址 |
| `TEMPORAL_TASK_QUEUE` | `video-production` | Temporal Task Queue |
| `API_KEY` | `dev-api-key-change-in-prod` | 后端 API Key |
| `MINIO_ENDPOINT` | `localhost:9000` | MinIO/S3 Endpoint（容器内部访问，docker-compose 会覆盖为 `minio:9000`） |
| `MINIO_PUBLIC_ENDPOINT` | `localhost:9000` | 生成预签名 URL 用，必须是浏览器可访问的地址（生产环境填 nginx 反代域名） |
| `MINIO_PUBLIC_SECURE` | `false` | 预签名 URL 是否用 https，生产环境经 nginx 反代时应设为 `true` |
| `AI_PROVIDER` | `deepseek` | 当前默认 AI Provider |
| `TTS_ENGINE` | `volcengine` | 当前默认 TTS 引擎 |
| `REMOTION_TEMPLATE_DIR` | `remotion-template` | Remotion 模板目录 |

前端配置文件位于 `frontend/.env`，可从示例复制：

```bash
cp frontend/.env.example frontend/.env
```

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_API_KEY=dev-api-key-change-in-prod
```

## 本地开发与生产容器部署的差异

本项目本地用 `docker-compose` 起一套（服务名互相直连），生产环境通常还会在前面挂一层 nginx 做域名反代，两者在几个地方容易踩坑：

### MinIO 预签名 URL：容器内网地址 vs 浏览器可访问地址

- `MINIO_ENDPOINT`：backend/worker 容器用它直连 MinIO 做实际的上传/下载。`docker-compose.yml` 会把它覆盖为容器网络里的服务名 `minio:9000`——这个名字宿主机和浏览器都解析不了，是正常现象，不用改。
- `MINIO_PUBLIC_ENDPOINT` / `MINIO_PUBLIC_SECURE`：只用于生成预签名 URL（`GET /api/projects/:id/video-url` 等），必须填**浏览器能访问到的地址**：
  - 本地开发：`localhost:9000`，`MINIO_PUBLIC_SECURE=false`。
  - 生产部署：nginx 反代出去的公网域名（例如 `ai-video-s3.zero-zero.cc`），`MINIO_PUBLIC_SECURE=true`。需要额外给这个域名建一条 nginx server block 反代到 MinIO 的 9000 端口，并在 DNS 加一条记录指向服务器公网 IP，否则前端拿到的视频/音频链接在浏览器里打不开。
- `backend/app/storage.py` 生成预签名 URL 时显式传了 `region="us-east-1"`：MinIO SDK 如果不知道 region，会反过来对 `MINIO_PUBLIC_ENDPOINT` 发一次真实的 `GetBucketLocation` 请求去探测；这个地址在容器网络里往往连不通（是给浏览器用的，不是给容器用的），不写死 region 会导致该接口 500。

### Remotion 渲染依赖的系统库

- `backend/Dockerfile` 为 Remotion headless Chrome 装了一批系统共享库（`libnss3`/`libnspr4`/`libatk` 等）。这是容器构建里必需的一步——如果之后升级基础镜像或换镜像，记得同步这批依赖，否则渲染会报 `error while loading shared libraries: libnspr4.so`。
- 如果不走 docker-compose、直接在宿主机跑渲染，需要自己装好这些库，或者继续用容器渲染。

### 前端访问后端 API 的方式

- 本地开发：`frontend/.env` 设 `VITE_API_BASE_URL=http://localhost:8000`，前端和后端是不同端口，走跨域请求。
- 生产部署：`VITE_API_BASE_URL` 留空，前端请求走相对路径 `/api/...`，由 nginx 按 `location /api` 反代到后端容器，天然同源，不需要处理 CORS。
- 如果生产环境前端和后端不同域部署，需要把后端 `CORS_ORIGINS` 加上前端的公网域名，否则浏览器会拦截跨域请求。

### 需要手动同步的密钥与域名

- `API_KEY`（后端）与 `VITE_API_KEY`（前端）默认是 `dev-api-key-change-in-prod`，生产环境必须改成随机值，且两边要保持一致。
- 生产环境新增/变更任何对外域名（例如上面的 MinIO 反代子域名）都要同步四件事：nginx 加 server block、DNS 加记录、对应 `.env` 配置更新、重启/reload 相关服务，四者缺一都会导致链路断在某一环。

## 快速启动

`backend`（uvicorn --reload）、`worker`、`frontend`（vite）都是 `docker-compose.yml` 里的常规服务，源码通过 volume 挂载、容器内热重载；依赖（`uv sync` / `pnpm install`）在容器启动时自动执行并缓存到容器卷里，不需要在宿主机单独安装。

1. 一条命令启动全部服务：

```bash
make up
```

服务端口：

| 服务 | 地址 |
| --- | --- |
| PostgreSQL | `localhost:5432` |
| Temporal | `localhost:7233` |
| Temporal UI | http://localhost:8080 |
| MinIO API | `localhost:9000` |
| MinIO Console | http://localhost:9001 |
| 后端 | http://localhost:8000 |
| 前端 | http://localhost:5173 |

2. 执行数据库迁移：

```bash
make migrate
```

如需导入初始化 SQL：

```bash
make init-db
```

启动后访问：

- 前端：http://localhost:5173
- 后端健康检查：http://localhost:8000/health
- OpenAPI 文档：http://localhost:8000/docs
- Temporal UI：http://localhost:8080

只想在前台跟踪某一个服务的日志（Ctrl-C 只会停掉这一个，不影响其它已在后台运行的服务）：

```bash
make dev-backend   # 或 make dev-worker / make dev-frontend
```

## 常用命令

```bash
# 启动 / 停止全部服务（postgres / temporal / minio / backend / worker / frontend）
make up
make down

# 数据库迁移
make migrate

# 前台跟踪单个服务日志
make dev-backend
make dev-worker
make dev-frontend

# 后端测试
docker-compose run --rm backend uv run pytest tests/ -v

# 前端构建
docker-compose run --rm frontend pnpm build

# 前端 lint
docker-compose run --rm frontend pnpm lint
```

## 核心工作流

```mermaid
stateDiagram-v2
    [*] --> draft: 创建项目
    draft --> narrative_generating: 触发叙事生成
    narrative_generating --> narrative_review: 生成成功
    narrative_generating --> narrative_failed: 生成失败
    narrative_failed --> narrative_generating: 重试
    narrative_review --> code_generating: 叙事审核通过
    narrative_review --> narrative_generating: 驳回
    code_generating --> code_review: 生成成功
    code_generating --> code_failed: 生成失败
    code_failed --> code_generating: 重试
    code_review --> video_generating: 代码审核通过
    code_review --> code_generating: 驳回代码
    code_review --> narrative_generating: 驳回叙事
    video_generating --> video_review: 渲染完成
    video_generating --> video_failed: 渲染失败
    video_failed --> code_review: 退回修复
    video_review --> published: 终审通过
    video_review --> code_review: 驳回代码
    video_review --> narrative_review: 驳回叙事
    draft --> abandoned: 废弃
    narrative_review --> abandoned: 废弃
    code_review --> abandoned: 废弃
    video_review --> abandoned: 废弃
    published --> [*]
    abandoned --> [*]
```

### 异步任务模式

耗时任务统一采用「Temporal Workflow + `worker_tasks` 表 + Worker 轮询 + Signal 回调」模式：

1. Workflow 进入生成或渲染阶段。
2. Activity 创建一条 `worker_tasks` 记录并返回。
3. Workflow 挂起等待 Signal。
4. Worker 轮询 `pending` 任务，执行 AI 生成、TTS 或渲染。
5. Worker 回写结果，并向 Workflow 发送完成 Signal。
6. Workflow 被唤醒，推进到下一个状态或失败重试。

## 主要页面

| 路径 | 说明 |
| --- | --- |
| `/topics` | 选题池、AI 头脑风暴、研究资料 |
| `/projects` | 视频项目列表 |
| `/projects/:id` | 项目详情、叙事审核、代码审核、视频审核 |
| `/projects/:id/performance` | 发布表现回流 |
| `/style-library` | 风格模板与 Prompt 组件 |
| `/ai-model-settings` | AI Provider、模型与业务场景配置 |
| `/ai-calls` | AI 调用记录、耗时和成本 |

## API 概览

所有业务 API 默认需要 `X-API-Key` 请求头。

| 前缀 | 说明 |
| --- | --- |
| `/api/topics` | 选题 CRUD、AI 头脑风暴、选题研究 |
| `/api/projects` | 项目 CRUD、版本读取、审核、重置、视频 URL、表现回流 |
| `/api/worker-tasks` | Worker 任务查询 |
| `/api/style-templates` | 风格模板管理 |
| `/api/prompt-components` | Prompt 组件管理与辅助生成 |
| `/api/ai-model-settings` | AI Provider、模型、业务模型配置 |
| `/api/ai-call-records` | AI 调用记录查询 |

## 数据与架构约束

- 不使用数据库外键约束，表间关联由应用层维护，`*_id` 字段仅表达关联意图。
- Temporal Workflow 是项目状态权威来源，`video_projects.status` 是给前端查询用的镜像字段。
- 镜头是最小内容原子单位，但渲染时必须整体提交，因为镜头间可能存在代码依赖。
- 三道人工审核闸门不可跳过：叙事审核、代码审核、视频审核。
- 审核驳回必须带结构化原因，系统按驳回类型路由到叙事重写、代码重写、代码修复或废弃。
- Tailwind v4 是当前前端的预期配置方式，通过 `frontend/src/index.css` 中的 `@import "tailwindcss"` 启用，不需要 `tailwind.config.js`。

## 测试

后端测试：

```bash
docker-compose run --rm backend uv run pytest tests/ -v
```

按模块运行：

```bash
docker-compose run --rm backend uv run pytest tests/test_projects.py -v
docker-compose run --rm backend uv run pytest tests/test_workflow.py -v
docker-compose run --rm backend uv run pytest tests/test_remotion_render_engine.py -v
```

前端构建检查：

```bash
docker-compose run --rm frontend pnpm build
```

## 文档

- [产品需求文档](docs/PRD_产品需求文档.md)
- [技术实现方案](docs/TECH_技术实现方案.md)
- [迭代设计与计划](docs/superpowers/)

## 开发提示

- 后端 `.env` 从 `backend/.env` 读取，前端 `.env` 从 `frontend/.env` 读取。
- `make dev-worker` 启动的是开发用合并 Worker，会同时运行 Temporal Worker、Narrative Worker、Code Worker 和 Render Worker。
- Remotion 渲染依赖 `remotion-template/node_modules`，`worker` 容器启动时会自动 `cd remotion-template && pnpm install`（依赖缓存在 `remotion_node_modules` 卷里），不需要在宿主机手动安装。
- 本地 MinIO 默认账号密码为 `minioadmin` / `minioadmin`。
- 如果更换 `API_KEY`，需要同步更新 `frontend/.env` 的 `VITE_API_KEY`。
- `backend`/`worker` 容器共用同一个 `backend_venv` 卷，`frontend` 容器使用 `frontend_node_modules` 卷；改了 `pyproject.toml`/`package.json` 后重新 `make up` 会自动 `uv sync`/`pnpm install`，一般不需要手动清卷。
- `docker-compose.yml` 里 `backend`/`worker` 的 `DATABASE_URL`/`TEMPORAL_ADDRESS`/`MINIO_ENDPOINT` 通过 `environment:` 覆盖为容器网络里的服务名（`postgres`/`temporal`/`minio`），会比 `backend/.env` 里写的 `localhost` 优先生效。
