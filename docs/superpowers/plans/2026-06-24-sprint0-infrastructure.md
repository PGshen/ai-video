# Sprint 0 — 基础设施搭建 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 搭建 AI 知识视频生产工作流平台的完整基础设施骨架，包含 docker-compose、DB migration、带 stub 路由的 FastAPI 应用、React/Vite 前端骨架和完整实现的 BaseWorker 框架。

**Architecture:** 后端为 FastAPI（async）+ SQLAlchemy 2.x（async for API / sync for Workers）+ Alembic + Temporal Python SDK；前端为 React 18 + Vite + TypeScript + TanStack Query v5 + shadcn/ui；基础设施（postgres / temporal / minio）通过 docker-compose 管理，应用服务本地直接运行。

**Tech Stack:** Python 3.12+, uv, FastAPI 0.115+, SQLAlchemy 2.0+, Alembic 1.13+, asyncpg, psycopg2-binary, temporalio 1.7+, pydantic 2.0+, pydantic-settings 2.0+, React 18, Vite 5, TypeScript 5, @tanstack/react-query 5, shadcn/ui, tailwindcss, react-router-dom 6

## Global Constraints

- 所有数据库表**不设外键约束**，关联关系在应用层维护
- API 鉴权：`X-API-Key` 请求头 vs 环境变量 `API_KEY`；`/health` 不需鉴权
- 所有 API stub handler 返回 `{"status": "TODO", "endpoint": "<METHOD> <path>"}`，HTTP 200
- `composite_score` 使用 PostgreSQL `GENERATED ALWAYS AS (...) STORED` 列
- 前端从 `VITE_API_KEY` 和 `VITE_API_BASE_URL` 读取配置
- BaseWorker 使用 sync SQLAlchemy（psycopg2）；FastAPI 使用 async SQLAlchemy（asyncpg）

---

## File Map

```
ai-video/
├── .gitignore
├── .env.example                          # 根目录环境变量模板
├── docker-compose.yml
├── Makefile
├── CLAUDE.md                             # harness 工程文档（Task 12）
├── backend/
│   ├── .env.example
│   ├── pyproject.toml                    # uv 管理
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   │       └── 0001_initial_schema.py
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_health.py               # Task 5
│   │   ├── test_api_stubs.py            # Task 7
│   │   └── test_base_worker.py          # Task 9
│   └── app/
│       ├── __init__.py
│       ├── config.py                     # Task 5
│       ├── db.py                         # Task 3（async + sync engines）
│       ├── auth.py                       # Task 5
│       ├── main.py                       # Task 5
│       ├── models/
│       │   ├── __init__.py              # re-exports all models
│       │   ├── topic.py                 # Task 3
│       │   ├── project.py               # Task 3
│       │   ├── script_version.py        # Task 3
│       │   ├── video_asset.py           # Task 3
│       │   ├── worker_task.py           # Task 3
│       │   ├── project_event.py         # Task 3
│       │   └── performance_record.py    # Task 3
│       ├── schemas/
│       │   ├── __init__.py
│       │   ├── topic.py                 # Task 6
│       │   ├── project.py               # Task 6
│       │   ├── review.py                # Task 6
│       │   └── worker_task.py           # Task 6
│       ├── api/
│       │   ├── __init__.py
│       │   ├── topics.py                # Task 7
│       │   ├── projects.py              # Task 7
│       │   ├── reviews.py               # Task 7
│       │   └── worker_tasks.py          # Task 7
│       ├── engines/
│       │   ├── render/
│       │   │   ├── __init__.py
│       │   │   └── base.py              # Task 8
│       │   ├── tts/
│       │   │   ├── __init__.py
│       │   │   └── base.py              # Task 8
│       │   └── ai/
│       │       ├── __init__.py
│       │       └── base.py              # Task 8
│       ├── workflows/
│       │   ├── __init__.py
│       │   ├── video_production.py      # Task 8
│       │   └── activities.py            # Task 8
│       └── workers/
│           ├── __init__.py
│           ├── base.py                  # Task 9（完整实现）
│           ├── script_worker.py         # Task 9（stub）
│           ├── render_worker.py         # Task 9（stub）
│           └── combined_worker.py       # Task 9（stub）
└── frontend/
    ├── .env.example
    ├── package.json                      # Task 10
    ├── vite.config.ts                    # Task 10
    ├── tsconfig.json                     # Task 10
    ├── index.html                        # Task 10
    ├── tailwind.config.ts                # Task 10
    ├── components.json                   # shadcn config（Task 10）
    └── src/
        ├── main.tsx                      # Task 11
        ├── App.tsx                       # Task 11（路由）
        ├── types/
        │   └── index.ts                 # Task 11（完整类型定义）
        ├── lib/
        │   └── api.ts                   # Task 11（fetch 封装）
        ├── hooks/
        │   ├── useTopics.ts             # Task 11
        │   ├── useProjects.ts           # Task 11
        │   └── useWorkerTasks.ts        # Task 11
        ├── components/
        │   ├── topics/                  # Task 11（空目录占位）
        │   ├── projects/                # Task 11
        │   ├── review/                  # Task 11
        │   └── ui/                      # shadcn 组件（Task 10）
        └── pages/
            ├── TopicsPage.tsx           # Task 11
            ├── ProjectsPage.tsx         # Task 11
            ├── ProjectDetailPage.tsx    # Task 11
            └── PerformancePage.tsx      # Task 11
```

---

## Task 1: Git init + Root infrastructure files

**Files:**
- Create: `.gitignore`
- Create: `docker-compose.yml`
- Create: `.env.example`
- Create: `Makefile`

**Interfaces:**
- Produces: `make up` 启动 docker-compose；`make down` 停止；`make migrate`、`make dev-backend`、`make dev-worker`、`make dev-frontend` 命令

- [ ] **Step 1: 初始化 git 仓库**

在 `/Users/peng/Me/Ai/ai-video` 目录执行：

```bash
cd /Users/peng/Me/Ai/ai-video
git init
```

Expected: `Initialized empty Git repository in .../ai-video/.git/`

- [ ] **Step 2: 创建 .gitignore**

```
# Python
__pycache__/
*.py[cod]
.venv/
*.egg-info/
dist/
.env
.pytest_cache/
.mypy_cache/

# Node
node_modules/
dist/
.env.local

# OS
.DS_Store
*.log

# Alembic
backend/alembic/versions/*.pyc

# Temporal
temporal_data/
```

保存为 `/Users/peng/Me/Ai/ai-video/.gitignore`

- [ ] **Step 3: 创建 docker-compose.yml**

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: video_workflow
      POSTGRES_USER: app
      POSTGRES_PASSWORD: ${DB_PASSWORD:-password}
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app -d video_workflow"]
      interval: 5s
      timeout: 5s
      retries: 5

  temporal:
    image: temporalio/auto-setup:latest
    environment:
      DB: postgres12
      DB_PORT: 5432
      POSTGRES_USER: app
      POSTGRES_PWD: ${DB_PASSWORD:-password}
      POSTGRES_SEEDS: postgres
      DYNAMIC_CONFIG_FILE_PATH: config/dynamicconfig/development-sql.yaml
    depends_on:
      postgres:
        condition: service_healthy
    ports:
      - "7233:7233"

  temporal-ui:
    image: temporalio/ui:latest
    environment:
      TEMPORAL_ADDRESS: temporal:7233
      TEMPORAL_CORS_ORIGINS: http://localhost:3000
    depends_on:
      - temporal
    ports:
      - "8080:8080"

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ACCESS_KEY:-minioadmin}
      MINIO_ROOT_PASSWORD: ${MINIO_SECRET_KEY:-minioadmin}
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio_data:/data

volumes:
  pgdata:
  minio_data:
```

保存为 `/Users/peng/Me/Ai/ai-video/docker-compose.yml`

- [ ] **Step 4: 创建根目录 .env.example**

```env
# PostgreSQL
DB_PASSWORD=password

# Temporal（共用 postgres 实例）
# Temporal 使用 POSTGRES_USER=app, POSTGRES_PWD=password，DB 名为 temporal（auto-setup 自动创建）

# MinIO
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
```

保存为 `/Users/peng/Me/Ai/ai-video/.env.example`

- [ ] **Step 5: 创建 Makefile**

```makefile
.PHONY: up down migrate dev-backend dev-worker dev-frontend

up:
	docker-compose up -d

down:
	docker-compose down

migrate:
	cd backend && uv run alembic upgrade head

dev-backend:
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-worker:
	cd backend && uv run python -m app.workers.combined_worker

dev-frontend:
	cd frontend && npm run dev
```

保存为 `/Users/peng/Me/Ai/ai-video/Makefile`

- [ ] **Step 6: 验证 docker-compose 启动**

```bash
cd /Users/peng/Me/Ai/ai-video
docker-compose up -d
docker-compose ps
```

Expected: 4 个服务状态均为 `Up` 或 `running`（postgres / temporal / temporal-ui / minio）。Temporal 可能需要 30-60 秒初始化。

```bash
docker-compose logs temporal | tail -5
```

Expected: 看到 `started` 或 `All services are healthy` 字样。

- [ ] **Step 7: Commit**

```bash
cd /Users/peng/Me/Ai/ai-video
git add .gitignore docker-compose.yml .env.example Makefile
git commit -m "feat: add root infrastructure files (docker-compose, Makefile)"
```

---

## Task 2: Backend Python project scaffold

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/.env.example`
- Create: `backend/app/__init__.py`（及所有子目录 `__init__.py`）

**Interfaces:**
- Produces: `uv sync` 安装依赖；`backend/.venv` 虚拟环境

- [ ] **Step 1: 安装 uv（如果未安装）**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv --version
```

Expected: 输出版本号，如 `uv 0.5.x`

- [ ] **Step 2: 创建 backend/pyproject.toml**

```toml
[project]
name = "ai-video-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "sqlalchemy>=2.0",
    "alembic>=1.13",
    "asyncpg>=0.30",
    "psycopg2-binary>=2.9",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
    "temporalio>=1.7",
    "python-dotenv>=1.0",
]

[tool.uv]
dev-dependencies = [
    "pytest>=8",
    "pytest-asyncio>=0.24",
    "httpx>=0.27",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

保存为 `/Users/peng/Me/Ai/ai-video/backend/pyproject.toml`

- [ ] **Step 3: 安装依赖**

```bash
cd /Users/peng/Me/Ai/ai-video/backend
uv sync
```

Expected: 创建 `.venv/`，输出 `All packages installed`

- [ ] **Step 4: 创建 backend/.env.example**

```env
DATABASE_URL=postgresql+asyncpg://app:password@localhost:5432/video_workflow
DATABASE_SYNC_URL=postgresql+psycopg2://app:password@localhost:5432/video_workflow
TEMPORAL_ADDRESS=localhost:7233
TEMPORAL_TASK_QUEUE=video-production
API_KEY=dev-api-key-change-in-prod
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
ANTHROPIC_API_KEY=
```

保存为 `/Users/peng/Me/Ai/ai-video/backend/.env.example`

同时从 `.env.example` 复制一份 `.env`（用于本地开发）：

```bash
cp /Users/peng/Me/Ai/ai-video/backend/.env.example /Users/peng/Me/Ai/ai-video/backend/.env
```

- [ ] **Step 5: 创建所有 app 子目录和 __init__.py**

```bash
cd /Users/peng/Me/Ai/ai-video/backend
mkdir -p app/api app/models app/schemas app/engines/render app/engines/tts app/engines/ai app/workflows app/workers
touch app/__init__.py
touch app/api/__init__.py
touch app/models/__init__.py
touch app/schemas/__init__.py
touch app/engines/__init__.py
touch app/engines/render/__init__.py
touch app/engines/tts/__init__.py
touch app/engines/ai/__init__.py
touch app/workflows/__init__.py
touch app/workers/__init__.py
mkdir -p tests
touch tests/__init__.py
```

- [ ] **Step 6: Commit**

```bash
cd /Users/peng/Me/Ai/ai-video
git add backend/
git commit -m "feat: scaffold backend Python project with uv"
```

---

## Task 3: SQLAlchemy models + db.py

**Files:**
- Create: `backend/app/db.py`
- Create: `backend/app/models/topic.py`
- Create: `backend/app/models/project.py`
- Create: `backend/app/models/script_version.py`
- Create: `backend/app/models/video_asset.py`
- Create: `backend/app/models/worker_task.py`
- Create: `backend/app/models/project_event.py`
- Create: `backend/app/models/performance_record.py`
- Modify: `backend/app/models/__init__.py`

**Interfaces:**
- Produces: `Base`（DeclarativeBase），`get_async_session()`（FastAPI Depends），`get_sync_session()`（Worker 使用）
- Produces: 7 个 ORM model 类

- [ ] **Step 1: 创建 app/db.py**

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy import create_engine
from typing import AsyncGenerator
from app.config import settings


class Base(DeclarativeBase):
    pass


# Async engine for FastAPI
async_engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


# Sync engine for Workers
sync_engine = create_engine(settings.DATABASE_SYNC_URL, echo=False)
SyncSessionLocal = sessionmaker(sync_engine)


def get_sync_session():
    return SyncSessionLocal()
```

保存为 `/Users/peng/Me/Ai/ai-video/backend/app/db.py`

> 注意：`db.py` 导入了 `app.config`，config 在 Task 5 创建。Task 3 的模型文件不需要运行，只需语法正确。

- [ ] **Step 2: 先创建 config.py 占位（Task 5 会完整实现）**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://app:password@localhost:5432/video_workflow"
    DATABASE_SYNC_URL: str = "postgresql+psycopg2://app:password@localhost:5432/video_workflow"
    TEMPORAL_ADDRESS: str = "localhost:7233"
    TEMPORAL_TASK_QUEUE: str = "video-production"
    API_KEY: str = "dev-api-key-change-in-prod"
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    ANTHROPIC_API_KEY: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
```

保存为 `/Users/peng/Me/Ai/ai-video/backend/app/config.py`

- [ ] **Step 3: 创建 models/topic.py**

```python
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Text, SmallInteger, Float, Boolean, Computed, DateTime
from sqlalchemy.dialects.postgresql import UUID as PGUUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base


def utcnow():
    return datetime.now(timezone.utc)


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    score_counterintuitive: Mapped[Optional[int]] = mapped_column(SmallInteger)
    score_defensibility: Mapped[Optional[int]] = mapped_column(SmallInteger)
    score_visual: Mapped[Optional[int]] = mapped_column(SmallInteger)
    score_freshness: Mapped[Optional[int]] = mapped_column(SmallInteger)
    composite_score: Mapped[Optional[float]] = mapped_column(
        Float,
        Computed(
            "(score_counterintuitive + score_defensibility + score_visual + score_freshness) / 4.0",
            persisted=True,
        ),
    )
    performance_score: Mapped[Optional[float]] = mapped_column(Float)
    tags: Mapped[Optional[list]] = mapped_column(ARRAY(String(50)))
    needs_recheck: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
```

保存为 `/Users/peng/Me/Ai/ai-video/backend/app/models/topic.py`

- [ ] **Step 4: 创建 models/project.py**

```python
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, SmallInteger, DateTime
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base


def utcnow():
    return datetime.now(timezone.utc)


class VideoProject(Base):
    __tablename__ = "video_projects"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    render_engine: Mapped[str] = mapped_column(String(20), nullable=False)
    tts_voice: Mapped[str] = mapped_column(String(50), nullable=False)
    aspect_ratio: Mapped[str] = mapped_column(String(20), nullable=False)
    current_script_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PGUUID(as_uuid=True)
    )
    current_video_asset_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PGUUID(as_uuid=True)
    )
    temporal_workflow_id: Mapped[Optional[str]] = mapped_column(String(100))
    retry_count: Mapped[int] = mapped_column(SmallInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
```

保存为 `/Users/peng/Me/Ai/ai-video/backend/app/models/project.py`

- [ ] **Step 5: 创建 models/script_version.py**

```python
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base


def utcnow():
    return datetime.now(timezone.utc)


class ScriptVersion(Base):
    __tablename__ = "script_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    scenes: Mapped[Optional[dict]] = mapped_column(JSONB)
    fact_checks: Mapped[Optional[dict]] = mapped_column(JSONB)
    render_engine: Mapped[str] = mapped_column(String(20), nullable=False)
    ai_model: Mapped[Optional[str]] = mapped_column(String(50))
    rejection_context: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
```

保存为 `/Users/peng/Me/Ai/ai-video/backend/app/models/script_version.py`

- [ ] **Step 6: 创建 models/video_asset.py**

```python
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Float, DateTime
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base


def utcnow():
    return datetime.now(timezone.utc)


class VideoAsset(Base):
    __tablename__ = "video_assets"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    script_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PGUUID(as_uuid=True)
    )
    video_file_key: Mapped[Optional[str]] = mapped_column(String(500))
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float)
    resolution: Mapped[Optional[str]] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="rendering")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
```

保存为 `/Users/peng/Me/Ai/ai-video/backend/app/models/video_asset.py`

- [ ] **Step 7: 创建 models/worker_task.py**

```python
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, SmallInteger, DateTime
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base


def utcnow():
    return datetime.now(timezone.utc)


class WorkerTask(Base):
    __tablename__ = "worker_tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    script_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PGUUID(as_uuid=True)
    )
    task_type: Mapped[str] = mapped_column(String(30), nullable=False)
    engine: Mapped[Optional[str]] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    input_payload: Mapped[Optional[dict]] = mapped_column(JSONB)
    output_payload: Mapped[Optional[dict]] = mapped_column(JSONB)
    retry_count: Mapped[int] = mapped_column(SmallInteger, default=0)
    max_retries: Mapped[int] = mapped_column(SmallInteger, default=3)
    temporal_workflow_id: Mapped[Optional[str]] = mapped_column(String(100))
    signal_name: Mapped[Optional[str]] = mapped_column(String(50))
    worker_id: Mapped[Optional[str]] = mapped_column(String(100))
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
```

保存为 `/Users/peng/Me/Ai/ai-video/backend/app/models/worker_task.py`

- [ ] **Step 8: 创建 models/project_event.py**

```python
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import BigInteger, String, DateTime
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base
import uuid


def utcnow():
    return datetime.now(timezone.utc)


class ProjectEvent(Base):
    __tablename__ = "project_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    from_status: Mapped[Optional[str]] = mapped_column(String(30))
    to_status: Mapped[Optional[str]] = mapped_column(String(30))
    actor: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
```

保存为 `/Users/peng/Me/Ai/ai-video/backend/app/models/project_event.py`

- [ ] **Step 9: 创建 models/performance_record.py**

```python
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Integer, Float, Text, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base


def utcnow():
    return datetime.now(timezone.utc)


class PerformanceRecord(Base):
    __tablename__ = "performance_records"
    __table_args__ = (UniqueConstraint("project_id", name="uq_performance_records_project_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    platform: Mapped[str] = mapped_column(String(30), nullable=False)
    views: Mapped[Optional[int]] = mapped_column(Integer)
    completion_rate: Mapped[Optional[float]] = mapped_column(Float)
    likes: Mapped[Optional[int]] = mapped_column(Integer)
    favorites: Mapped[Optional[int]] = mapped_column(Integer)
    comment_tags: Mapped[Optional[list]] = mapped_column(ARRAY(String(30)))
    comment_summary: Mapped[Optional[str]] = mapped_column(Text)
    recorded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
```

保存为 `/Users/peng/Me/Ai/ai-video/backend/app/models/performance_record.py`

- [ ] **Step 10: 更新 models/__init__.py**

```python
from app.models.topic import Topic
from app.models.project import VideoProject
from app.models.script_version import ScriptVersion
from app.models.video_asset import VideoAsset
from app.models.worker_task import WorkerTask
from app.models.project_event import ProjectEvent
from app.models.performance_record import PerformanceRecord

__all__ = [
    "Topic",
    "VideoProject",
    "ScriptVersion",
    "VideoAsset",
    "WorkerTask",
    "ProjectEvent",
    "PerformanceRecord",
]
```

保存为 `/Users/peng/Me/Ai/ai-video/backend/app/models/__init__.py`

- [ ] **Step 11: 验证语法**

```bash
cd /Users/peng/Me/Ai/ai-video/backend
uv run python -c "from app.models import Topic, VideoProject, ScriptVersion, VideoAsset, WorkerTask, ProjectEvent, PerformanceRecord; print('OK')"
```

Expected: `OK`

- [ ] **Step 12: Commit**

```bash
cd /Users/peng/Me/Ai/ai-video
git add backend/app/
git commit -m "feat: add SQLAlchemy models and db session factories"
```

---

## Task 4: Alembic setup + initial migration

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`
- Create: `backend/alembic/versions/0001_initial_schema.py`

**Interfaces:**
- Produces: `uv run alembic upgrade head` 建全 7 张表 + 所有索引

- [ ] **Step 1: 初始化 Alembic**

```bash
cd /Users/peng/Me/Ai/ai-video/backend
uv run alembic init alembic
```

Expected: 创建 `alembic/` 目录和 `alembic.ini`

- [ ] **Step 2: 修改 alembic.ini — 更新 sqlalchemy.url**

打开 `backend/alembic.ini`，找到这一行：
```
sqlalchemy.url = driver://user:pass@localhost/dbname
```
替换为：
```
sqlalchemy.url = postgresql+psycopg2://app:password@localhost:5432/video_workflow
```

- [ ] **Step 3: 替换 alembic/env.py**

用以下内容完整替换 `backend/alembic/env.py`：

```python
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.config import settings
from app.db import Base
import app.models  # noqa: F401 — 触发所有 model 导入，确保 metadata 完整

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_SYNC_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

保存为 `/Users/peng/Me/Ai/ai-video/backend/alembic/env.py`

- [ ] **Step 4: 创建初始 migration**

```bash
cd /Users/peng/Me/Ai/ai-video/backend
uv run alembic revision --autogenerate -m "initial_schema"
```

Expected: 在 `alembic/versions/` 下生成一个新文件，如 `xxxx_initial_schema.py`

- [ ] **Step 5: 检查并补全生成的 migration**

Alembic autogenerate 可能无法处理 `Computed` 列和 `GIN` 索引。打开生成的文件，在 `upgrade()` 函数末尾追加以下 SQL（在 `op.create_table()` 调用之后）：

```python
# 在 upgrade() 函数中，op.create_table() 之后添加：
from sqlalchemy import text

def upgrade() -> None:
    # ... autogenerated op.create_table() calls ...

    # Indexes for topics
    op.create_index("idx_topics_status", "topics", ["status"])
    op.create_index("idx_topics_composite_score", "topics", ["composite_score"], postgresql_ops={"composite_score": "DESC NULLS LAST"})
    op.execute(text("CREATE INDEX IF NOT EXISTS idx_topics_tags ON topics USING GIN(tags)"))

    # Indexes for video_projects
    op.create_index("idx_projects_status", "video_projects", ["status"])
    op.create_index("idx_projects_topic_id", "video_projects", ["topic_id"])

    # Indexes for script_versions
    op.create_index("idx_script_versions_project_id", "script_versions", ["project_id"])

    # Indexes for video_assets
    op.create_index("idx_video_assets_project_id", "video_assets", ["project_id"])

    # Indexes for worker_tasks
    op.create_index("idx_worker_tasks_status", "worker_tasks", ["status"])
    op.create_index("idx_worker_tasks_project_id", "worker_tasks", ["project_id"])
    op.create_index("idx_worker_tasks_type_status", "worker_tasks", ["task_type", "status"])

    # Indexes for project_events
    op.create_index("idx_project_events_project_id", "project_events", ["project_id"])
    op.create_index("idx_project_events_created_at", "project_events", ["created_at"], postgresql_ops={"created_at": "DESC"})
```

对应地在 `downgrade()` 中删除这些索引：

```python
def downgrade() -> None:
    op.drop_index("idx_project_events_created_at", "project_events")
    op.drop_index("idx_project_events_project_id", "project_events")
    op.drop_index("idx_worker_tasks_type_status", "worker_tasks")
    op.drop_index("idx_worker_tasks_project_id", "worker_tasks")
    op.drop_index("idx_worker_tasks_status", "worker_tasks")
    op.drop_index("idx_video_assets_project_id", "video_assets")
    op.drop_index("idx_script_versions_project_id", "script_versions")
    op.drop_index("idx_projects_topic_id", "video_projects")
    op.drop_index("idx_projects_status", "video_projects")
    op.execute(text("DROP INDEX IF EXISTS idx_topics_tags"))
    op.drop_index("idx_topics_composite_score", "topics")
    op.drop_index("idx_topics_status", "topics")
    # ... autogenerated op.drop_table() calls ...
```

- [ ] **Step 6: 执行 migration**

确保 docker-compose 已启动（postgres 运行中）：

```bash
cd /Users/peng/Me/Ai/ai-video
make migrate
```

Expected: 输出类似：
```
INFO  [alembic.runtime.migration] Running upgrade  -> xxxx, initial_schema
```

- [ ] **Step 7: 验证表已创建**

```bash
docker exec -it $(docker-compose ps -q postgres) psql -U app -d video_workflow -c "\dt"
```

Expected: 列出 7 张表：`performance_records`, `project_events`, `script_versions`, `topics`, `video_assets`, `video_projects`, `worker_tasks`

- [ ] **Step 8: Commit**

```bash
cd /Users/peng/Me/Ai/ai-video
git add backend/alembic/ backend/alembic.ini
git commit -m "feat: add Alembic setup and initial schema migration (7 tables)"
```

---

## Task 5: FastAPI app core (config, auth, main) + /health test

**Files:**
- Modify: `backend/app/config.py`（Task 3 已创建占位，此处无需修改）
- Create: `backend/app/auth.py`
- Create: `backend/app/main.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_health.py`

**Interfaces:**
- Produces: `verify_api_key` FastAPI Depends；`app` FastAPI 实例；`GET /health` 端点

- [ ] **Step 1: 写 test_health.py 测试（TDD — 先写测试）**

```python
# backend/tests/test_health.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_no_auth_required():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_protected_endpoint_without_key_returns_401():
    response = client.get("/api/topics")
    assert response.status_code == 401


def test_protected_endpoint_with_wrong_key_returns_401():
    response = client.get("/api/topics", headers={"X-API-Key": "wrong-key"})
    assert response.status_code == 401
```

保存为 `/Users/peng/Me/Ai/ai-video/backend/tests/test_health.py`

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd /Users/peng/Me/Ai/ai-video/backend
uv run pytest tests/test_health.py -v
```

Expected: FAIL — `ImportError` 因为 `app.main` 还不存在

- [ ] **Step 3: 创建 app/auth.py**

```python
from fastapi import Header, HTTPException
from app.config import settings


async def verify_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> None:
    if x_api_key != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
```

保存为 `/Users/peng/Me/Ai/ai-video/backend/app/auth.py`

- [ ] **Step 4: 创建 app/main.py**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="AI Video Workflow Platform", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


# Routers are registered in Task 7
```

保存为 `/Users/peng/Me/Ai/ai-video/backend/app/main.py`

- [ ] **Step 5: 创建 tests/conftest.py**

```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock
from app.main import app
from app.db import get_async_session
from app.config import settings


@pytest.fixture
def client():
    async def mock_session():
        yield MagicMock()

    app.dependency_overrides[get_async_session] = mock_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    return {"X-API-Key": settings.API_KEY}
```

保存为 `/Users/peng/Me/Ai/ai-video/backend/tests/conftest.py`

- [ ] **Step 6: 更新 test_health.py 使用 conftest fixtures**

```python
# backend/tests/test_health.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_no_auth_required():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_protected_endpoint_without_key_returns_401(client):
    response = client.get("/api/topics")
    assert response.status_code == 401


def test_protected_endpoint_with_wrong_key_returns_401(client):
    response = client.get("/api/topics", headers={"X-API-Key": "wrong-key"})
    assert response.status_code == 401
```

- [ ] **Step 7: 运行测试，确认通过**

```bash
cd /Users/peng/Me/Ai/ai-video/backend
uv run pytest tests/test_health.py -v
```

Expected:
```
tests/test_health.py::test_health_no_auth_required PASSED
tests/test_health.py::test_protected_endpoint_without_key_returns_401 PASSED
tests/test_health.py::test_protected_endpoint_with_wrong_key_returns_401 PASSED
```

> Note: `test_protected_endpoint_*` 测试此时会 PASS 因为 `/api/topics` 路由还不存在返回 404，不是 401。稍后 Task 7 注册路由后这些测试才能完全通过。先确保无 import error 即可。

- [ ] **Step 8: Commit**

```bash
cd /Users/peng/Me/Ai/ai-video
git add backend/app/auth.py backend/app/main.py backend/tests/
git commit -m "feat: add FastAPI app core with API Key auth and /health endpoint"
```

---

## Task 6: Pydantic schemas

**Files:**
- Create: `backend/app/schemas/topic.py`
- Create: `backend/app/schemas/project.py`
- Create: `backend/app/schemas/review.py`
- Create: `backend/app/schemas/worker_task.py`
- Modify: `backend/app/schemas/__init__.py`

**Interfaces:**
- Produces: 所有 API 的 Request/Response Pydantic 模型，字段与技术方案附录 13 一致

- [ ] **Step 1: 创建 schemas/topic.py**

```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID


class TopicScores(BaseModel):
    counterintuitive: Optional[int] = Field(None, ge=1, le=5)
    defensibility: Optional[int] = Field(None, ge=1, le=5)
    visual: Optional[int] = Field(None, ge=1, le=5)
    freshness: Optional[int] = Field(None, ge=1, le=5)


class TopicBase(BaseModel):
    title: str
    description: Optional[str] = None
    source: str
    tags: list[str] = []
    scores: TopicScores = TopicScores()


class TopicCreate(TopicBase):
    pass


class TopicUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    source: Optional[str] = None
    tags: Optional[list[str]] = None
    scores: Optional[TopicScores] = None
    status: Optional[str] = None


class TopicResponse(BaseModel):
    id: UUID
    title: str
    description: Optional[str]
    source: str
    status: str
    scores: TopicScores
    composite_score: Optional[float]
    performance_score: Optional[float]
    tags: list[str]
    needs_recheck: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TopicListResponse(BaseModel):
    items: list[TopicResponse]
    total: int


class BrainstormRequest(BaseModel):
    topic_direction: str
    count: int = Field(default=5, ge=1, le=20)


class BrainstormResponse(BaseModel):
    candidates: list[dict]
```

保存为 `/Users/peng/Me/Ai/ai-video/backend/app/schemas/topic.py`

- [ ] **Step 2: 创建 schemas/project.py**

```python
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID


class ProjectCreate(BaseModel):
    topic_id: UUID
    render_engine: str
    tts_voice: str
    aspect_ratio: str


class SceneSchema(BaseModel):
    scene_index: int
    narration: str
    description: str
    code: str
    estimated_duration_seconds: float


class FactCheckItemSchema(BaseModel):
    claim_text: str
    scene_index: int
    source_url: Optional[str]
    source_description: str
    confidence: str
    is_hypothesis: bool
    assumptions: Optional[str]
    controversy: Optional[str]
    reviewer_verdict: Optional[str]
    reviewer_note: Optional[str]


class ScriptVersionSchema(BaseModel):
    id: UUID
    project_id: UUID
    version_number: int
    scenes: Optional[list[SceneSchema]]
    fact_checks: Optional[list[FactCheckItemSchema]]
    render_engine: str
    ai_model: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class VideoAssetSchema(BaseModel):
    id: UUID
    project_id: UUID
    video_file_key: Optional[str]
    duration_seconds: Optional[float]
    resolution: Optional[str]
    status: str

    model_config = {"from_attributes": True}


class ProjectResponse(BaseModel):
    id: UUID
    topic_id: UUID
    status: str
    render_engine: str
    tts_voice: str
    aspect_ratio: str
    retry_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectDetailResponse(ProjectResponse):
    current_script_version: Optional[ScriptVersionSchema]
    current_video_asset: Optional[VideoAssetSchema]


class ProjectListResponse(BaseModel):
    items: list[ProjectResponse]
    total: int


class ScriptVersionListResponse(BaseModel):
    items: list[ScriptVersionSchema]


class EventSchema(BaseModel):
    id: int
    project_id: UUID
    event_type: str
    from_status: Optional[str]
    to_status: Optional[str]
    actor: str
    payload: Optional[dict]
    created_at: datetime

    model_config = {"from_attributes": True}


class EventListResponse(BaseModel):
    items: list[EventSchema]


class PerformanceCreate(BaseModel):
    platform: str
    views: Optional[int] = None
    completion_rate: Optional[float] = None
    likes: Optional[int] = None
    favorites: Optional[int] = None
    comment_tags: list[str] = []
    comment_summary: Optional[str] = None


class PerformanceResponse(BaseModel):
    id: UUID
    project_id: UUID
    platform: str
    views: Optional[int]
    completion_rate: Optional[float]
    likes: Optional[int]
    favorites: Optional[int]
    comment_tags: list[str]
    comment_summary: Optional[str]

    model_config = {"from_attributes": True}


class PreviewUrlResponse(BaseModel):
    url: str
    expires_in_seconds: int
```

保存为 `/Users/peng/Me/Ai/ai-video/backend/app/schemas/project.py`

- [ ] **Step 3: 创建 schemas/review.py**

```python
from pydantic import BaseModel
from typing import Optional


class FactCheckVerdict(BaseModel):
    index: int
    verdict: str
    note: str = ""


class ReviewRequest(BaseModel):
    gate: str
    verdict: str
    rejection_type: Optional[str] = None
    rejection_detail: Optional[str] = None
    target_stage: Optional[str] = None
    fact_check_verdicts: Optional[list[FactCheckVerdict]] = None


class ReviewResponse(BaseModel):
    status: str
    project_id: str
```

保存为 `/Users/peng/Me/Ai/ai-video/backend/app/schemas/review.py`

- [ ] **Step 4: 创建 schemas/worker_task.py**

```python
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID


class WorkerTaskResponse(BaseModel):
    id: UUID
    project_id: UUID
    task_type: str
    engine: Optional[str]
    status: str
    retry_count: int
    max_retries: int
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class WorkerTaskListResponse(BaseModel):
    items: list[WorkerTaskResponse]
```

保存为 `/Users/peng/Me/Ai/ai-video/backend/app/schemas/worker_task.py`

- [ ] **Step 5: 更新 schemas/__init__.py**

```python
from app.schemas.topic import (
    TopicCreate, TopicUpdate, TopicResponse, TopicListResponse,
    BrainstormRequest, BrainstormResponse,
)
from app.schemas.project import (
    ProjectCreate, ProjectResponse, ProjectDetailResponse, ProjectListResponse,
    ScriptVersionListResponse, EventListResponse, PerformanceCreate,
    PerformanceResponse, PreviewUrlResponse,
)
from app.schemas.review import ReviewRequest, ReviewResponse
from app.schemas.worker_task import WorkerTaskResponse, WorkerTaskListResponse

__all__ = [
    "TopicCreate", "TopicUpdate", "TopicResponse", "TopicListResponse",
    "BrainstormRequest", "BrainstormResponse",
    "ProjectCreate", "ProjectResponse", "ProjectDetailResponse", "ProjectListResponse",
    "ScriptVersionListResponse", "EventListResponse", "PerformanceCreate",
    "PerformanceResponse", "PreviewUrlResponse",
    "ReviewRequest", "ReviewResponse",
    "WorkerTaskResponse", "WorkerTaskListResponse",
]
```

- [ ] **Step 6: 验证 schemas 导入正常**

```bash
cd /Users/peng/Me/Ai/ai-video/backend
uv run python -c "from app.schemas import TopicCreate, ProjectCreate, ReviewRequest, WorkerTaskResponse; print('OK')"
```

Expected: `OK`

- [ ] **Step 7: Commit**

```bash
cd /Users/peng/Me/Ai/ai-video
git add backend/app/schemas/
git commit -m "feat: add Pydantic schemas for all API endpoints"
```

---

## Task 7: API route stubs + tests

**Files:**
- Create: `backend/app/api/topics.py`
- Create: `backend/app/api/projects.py`
- Create: `backend/app/api/reviews.py`
- Create: `backend/app/api/worker_tasks.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_api_stubs.py`

**Interfaces:**
- Consumes: `verify_api_key` from `app.auth`；schemas from `app.schemas`
- Produces: 13 个 stub API endpoint，全部返回 `{"status": "TODO", "endpoint": "..."}`

- [ ] **Step 1: 写 test_api_stubs.py 测试（TDD — 先写）**

```python
# backend/tests/test_api_stubs.py
import pytest


STUB_ENDPOINTS = [
    ("GET", "/api/topics"),
    ("POST", "/api/topics"),
    ("POST", "/api/topics/brainstorm"),
    ("GET", "/api/projects"),
    ("POST", "/api/projects"),
    ("GET", "/api/worker-tasks"),
]

PROJECT_ID = "00000000-0000-0000-0000-000000000001"

PROJECT_STUB_ENDPOINTS = [
    ("GET", f"/api/projects/{PROJECT_ID}"),
    ("POST", f"/api/projects/{PROJECT_ID}/review"),
    ("GET", f"/api/projects/{PROJECT_ID}/script-versions"),
    ("GET", f"/api/projects/{PROJECT_ID}/events"),
    ("POST", f"/api/projects/{PROJECT_ID}/performance"),
    ("GET", f"/api/projects/{PROJECT_ID}/preview-url"),
]


@pytest.mark.parametrize("method,path", STUB_ENDPOINTS)
def test_stub_endpoint_returns_todo(client, auth_headers, method, path):
    response = getattr(client, method.lower())(path, headers=auth_headers, json={})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "TODO"


@pytest.mark.parametrize("method,path", PROJECT_STUB_ENDPOINTS)
def test_project_stub_endpoint_returns_todo(client, auth_headers, method, path):
    response = getattr(client, method.lower())(path, headers=auth_headers, json={})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "TODO"


def test_topic_patch_stub(client, auth_headers):
    response = client.patch(
        f"/api/topics/{PROJECT_ID}", headers=auth_headers, json={}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "TODO"


def test_protected_endpoints_require_api_key(client):
    response = client.get("/api/topics")
    assert response.status_code == 401
```

保存为 `/Users/peng/Me/Ai/ai-video/backend/tests/test_api_stubs.py`

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd /Users/peng/Me/Ai/ai-video/backend
uv run pytest tests/test_api_stubs.py -v 2>&1 | head -20
```

Expected: FAIL 因为路由未注册

- [ ] **Step 3: 创建 api/topics.py**

```python
from fastapi import APIRouter, Depends
from app.auth import verify_api_key

router = APIRouter(prefix="/api/topics", tags=["topics"])


@router.get("")
async def list_topics(_=Depends(verify_api_key)):
    return {"status": "TODO", "endpoint": "GET /api/topics"}


@router.post("")
async def create_topic(_=Depends(verify_api_key)):
    return {"status": "TODO", "endpoint": "POST /api/topics"}


@router.patch("/{topic_id}")
async def update_topic(topic_id: str, _=Depends(verify_api_key)):
    return {"status": "TODO", "endpoint": f"PATCH /api/topics/{topic_id}"}


@router.post("/brainstorm")
async def brainstorm_topics(_=Depends(verify_api_key)):
    return {"status": "TODO", "endpoint": "POST /api/topics/brainstorm"}
```

保存为 `/Users/peng/Me/Ai/ai-video/backend/app/api/topics.py`

- [ ] **Step 4: 创建 api/projects.py**

```python
from fastapi import APIRouter, Depends
from app.auth import verify_api_key

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("")
async def list_projects(_=Depends(verify_api_key)):
    return {"status": "TODO", "endpoint": "GET /api/projects"}


@router.post("")
async def create_project(_=Depends(verify_api_key)):
    return {"status": "TODO", "endpoint": "POST /api/projects"}


@router.get("/{project_id}")
async def get_project(project_id: str, _=Depends(verify_api_key)):
    return {"status": "TODO", "endpoint": f"GET /api/projects/{project_id}"}


@router.get("/{project_id}/script-versions")
async def list_script_versions(project_id: str, _=Depends(verify_api_key)):
    return {"status": "TODO", "endpoint": f"GET /api/projects/{project_id}/script-versions"}


@router.get("/{project_id}/events")
async def list_events(project_id: str, _=Depends(verify_api_key)):
    return {"status": "TODO", "endpoint": f"GET /api/projects/{project_id}/events"}


@router.post("/{project_id}/performance")
async def record_performance(project_id: str, _=Depends(verify_api_key)):
    return {"status": "TODO", "endpoint": f"POST /api/projects/{project_id}/performance"}


@router.get("/{project_id}/preview-url")
async def get_preview_url(project_id: str, _=Depends(verify_api_key)):
    return {"status": "TODO", "endpoint": f"GET /api/projects/{project_id}/preview-url"}
```

保存为 `/Users/peng/Me/Ai/ai-video/backend/app/api/projects.py`

- [ ] **Step 5: 创建 api/reviews.py**

```python
from fastapi import APIRouter, Depends
from app.auth import verify_api_key

router = APIRouter(prefix="/api/projects", tags=["reviews"])


@router.post("/{project_id}/review")
async def submit_review(project_id: str, _=Depends(verify_api_key)):
    return {"status": "TODO", "endpoint": f"POST /api/projects/{project_id}/review"}
```

保存为 `/Users/peng/Me/Ai/ai-video/backend/app/api/reviews.py`

- [ ] **Step 6: 创建 api/worker_tasks.py**

```python
from fastapi import APIRouter, Depends
from app.auth import verify_api_key

router = APIRouter(prefix="/api/worker-tasks", tags=["worker-tasks"])


@router.get("")
async def list_worker_tasks(_=Depends(verify_api_key)):
    return {"status": "TODO", "endpoint": "GET /api/worker-tasks"}
```

保存为 `/Users/peng/Me/Ai/ai-video/backend/app/api/worker_tasks.py`

- [ ] **Step 7: 注册路由到 main.py**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import topics, projects, reviews, worker_tasks

app = FastAPI(title="AI Video Workflow Platform", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


app.include_router(topics.router)
app.include_router(projects.router)
app.include_router(reviews.router)
app.include_router(worker_tasks.router)
```

完整替换 `backend/app/main.py`

- [ ] **Step 8: 运行所有测试**

```bash
cd /Users/peng/Me/Ai/ai-video/backend
uv run pytest tests/ -v
```

Expected:
```
tests/test_health.py::test_health_no_auth_required PASSED
tests/test_health.py::test_protected_endpoint_without_key_returns_401 PASSED
tests/test_health.py::test_protected_endpoint_with_wrong_key_returns_401 PASSED
tests/test_api_stubs.py::test_stub_endpoint_returns_todo[GET-/api/topics] PASSED
tests/test_api_stubs.py::test_stub_endpoint_returns_todo[POST-/api/topics] PASSED
... (所有测试 PASSED)
```

- [ ] **Step 9: 手动验证后端启动**

```bash
cd /Users/peng/Me/Ai/ai-video/backend
uv run uvicorn app.main:app --reload &
sleep 2
curl http://localhost:8000/health
curl -H "X-API-Key: dev-api-key-change-in-prod" http://localhost:8000/api/topics
kill %1
```

Expected:
```json
{"status":"ok"}
{"status":"TODO","endpoint":"GET /api/topics"}
```

- [ ] **Step 10: Commit**

```bash
cd /Users/peng/Me/Ai/ai-video
git add backend/app/api/ backend/app/main.py backend/tests/test_api_stubs.py
git commit -m "feat: add all API route stubs with API Key auth"
```

---

## Task 8: Engine protocols + Temporal workflow skeleton

**Files:**
- Create: `backend/app/engines/render/base.py`
- Create: `backend/app/engines/tts/base.py`
- Create: `backend/app/engines/ai/base.py`
- Create: `backend/app/workflows/video_production.py`
- Create: `backend/app/workflows/activities.py`

**Interfaces:**
- Produces: `RenderEngine`, `TTSEngine`, `AIProvider` Protocol 类；`VideoProductionWorkflow` Temporal workflow 骨架；4 个 Activity 骨架

- [ ] **Step 1: 创建 engines/render/base.py**

```python
from typing import Protocol
from dataclasses import dataclass


@dataclass
class SceneAudio:
    scene_index: int
    audio_path: str
    duration_seconds: float


@dataclass
class SceneInput:
    scene_index: int
    narration: str
    description: str
    code: str
    audio: SceneAudio | None


@dataclass
class RenderRequest:
    scenes: list[SceneInput]
    output_format: str
    resolution: tuple[int, int]
    fps: int = 30


@dataclass
class RenderResult:
    success: bool
    output_path: str | None
    duration_seconds: float | None
    error_message: str | None
    render_log: str


class RenderEngine(Protocol):
    @property
    def engine_name(self) -> str: ...

    async def validate_code(self, scenes: list[SceneInput]) -> tuple[bool, str]: ...

    async def render(self, request: RenderRequest) -> RenderResult: ...

    async def health_check(self) -> bool: ...


class EngineRegistry[T]:
    def __init__(self):
        self._engines: dict[str, T] = {}

    def register(self, engine: T) -> None:
        self._engines[engine.engine_name] = engine

    def get(self, name: str) -> T:
        if name not in self._engines:
            raise ValueError(f"Unknown engine: {name}")
        return self._engines[name]

    def list_engines(self) -> list[str]:
        return list(self._engines.keys())
```

保存为 `/Users/peng/Me/Ai/ai-video/backend/app/engines/render/base.py`

- [ ] **Step 2: 创建 engines/tts/base.py**

```python
from typing import Protocol
from dataclasses import dataclass


@dataclass
class TTSRequest:
    text: str
    voice: str = "default"
    speed: float = 1.0


@dataclass
class TTSResult:
    success: bool
    output_path: str | None
    duration_seconds: float | None
    error_message: str | None


class TTSEngine(Protocol):
    @property
    def engine_name(self) -> str: ...

    async def synthesize(self, request: TTSRequest) -> TTSResult: ...

    async def health_check(self) -> bool: ...
```

保存为 `/Users/peng/Me/Ai/ai-video/backend/app/engines/tts/base.py`

- [ ] **Step 3: 创建 engines/ai/base.py**

```python
from typing import Protocol
from dataclasses import dataclass


@dataclass
class ScriptGenerationResult:
    scenes: list[dict]
    fact_checks: list[dict]


class AIProvider(Protocol):
    @property
    def engine_name(self) -> str: ...

    @property
    def model_name(self) -> str: ...

    async def generate_script(
        self,
        topic_title: str,
        topic_description: str,
        render_engine: str,
        rejection_context: dict | None = None,
    ) -> ScriptGenerationResult: ...
```

保存为 `/Users/peng/Me/Ai/ai-video/backend/app/engines/ai/base.py`

- [ ] **Step 4: 创建 workflows/activities.py**

```python
from temporalio import activity


@activity.defn
async def submit_script_generation_task(project_id: str) -> None:
    raise NotImplementedError("Sprint 2")


@activity.defn
async def submit_video_generation_task(project_id: str) -> None:
    raise NotImplementedError("Sprint 3")


@activity.defn
async def update_project_status(project_id: str, new_status: str) -> None:
    raise NotImplementedError("Sprint 2")


@activity.defn
async def check_and_increment_retry(
    project_id: str, stage: str, error: str
) -> bool:
    raise NotImplementedError("Sprint 2")
```

保存为 `/Users/peng/Me/Ai/ai-video/backend/app/workflows/activities.py`

- [ ] **Step 5: 创建 workflows/video_production.py**

```python
from temporalio import workflow


@workflow.defn
class VideoProductionWorkflow:

    @workflow.run
    async def run(self, project_id: str) -> None:
        raise NotImplementedError("Sprint 2")
```

保存为 `/Users/peng/Me/Ai/ai-video/backend/app/workflows/video_production.py`

- [ ] **Step 6: 验证导入**

```bash
cd /Users/peng/Me/Ai/ai-video/backend
uv run python -c "
from app.engines.render.base import RenderEngine, EngineRegistry, SceneInput, RenderRequest, RenderResult, SceneAudio
from app.engines.tts.base import TTSEngine, TTSRequest, TTSResult
from app.engines.ai.base import AIProvider
from app.workflows.video_production import VideoProductionWorkflow
from app.workflows.activities import submit_script_generation_task, update_project_status
print('OK')
"
```

Expected: `OK`

- [ ] **Step 7: Commit**

```bash
cd /Users/peng/Me/Ai/ai-video
git add backend/app/engines/ backend/app/workflows/
git commit -m "feat: add engine Protocol definitions and Temporal workflow skeleton"
```

---

## Task 9: BaseWorker (complete) + stub workers

**Files:**
- Create: `backend/app/workers/base.py`
- Create: `backend/app/workers/script_worker.py`
- Create: `backend/app/workers/render_worker.py`
- Create: `backend/app/workers/combined_worker.py`
- Create: `backend/tests/test_base_worker.py`

**Interfaces:**
- Consumes: `get_sync_session()` from `app.db`；`WorkerTask` model；Temporal `Client`
- Produces: `BaseWorker` 完整实现（含重试逻辑）；`ScriptWorker`、`RenderWorker`、`CombinedWorker` stub

- [ ] **Step 1: 写 test_base_worker.py 测试（TDD — 先写）**

```python
# backend/tests/test_base_worker.py
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.workers.base import BaseWorker


class ConcreteWorker(BaseWorker):
    supported_task_types = ["test_task"]

    async def _execute(self, task) -> dict:
        return {"result": "done"}


@pytest.fixture
def mock_temporal_client():
    client = AsyncMock()
    handle = AsyncMock()
    client.get_workflow_handle.return_value = handle
    return client


@pytest.fixture
def worker(mock_temporal_client):
    return ConcreteWorker(
        worker_id="test-worker-01",
        temporal_client=mock_temporal_client,
        poll_interval=0.1,
    )


@pytest.fixture
def mock_task():
    task = MagicMock()
    task.id = "task-uuid-123"
    task.project_id = "project-uuid-456"
    task.task_type = "test_task"
    task.status = "processing"
    task.retry_count = 0
    task.max_retries = 3
    task.temporal_workflow_id = "workflow-id-789"
    task.signal_name = "task_completed"
    task.input_payload = {}
    task.output_payload = None
    task.completed_at = None
    return task


@pytest.mark.asyncio
async def test_process_task_success_sends_signal(worker, mock_task, mock_temporal_client):
    with patch("app.workers.base.get_sync_session") as mock_session_fn:
        mock_db = MagicMock()
        mock_session_fn.return_value = mock_db

        await worker._process_task(mock_task)

    assert mock_task.status == "completed"
    mock_temporal_client.get_workflow_handle.assert_called_once_with("workflow-id-789")
    handle = mock_temporal_client.get_workflow_handle.return_value
    handle.signal.assert_called_once()
    signal_args = handle.signal.call_args
    assert signal_args[0][0] == "task_completed"
    assert signal_args[0][1]["success"] is True


@pytest.mark.asyncio
async def test_process_task_failure_retries_without_signal(worker, mock_task, mock_temporal_client):
    class FailingWorker(BaseWorker):
        supported_task_types = ["test_task"]
        async def _execute(self, task) -> dict:
            raise RuntimeError("boom")

    failing_worker = FailingWorker(
        worker_id="fail-worker",
        temporal_client=mock_temporal_client,
        poll_interval=0.1,
    )
    mock_task.retry_count = 0
    mock_task.max_retries = 3

    with patch("app.workers.base.get_sync_session") as mock_session_fn:
        mock_db = MagicMock()
        mock_session_fn.return_value = mock_db
        await failing_worker._process_task(mock_task)

    assert mock_task.status == "pending"
    assert mock_task.retry_count == 1
    mock_temporal_client.get_workflow_handle.return_value.signal.assert_not_called()


@pytest.mark.asyncio
async def test_process_task_failure_at_max_retries_sends_failure_signal(worker, mock_task, mock_temporal_client):
    class FailingWorker(BaseWorker):
        supported_task_types = ["test_task"]
        async def _execute(self, task) -> dict:
            raise RuntimeError("fatal error")

    failing_worker = FailingWorker(
        worker_id="fail-worker",
        temporal_client=mock_temporal_client,
        poll_interval=0.1,
    )
    mock_task.retry_count = 3
    mock_task.max_retries = 3

    with patch("app.workers.base.get_sync_session") as mock_session_fn:
        mock_db = MagicMock()
        mock_session_fn.return_value = mock_db
        await failing_worker._process_task(mock_task)

    assert mock_task.status == "failed"
    handle = mock_temporal_client.get_workflow_handle.return_value
    handle.signal.assert_called_once()
    signal_args = handle.signal.call_args
    assert signal_args[0][1]["success"] is False
```

保存为 `/Users/peng/Me/Ai/ai-video/backend/tests/test_base_worker.py`

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd /Users/peng/Me/Ai/ai-video/backend
uv run pytest tests/test_base_worker.py -v 2>&1 | head -10
```

Expected: FAIL — `ImportError` 因为 `app.workers.base` 不存在

- [ ] **Step 3: 创建 workers/base.py**

```python
import asyncio
from datetime import datetime, timezone
from typing import Any
from temporalio.client import Client
from sqlalchemy import text
from app.db import get_sync_session


class BaseWorker:
    supported_task_types: list[str] = []

    def __init__(
        self,
        worker_id: str,
        temporal_client: Client,
        poll_interval: float = 2.0,
    ):
        self.worker_id = worker_id
        self.temporal_client = temporal_client
        self.poll_interval = poll_interval

    async def run(self):
        while True:
            task = self._claim_next_task()
            if task:
                await self._process_task(task)
            else:
                await asyncio.sleep(self.poll_interval)

    def _claim_next_task(self) -> Any | None:
        db = get_sync_session()
        try:
            if not self.supported_task_types:
                return None

            type_placeholders = ", ".join(
                f":type_{i}" for i in range(len(self.supported_task_types))
            )
            params = {"worker_id": self.worker_id}
            for i, t in enumerate(self.supported_task_types):
                params[f"type_{i}"] = t

            result = db.execute(
                text(f"""
                    UPDATE worker_tasks
                    SET status = 'processing',
                        worker_id = :worker_id,
                        started_at = NOW()
                    WHERE id = (
                        SELECT id FROM worker_tasks
                        WHERE status = 'pending'
                          AND task_type IN ({type_placeholders})
                        ORDER BY created_at
                        FOR UPDATE SKIP LOCKED
                        LIMIT 1
                    )
                    RETURNING *
                """),
                params,
            ).fetchone()
            db.commit()
            return result
        finally:
            db.close()

    async def _process_task(self, task: Any):
        db = get_sync_session()
        try:
            output = await self._execute(task)
            task.status = "completed"
            task.output_payload = output
            task.completed_at = datetime.now(timezone.utc)
            db.merge(task)
            db.commit()

            await self._send_signal(task, {
                "task_id": str(task.id),
                "success": True,
                **output,
            })

        except Exception as e:
            if task.retry_count < task.max_retries:
                task.status = "pending"
                task.retry_count += 1
                task.worker_id = None
                task.started_at = None
                task.completed_at = None
                db.merge(task)
                db.commit()
                return

            task.status = "failed"
            task.output_payload = {"error_message": str(e)}
            task.completed_at = datetime.now(timezone.utc)
            db.merge(task)
            db.commit()

            await self._send_signal(task, {
                "task_id": str(task.id),
                "success": False,
                "error": str(e),
            })
        finally:
            db.close()

    async def _send_signal(self, task: Any, payload: dict):
        handle = self.temporal_client.get_workflow_handle(task.temporal_workflow_id)
        await handle.signal(task.signal_name, payload)

    async def _execute(self, task: Any) -> dict:
        raise NotImplementedError
```

保存为 `/Users/peng/Me/Ai/ai-video/backend/app/workers/base.py`

- [ ] **Step 4: 运行 BaseWorker 测试**

```bash
cd /Users/peng/Me/Ai/ai-video/backend
uv run pytest tests/test_base_worker.py -v
```

Expected: 全部 3 个测试 PASSED

- [ ] **Step 5: 创建 workers/script_worker.py**

```python
from app.workers.base import BaseWorker


class ScriptWorker(BaseWorker):
    supported_task_types = ["generate_script"]

    async def _execute(self, task) -> dict:
        raise NotImplementedError("Sprint 2: implement script generation")
```

保存为 `/Users/peng/Me/Ai/ai-video/backend/app/workers/script_worker.py`

- [ ] **Step 6: 创建 workers/render_worker.py**

```python
from app.workers.base import BaseWorker


class RenderWorker(BaseWorker):
    supported_task_types = ["render_video"]

    async def _execute(self, task) -> dict:
        raise NotImplementedError("Sprint 3: implement TTS + render pipeline")
```

保存为 `/Users/peng/Me/Ai/ai-video/backend/app/workers/render_worker.py`

- [ ] **Step 7: 创建 workers/combined_worker.py**

```python
"""
开发环境用合并 Worker。
单进程同时处理 generate_script 和 render_video 任务。
"""
import asyncio
import logging
from temporalio.client import Client
from app.workers.base import BaseWorker
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CombinedWorker(BaseWorker):
    """开发用：合并所有任务类型"""
    supported_task_types = ["generate_script", "render_video"]

    async def _execute(self, task) -> dict:
        raise NotImplementedError(f"Task type {task.task_type} not yet implemented")


async def main():
    logger.info("Connecting to Temporal at %s", settings.TEMPORAL_ADDRESS)
    client = await Client.connect(settings.TEMPORAL_ADDRESS)

    worker = CombinedWorker(
        worker_id="combined-worker-01",
        temporal_client=client,
        poll_interval=2.0,
    )
    logger.info("CombinedWorker started. Polling for tasks...")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
```

保存为 `/Users/peng/Me/Ai/ai-video/backend/app/workers/combined_worker.py`

- [ ] **Step 8: 运行全量测试**

```bash
cd /Users/peng/Me/Ai/ai-video/backend
uv run pytest tests/ -v
```

Expected: 所有测试 PASSED，无 FAIL

- [ ] **Step 9: Commit**

```bash
cd /Users/peng/Me/Ai/ai-video
git add backend/app/workers/ backend/tests/test_base_worker.py
git commit -m "feat: implement BaseWorker with retry logic and stub workers"
```

---

## Task 10: Frontend Vite setup + shadcn init

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.app.json`
- Create: `frontend/index.html`
- Create: `frontend/tailwind.config.ts`
- Create: `frontend/postcss.config.js`
- Create: `frontend/.env.example`
- Create: `frontend/src/index.css`（tailwind directives）
- Create: shadcn 必要组件（通过 CLI）

**Interfaces:**
- Produces: `npm run dev` 在 5173 端口启动 Vite dev server；shadcn/ui 组件可用

- [ ] **Step 1: 初始化 Vite + React + TypeScript 项目**

```bash
cd /Users/peng/Me/Ai/ai-video
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
```

Expected: `frontend/` 目录含 `src/`、`package.json`、`vite.config.ts` 等标准 Vite 文件

- [ ] **Step 2: 安装核心依赖**

```bash
cd /Users/peng/Me/Ai/ai-video/frontend
npm install react-router-dom@6 @tanstack/react-query@5
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
```

Expected: 安装成功，生成 `tailwind.config.js` 和 `postcss.config.js`

- [ ] **Step 3: 更新 tailwind.config.ts（重命名并更新内容）**

删除生成的 `tailwind.config.js`，创建 `tailwind.config.ts`：

```typescript
import type { Config } from "tailwindcss";

export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {},
  },
  plugins: [],
} satisfies Config;
```

保存为 `frontend/tailwind.config.ts`

- [ ] **Step 4: 更新 src/index.css**

完整替换 `frontend/src/index.css`：

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

- [ ] **Step 5: 初始化 shadcn/ui**

```bash
cd /Users/peng/Me/Ai/ai-video/frontend
npx shadcn@latest init
```

交互式问答，选择以下选项：
- Style: **Default**
- Base color: **Slate**
- CSS variables: **Yes**

Expected: 生成 `components.json`，更新 `tailwind.config.ts` 和 `src/index.css`，创建 `src/lib/utils.ts`

- [ ] **Step 6: 安装 Sprint 1 必用 shadcn 组件**

```bash
cd /Users/peng/Me/Ai/ai-video/frontend
npx shadcn@latest add button card badge dialog table input select
```

Expected: 在 `src/components/ui/` 下生成对应组件文件

- [ ] **Step 7: 创建 frontend/.env.example**

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_API_KEY=dev-api-key-change-in-prod
```

同时创建本地开发用 `.env`：

```bash
cp /Users/peng/Me/Ai/ai-video/frontend/.env.example /Users/peng/Me/Ai/ai-video/frontend/.env
```

- [ ] **Step 8: 验证 Vite 启动**

```bash
cd /Users/peng/Me/Ai/ai-video/frontend
npm run dev &
sleep 3
curl -s http://localhost:5173 | head -5
kill %1
```

Expected: 输出包含 `<!doctype html>` 或 React 页面 HTML

- [ ] **Step 9: Commit**

```bash
cd /Users/peng/Me/Ai/ai-video
git add frontend/
git commit -m "feat: initialize Vite + React + TypeScript + shadcn/ui frontend"
```

---

## Task 11: Frontend skeleton (types, api, hooks, pages, routing)

**Files:**
- Create: `frontend/src/types/index.ts`
- Create: `frontend/src/lib/api.ts`
- Create: `frontend/src/hooks/useTopics.ts`
- Create: `frontend/src/hooks/useProjects.ts`
- Create: `frontend/src/hooks/useWorkerTasks.ts`
- Create: `frontend/src/pages/TopicsPage.tsx`
- Create: `frontend/src/pages/ProjectsPage.tsx`
- Create: `frontend/src/pages/ProjectDetailPage.tsx`
- Create: `frontend/src/pages/PerformancePage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/main.tsx`
- Create: `frontend/src/components/Layout.tsx`

**Interfaces:**
- Produces: 4 个可访问的页面路由；左侧导航可跳转；所有 TypeScript 类型可用

- [ ] **Step 1: 创建完整类型定义 src/types/index.ts**

```typescript
// ═══ 选题 ═══
export interface TopicScores {
  counterintuitive: number;
  defensibility: number;
  visual: number;
  freshness: number;
}

export interface Topic {
  id: string;
  title: string;
  description: string;
  source: "manual" | "ai_brainstorm" | "audience" | "competitor";
  status: "pending" | "stocked" | "in_production" | "used" | "abandoned";
  scores: TopicScores;
  compositeScore: number;
  performanceScore: number | null;
  tags: string[];
  needsRecheck: boolean;
  createdAt: string;
  updatedAt: string;
}

// ═══ 视频项目 ═══
export type ProjectStatus =
  | "draft"
  | "script_generating"
  | "script_failed"
  | "script_review"
  | "video_generating"
  | "video_failed"
  | "video_review"
  | "published"
  | "abandoned";

export interface VideoProject {
  id: string;
  topicId: string;
  status: ProjectStatus;
  renderEngine: "manim" | "remotion";
  ttsVoice: string;
  aspectRatio: "landscape" | "portrait";
  currentScriptVersion: ScriptVersion | null;
  currentVideoAsset: VideoAsset | null;
  retryCount: number;
  createdAt: string;
  updatedAt: string;
}

// ═══ 镜头 ═══
export interface Scene {
  sceneIndex: number;
  narration: string;
  description: string;
  code: string;
  estimatedDurationSeconds: number;
}

// ═══ 事实核查条目 ═══
export interface FactCheckItem {
  claimText: string;
  sceneIndex: number;
  sourceUrl: string | null;
  sourceDescription: string;
  confidence: "high" | "medium" | "low";
  isHypothesis: boolean;
  assumptions: string | null;
  controversy: string | null;
  reviewerVerdict: "approved" | "rejected" | "needs_revision" | null;
  reviewerNote: string | null;
}

// ═══ 脚本版本 ═══
export interface ScriptVersion {
  id: string;
  projectId: string;
  versionNumber: number;
  scenes: Scene[];
  factChecks: FactCheckItem[];
  renderEngine: "manim" | "remotion";
  aiModel: string;
  rejectionContext: RejectionContext | null;
  createdAt: string;
}

// ═══ 视频产物 ═══
export interface VideoAsset {
  id: string;
  projectId: string;
  scriptVersionId: string;
  videoFileKey: string;
  durationSeconds: number;
  resolution: string;
  status: "rendering" | "completed" | "failed";
  createdAt: string;
}

// ═══ 审核请求 ═══
export interface ReviewRequest {
  gate: "script" | "video";
  verdict: "approved" | "rejected" | "abandoned";
  rejectionType?: "topic_invalid" | "fact_error" | "script_weak" | "sync_issue";
  rejectionDetail?: string;
  targetStage?: "script_generating";
  factCheckVerdicts?: Array<{
    index: number;
    verdict: "approved" | "rejected" | "needs_revision";
    note: string;
  }>;
}

// ═══ 驳回上下文 ═══
export interface RejectionContext {
  rejectionType: string;
  rejectionDetail: string;
  targetStage: string;
  rejectedAt: string;
}

// ═══ 异步任务 ═══
export interface WorkerTask {
  id: string;
  projectId: string;
  taskType: "generate_script" | "render_video";
  engine: string;
  status: "pending" | "processing" | "completed" | "failed";
  retryCount: number;
  maxRetries: number;
  createdAt: string;
  startedAt: string | null;
  completedAt: string | null;
}

// ═══ 项目事件 ═══
export interface ProjectEvent {
  id: number;
  projectId: string;
  eventType: string;
  fromStatus: string | null;
  toStatus: string | null;
  actor: string;
  payload: Record<string, unknown>;
  createdAt: string;
}

// ═══ 表现数据 ═══
export interface PerformanceRecord {
  id: string;
  projectId: string;
  platform: string;
  views: number;
  completionRate: number;
  likes: number;
  favorites: number;
  commentTags: string[];
  commentSummary: string | null;
  recordedAt: string;
}
```

保存为 `frontend/src/types/index.ts`

- [ ] **Step 2: 创建 src/lib/api.ts**

```typescript
const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const API_KEY = import.meta.env.VITE_API_KEY ?? "";

async function request<T>(
  method: string,
  path: string,
  body?: unknown
): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": API_KEY,
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }

  return response.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, body),
};
```

保存为 `frontend/src/lib/api.ts`

- [ ] **Step 3: 创建 hooks/useTopics.ts**

```typescript
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Topic } from "@/types";

interface TopicListResponse {
  items: Topic[];
  total: number;
}

export function useTopics() {
  return useQuery<TopicListResponse>({
    queryKey: ["topics"],
    queryFn: () => api.get<TopicListResponse>("/api/topics"),
  });
}
```

保存为 `frontend/src/hooks/useTopics.ts`

- [ ] **Step 4: 创建 hooks/useProjects.ts**

```typescript
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { VideoProject } from "@/types";

interface ProjectListResponse {
  items: VideoProject[];
  total: number;
}

export function useProjects(status?: string) {
  return useQuery<ProjectListResponse>({
    queryKey: ["projects", status],
    queryFn: () =>
      api.get<ProjectListResponse>(
        `/api/projects${status ? `?status=${status}` : ""}`
      ),
  });
}

export function useProject(id: string) {
  return useQuery<VideoProject>({
    queryKey: ["projects", id],
    queryFn: () => api.get<VideoProject>(`/api/projects/${id}`),
    enabled: !!id,
  });
}
```

保存为 `frontend/src/hooks/useProjects.ts`

- [ ] **Step 5: 创建 hooks/useWorkerTasks.ts**

```typescript
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { WorkerTask } from "@/types";

interface WorkerTaskListResponse {
  items: WorkerTask[];
}

export function useWorkerTasks(projectId?: string) {
  return useQuery<WorkerTaskListResponse>({
    queryKey: ["worker-tasks", projectId],
    queryFn: () =>
      api.get<WorkerTaskListResponse>(
        `/api/worker-tasks${projectId ? `?project_id=${projectId}` : ""}`
      ),
    refetchInterval: 3000,
  });
}
```

保存为 `frontend/src/hooks/useWorkerTasks.ts`

- [ ] **Step 6: 创建四个页面占位组件**

`frontend/src/pages/TopicsPage.tsx`：
```tsx
export default function TopicsPage() {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">选题池</h1>
      <p className="text-muted-foreground">TODO: TopicsPage</p>
    </div>
  );
}
```

`frontend/src/pages/ProjectsPage.tsx`：
```tsx
export default function ProjectsPage() {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">项目列表</h1>
      <p className="text-muted-foreground">TODO: ProjectsPage</p>
    </div>
  );
}
```

`frontend/src/pages/ProjectDetailPage.tsx`：
```tsx
import { useParams } from "react-router-dom";

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">项目详情</h1>
      <p className="text-muted-foreground">TODO: ProjectDetailPage — id: {id}</p>
    </div>
  );
}
```

`frontend/src/pages/PerformancePage.tsx`：
```tsx
import { useParams } from "react-router-dom";

export default function PerformancePage() {
  const { id } = useParams<{ id: string }>();
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">发布表现数据录入</h1>
      <p className="text-muted-foreground">TODO: PerformancePage — project: {id}</p>
    </div>
  );
}
```

- [ ] **Step 7: 创建 Layout 组件（带左侧导航）**

```tsx
// frontend/src/components/Layout.tsx
import { NavLink, Outlet } from "react-router-dom";
import { cn } from "@/lib/utils";

const navItems = [
  { to: "/topics", label: "选题池" },
  { to: "/projects", label: "项目列表" },
];

export default function Layout() {
  return (
    <div className="flex min-h-screen">
      <aside className="w-48 border-r bg-muted/40 flex flex-col p-4 gap-2">
        <div className="font-bold text-lg mb-4">AI 视频工厂</div>
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              cn(
                "px-3 py-2 rounded-md text-sm transition-colors",
                isActive
                  ? "bg-primary text-primary-foreground"
                  : "hover:bg-muted"
              )
            }
          >
            {item.label}
          </NavLink>
        ))}
      </aside>
      <main className="flex-1">
        <Outlet />
      </main>
    </div>
  );
}
```

保存为 `frontend/src/components/Layout.tsx`

- [ ] **Step 8: 更新 App.tsx（路由配置）**

```tsx
// frontend/src/App.tsx
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Layout from "@/components/Layout";
import TopicsPage from "@/pages/TopicsPage";
import ProjectsPage from "@/pages/ProjectsPage";
import ProjectDetailPage from "@/pages/ProjectDetailPage";
import PerformancePage from "@/pages/PerformancePage";

const queryClient = new QueryClient();

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Navigate to="/topics" replace />} />
          <Route element={<Layout />}>
            <Route path="/topics" element={<TopicsPage />} />
            <Route path="/projects" element={<ProjectsPage />} />
            <Route path="/projects/:id" element={<ProjectDetailPage />} />
            <Route
              path="/projects/:id/performance"
              element={<PerformancePage />}
            />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
```

- [ ] **Step 9: 更新 main.tsx**

```tsx
// frontend/src/main.tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
```

- [ ] **Step 10: 更新 vite.config.ts 添加路径别名**

```typescript
// frontend/vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
```

同时安装 `@types/node`：
```bash
cd /Users/peng/Me/Ai/ai-video/frontend
npm install -D @types/node
```

- [ ] **Step 11: 更新 tsconfig.app.json 添加路径别名**

在 `frontend/tsconfig.app.json` 的 `compilerOptions` 中添加：
```json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  }
}
```

- [ ] **Step 12: 创建 components 子目录占位**

```bash
mkdir -p /Users/peng/Me/Ai/ai-video/frontend/src/components/topics
mkdir -p /Users/peng/Me/Ai/ai-video/frontend/src/components/projects
mkdir -p /Users/peng/Me/Ai/ai-video/frontend/src/components/review
touch /Users/peng/Me/Ai/ai-video/frontend/src/components/topics/.gitkeep
touch /Users/peng/Me/Ai/ai-video/frontend/src/components/projects/.gitkeep
touch /Users/peng/Me/Ai/ai-video/frontend/src/components/review/.gitkeep
```

- [ ] **Step 13: 验证前端构建**

```bash
cd /Users/peng/Me/Ai/ai-video/frontend
npm run build
```

Expected: 构建成功，无 TypeScript 错误

- [ ] **Step 14: 验证 dev server 运行**

```bash
cd /Users/peng/Me/Ai/ai-video/frontend
npm run dev &
sleep 3
curl -s http://localhost:5173 | grep -c "<!doctype"
kill %1
```

Expected: 输出 `1`（页面可访问）

- [ ] **Step 15: Commit**

```bash
cd /Users/peng/Me/Ai/ai-video
git add frontend/src/
git commit -m "feat: add frontend skeleton with routing, types, hooks, and page stubs"
```

---

## Task 12: CLAUDE.md

**Files:**
- Create: `CLAUDE.md`

**Interfaces:**
- Produces: harness 工程文档，告知 Claude Code 项目结构、运行方式、关键约束

- [ ] **Step 1: 创建 CLAUDE.md**

```markdown
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

## 环境变量

后端从 `backend/.env` 读取（参考 `backend/.env.example`）。
前端从 `frontend/.env` 读取（参考 `frontend/.env.example`）。

## 测试

```bash
cd backend
uv run pytest tests/ -v
```

## 当前 Sprint 状态

- **Sprint 0（已完成）**：基础设施骨架，所有 API 返回 stub
- **Sprint 1**：选题池 + 项目状态机（Temporal Workflow 空壳跑通）
- **Sprint 2**：脚本生成 + 内容审核
- **Sprint 3**：视频生成 + 视频审核
```

保存为 `/Users/peng/Me/Ai/ai-video/CLAUDE.md`

- [ ] **Step 2: 最终全量测试**

```bash
cd /Users/peng/Me/Ai/ai-video/backend
uv run pytest tests/ -v
```

Expected: 所有测试 PASSED

```bash
cd /Users/peng/Me/Ai/ai-video/frontend
npm run build
```

Expected: 构建成功，无错误

- [ ] **Step 3: 验收标准检查**

```bash
# 1. 基础设施已启动
docker-compose ps

# 2. Migration 已完成
docker exec -it $(docker-compose ps -q postgres) psql -U app -d video_workflow -c "\dt" | grep -c "table"

# 3. 后端健康检查
curl http://localhost:8000/health

# 4. Stub 路由
curl -H "X-API-Key: dev-api-key-change-in-prod" http://localhost:8000/api/topics

# 5. 未授权返回 401
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/topics
```

Expected:
```
{"status":"ok"}
{"status":"TODO","endpoint":"GET /api/topics"}
401
```

- [ ] **Step 4: Commit**

```bash
cd /Users/peng/Me/Ai/ai-video
git add CLAUDE.md
git commit -m "docs: add CLAUDE.md harness documentation"
```

---

## Self-Review

**Spec coverage check:**

| 设计文档要求 | 实现 Task |
|-------------|-----------|
| docker-compose（4 个服务）| Task 1 |
| Makefile 命令 | Task 1 |
| uv 管理 Python 依赖 | Task 2 |
| 7 张表完整 schema | Task 3 + Task 4 |
| composite_score GENERATED 列 | Task 3（模型）+ Task 4（migration） |
| FastAPI + API Key 鉴权 | Task 5 |
| `/health` 无需鉴权 | Task 5 |
| 13 个 API stub endpoint | Task 7 |
| Pydantic schema 完整字段 | Task 6 |
| Engine Protocol 定义 | Task 8 |
| Temporal Workflow 骨架 | Task 8 |
| BaseWorker 完整实现（含重试逻辑）| Task 9 |
| ScriptWorker / RenderWorker / CombinedWorker stub | Task 9 |
| Vite + React + TypeScript | Task 10 |
| shadcn/ui 初始化 + 必用组件 | Task 10 |
| TypeScript 类型定义（附录 13）| Task 11 |
| 4 个页面路由 + 左侧导航 | Task 11 |
| TanStack Query hooks | Task 11 |
| api.ts（fetch 封装 + API Key）| Task 11 |
| CLAUDE.md harness 文档 | Task 12 |

**无遗漏。**

**Placeholder scan:** 所有 Step 均含完整代码，无 TBD / TODO 文字（除 stub handler 返回值本身）。

**Type consistency:** `WorkerTask`、`Topic`、`VideoProject` 等类型在 `types/index.ts` 定义，hooks 引用相同类型，无名称冲突。
