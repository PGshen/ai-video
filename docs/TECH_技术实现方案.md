# AI 知识视频生产工作流平台 — 技术实现方案

> 版本: v4.0 | 日期: 2026-06-24 | 配套文档: PRD v2.0

---

## 1. 技术栈总览

| 层级 | 技术选型 | 说明 |
|------|----------|------|
| 前端 | React + TypeScript + Shadcn/ui + TanStack Query | Shadcn 提供组件库，TanStack Query 管理服务端状态 |
| 后端 | Python + FastAPI | 异步 API，与 AI SDK 和工作流引擎无缝集成 |
| 数据库 | PostgreSQL + SQLAlchemy + Alembic | 关系型存储，JSONB 字段存储半结构化数据，**不使用数据库外键约束** |
| 工作流引擎 | Temporal (Python SDK) | 持久化工作流，原生支持重试、人工信号、定时器 |
| 对象存储 | MinIO / S3 | 存储视频、音频、渲染产物 |
| AI 服务 | Anthropic Claude API / OpenAI API | 叙事生成、代码生成、选题头脑风暴 |
| TTS | 可插拔（Edge TTS / OpenAI TTS / Fish Audio） | 通过 TTSEngine Protocol 抽象 |
| 视频渲染 | 可插拔（Manim / Remotion） | 通过 RenderEngine Protocol 抽象，渲染时直接注入音频轨道 |

### 为什么选 Temporal

Temporal 的核心优势在于原生的「人工信号等待」能力（Signal + await），完美匹配「工作流跑到审核环节挂起、等人点通过后继续」的场景：

- **持久化：** Workflow 实例的状态、事件历史存在 Temporal Server 自己的数据库中（非 Worker 内存），Worker 重启、崩溃不影响工作流状态
- **原生重试：** Activity 级别的 RetryPolicy，支持递增退避、最大重试次数
- **Signal 机制：** 工作流可以 `await workflow.wait_signal(...)` 无限期挂起，等待外部信号。本系统中统一使用 Signal 作为所有异步操作的回调机制（人工审核、叙事/代码生成完成、视频渲染完成），保持架构一致性
- **可观测性：** 自带 Web UI，可以查看每个 Workflow 实例的执行历史、当前状态

对比其他选项：n8n 偏低代码编排，对复杂状态机表达力不足；Prefect 偏数据管道，对人工卡点支持弱。

---

## 2. 核心架构模式：Signal 驱动的异步任务

本系统所有耗时操作（叙事生成、代码生成、视频渲染）采用统一的架构模式：

```
Temporal Workflow              后端 Activity            Worker 进程
     │                            │                       │
     │ ── execute_activity ──→    │                       │
     │                       ① 创建 worker_tasks 记录     │
     │                          (status=pending)          │
     │                       ② return（Activity 结束）     │
     │                            │                       │
     │ ③ await wait_signal(...)   │                 ④ 轮询 pending 任务
     │    （挂起等待）              │                 ⑤ 标记 processing
     │                            │                 ⑥ 执行任务
     │                            │                 ⑦ 回写结果
     │                            │                 ⑧ 发送 Temporal Signal
     │                            │                       │
     │ ⑨ Signal 唤醒，继续执行     │                       │
```

**与轮询模式对比的优势：**

- **实时性：** 任务完成后 Worker 立即发送 Signal，Workflow 立即恢复，无轮询延迟
- **一致性：** Signal 是 Temporal 原生机制，与人工审核信号使用同一套 API，状态管理统一
- **资源效率：** 无需 Activity 长时间占用线程做轮询循环

**Worker 发送 Signal 的方式：**

Worker 完成任务后，通过 Temporal Client 向对应的 Workflow 实例发送 Signal：

```python
from temporalio.client import Client

async def send_completion_signal(
    temporal_client: Client,
    workflow_id: str,
    signal_name: str,
    result: dict,
):
    """Worker 完成任务后调用此函数发送 Signal"""
    handle = temporal_client.get_workflow_handle(workflow_id)
    await handle.signal(signal_name, result)
```

`worker_tasks` 表中的 `temporal_workflow_id` 和 `signal_name` 字段告诉 Worker 该向哪个 Workflow 发送什么 Signal。

---

## 3. 数据库设计

> **设计原则：** 不使用数据库外键约束，关联关系在应用层维护。表之间的引用字段保留 `_id` 命名约定标识关联意图。

### 3.1 topics — 选题表

| 字段 | 类型 | 约束/默认值 | 说明 |
|------|------|-------------|------|
| id | UUID | PK, DEFAULT gen_random_uuid() | 主键 |
| title | VARCHAR(200) | NOT NULL | 选题标题 |
| description | TEXT | | 详细描述、背景信息 |
| source | VARCHAR(50) | NOT NULL | `manual` / `ai_brainstorm` / `audience` / `competitor` |
| status | VARCHAR(20) | DEFAULT 'pending' | `pending` / `stocked` / `used` / `abandoned`；项目制作状态不回写选题 |
| score_counterintuitive | SMALLINT | CHECK (1–5) | 反直觉强度 |
| score_defensibility | SMALLINT | CHECK (1–5) | 事实可辩护性（<3 不允许入库） |
| score_visual | SMALLINT | CHECK (1–5) | 视觉化潜力 |
| score_freshness | SMALLINT | CHECK (1–5) | 新鲜度 |
| composite_score | FLOAT | GENERATED | 加权综合分，用于排序 |
| performance_score | FLOAT | DEFAULT NULL | 发布后数据回流的表现分 |
| tags | VARCHAR(50)[] | | 分类标签（心理学、物理、数学…） |
| needs_recheck | BOOLEAN | DEFAULT FALSE | 评论区质疑触发的复核标记 |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | |

**索引：**

```sql
CREATE INDEX idx_topics_status ON topics(status);
CREATE INDEX idx_topics_composite_score ON topics(composite_score DESC);
CREATE INDEX idx_topics_tags ON topics USING GIN(tags);
```

### 3.2 video_projects — 视频项目表（核心实体）

| 字段 | 类型 | 约束/默认值 | 说明 |
|------|------|-------------|------|
| id | UUID | PK | 主键 |
| topic_id | UUID | NOT NULL | 关联选题（应用层维护关系） |
| status | VARCHAR(30) | NOT NULL | 状态机状态（见 PRD 3.2） |
| render_engine | VARCHAR(20) | NOT NULL | `manim` / `remotion` |
| tts_voice | VARCHAR(50) | NOT NULL | TTS 音色标识（如 `zh-CN-XiaoxiaoNeural`） |
| aspect_ratio | VARCHAR(20) | NOT NULL | `landscape`（横屏 16:9）/ `portrait`（竖屏 9:16） |
| current_code_version_id | UUID | | 当前生效代码版本 |
| current_video_asset_id | UUID | | 当前最新成片 |
| temporal_workflow_id | VARCHAR(100) | | Temporal 工作流实例 ID |
| retry_count | SMALLINT | DEFAULT 0 | 当前阶段已重试次数 |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | |

**索引：**

```sql
CREATE INDEX idx_projects_status ON video_projects(status);
CREATE INDEX idx_projects_topic_id ON video_projects(topic_id);
```

> **说明：** `status` 字段是 Temporal 工作流状态的冗余镜像，主要用于前端列表页快速筛选查询，避免每次都去查 Temporal。状态变更时由 Activity 同步更新到此字段。真正的状态权威来源是 Temporal Workflow。

### 3.3 code_versions — 代码版本表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | PK |
| project_id | UUID | 关联视频项目 |
| version_number | INT | 自增版本号（同一项目下） |
| scenes | JSONB | **镜头数组**（核心数据结构，见下方） |
| fact_checks | JSONB | 事实核查表（FactCheckItem[] 数组） |
| render_engine | VARCHAR(20) | `manim` / `remotion`（记录生成时使用的引擎） |
| ai_model | VARCHAR(50) | 生成使用的模型标识 |
| rejection_context | JSONB | 如果是因驳回重生成，包含驳回信息 |
| created_at | TIMESTAMPTZ | |

**`scenes` JSONB 结构：**

```typescript
type Scene = {
  scene_index: number;        // 镜头编号，从 0 开始
  narration: string;          // 旁白文稿
  description: string;        // 画面描述
  code: string;               // 渲染代码（Manim/Remotion）
  estimated_duration_seconds: number;  // 预估时长
};

// scenes 字段存储 Scene[]
```

> **关于镜头间依赖：** 镜头的 `code` 字段可能引用前序镜头创建的画布和元素。渲染时所有镜头代码作为整体提交给渲染引擎。镜头粒度的拆分主要服务于：旁白逐段 TTS 生成、审核时精确定位、事实核查条目关联。

**`fact_checks` JSONB 结构：**

```typescript
type FactCheckItem = {
  claim_text: string;
  scene_index: number;        // 对应镜头编号
  source_url: string | null;
  source_description: string;
  confidence: 'high' | 'medium' | 'low';
  is_hypothesis: boolean;
  assumptions: string | null;
  controversy: string | null;
  reviewer_verdict: 'approved' | 'rejected' | 'needs_revision' | null;
  reviewer_note: string | null;
};
```

**索引：**

```sql
CREATE INDEX idx_code_versions_project_id ON code_versions(project_id);
```

### 3.4 video_assets — 视频产物表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | PK |
| project_id | UUID | 关联视频项目 |
| code_version_id | UUID | 基于哪个代码版本渲染 |
| video_file_key | VARCHAR(500) | S3/MinIO 对象键（最终成片，已含音频） |
| duration_seconds | FLOAT | 成片时长 |
| resolution | VARCHAR(20) | 如 `1920x1080` |
| status | VARCHAR(20) | `rendering` / `completed` / `failed` |
| created_at | TIMESTAMPTZ | |

**索引：**

```sql
CREATE INDEX idx_video_assets_project_id ON video_assets(project_id);
```

### 3.5 worker_tasks — 异步任务表

统一管理所有异步任务（叙事生成、代码生成、视频渲染），是 Worker 与 Temporal Workflow 之间的桥梁。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | PK |
| project_id | UUID | 关联视频项目 |
| code_version_id | UUID | 关联代码版本（`generate_code` 时为 NULL） |
| task_type | VARCHAR(30) | `generate_code` / `render_video` |
| engine | VARCHAR(30) | 执行引擎标识（`claude` / `manim` / `remotion`） |
| status | VARCHAR(20) | `pending` / `processing` / `completed` / `failed` |
| input_payload | JSONB | 任务输入数据 |
| output_payload | JSONB | 任务输出数据（结果/错误信息） |
| retry_count | SMALLINT | DEFAULT 0 |
| max_retries | SMALLINT | DEFAULT 3 |
| temporal_workflow_id | VARCHAR(100) | 完成后要通知的 Workflow 实例 ID |
| signal_name | VARCHAR(50) | 完成后要发送的 Signal 名称 |
| worker_id | VARCHAR(100) | 执行该任务的 Worker 标识 |
| started_at | TIMESTAMPTZ | 开始执行时间 |
| completed_at | TIMESTAMPTZ | 完成时间 |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |

**索引：**

```sql
CREATE INDEX idx_worker_tasks_status ON worker_tasks(status);
CREATE INDEX idx_worker_tasks_project_id ON worker_tasks(project_id);
CREATE INDEX idx_worker_tasks_type_status ON worker_tasks(task_type, status);
```

**各任务类型的 input_payload / output_payload：**

#### generate_code

```json
// input_payload
{
  "topic_title": "为什么说生命的中点其实是18岁",
  "topic_description": "...",
  "render_engine": "manim",
  "rejection_context": null
}

// output_payload (成功)
{
  "code_version_id": "uuid",
  "scene_count": 5,
  "fact_check_count": 8
}

// output_payload (失败)
{
  "error_message": "AI API rate limit exceeded"
}
```

#### render_video

```json
// input_payload
{
  "scenes": [
    {
      "scene_index": 0,
      "narration": "你有没有想过...",
      "description": "标题动画",
      "code": "class TitleScene(Scene):\n    ...",
      "estimated_duration_seconds": 5.0
    }
  ],
  "render_engine": "manim",
  "tts_engine": "edge_tts",
  "tts_voice": "zh-CN-XiaoxiaoNeural",   // 从项目配置读取
  "output_format": "mp4",
  "resolution": [1920, 1080],             // 由 aspect_ratio 决定
  "fps": 30
}

// output_payload (成功)
{
  "video_file_key": "videos/proj_xxx/final.mp4",
  "video_asset_id": "uuid",
  "duration_seconds": 128.0
}

// output_payload (失败)
{
  "error_message": "NameError: name 'FadeIn' is not defined",
  "failed_stage": "render",
  "render_log": "..."
}
```

> **`failed_stage` 字段：** 标识失败发生在哪个阶段（`tts` / `render`），帮助定位问题。

### 3.6 project_events — 项目事件日志表（不可变追加日志）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGSERIAL | PK |
| project_id | UUID | 关联视频项目 |
| event_type | VARCHAR(50) | `status_changed` / `review_approved` / `review_rejected` / `task_completed` / `task_failed` / `published` 等 |
| from_status | VARCHAR(30) | 状态转移前 |
| to_status | VARCHAR(30) | 状态转移后 |
| actor | VARCHAR(50) | `system` / `user:<user_id>` |
| payload | JSONB | 额外数据（驳回原因、错误信息、审核意见等） |
| created_at | TIMESTAMPTZ | DEFAULT NOW() |

**索引：**

```sql
CREATE INDEX idx_project_events_project_id ON project_events(project_id);
CREATE INDEX idx_project_events_created_at ON project_events(created_at DESC);
```

### 3.7 performance_records — 发布表现数据表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | PK |
| project_id | UUID | 关联视频项目（UNIQUE 约束，一个项目一条记录） |
| platform | VARCHAR(30) | `bilibili` / `douyin` / `youtube` 等 |
| views | INT | 播放量 |
| completion_rate | FLOAT | 完播率 |
| likes | INT | 点赞数 |
| favorites | INT | 收藏数 |
| comment_tags | VARCHAR(30)[] | 评论标签 |
| comment_summary | TEXT | 评论摘要 |
| recorded_at | TIMESTAMPTZ | 数据采集时间 |
| created_at | TIMESTAMPTZ | |

### 3.8 ER 关系总结

```
topics 1 ── N video_projects 1 ── N code_versions
                             1 ── N video_assets
                             1 ── N worker_tasks
                             1 ── N project_events
                             1 ── 1 performance_records
```

> 所有关联在应用层维护，数据库不设 FK 约束。删除操作在 Service 层做级联检查。

---

## 4. Temporal 工作流设计

### 4.1 Signal 全景

本系统所有异步等待均通过 Temporal Signal 实现，分为两类：

| 类别 | Signal 名称 | 发送方 | 触发时机 | Payload |
|------|-------------|--------|----------|---------|
| 人工审核 | `code_review` | 后端 API | 审核人点击通过/驳回 | `{ verdict, rejection_type?, rejection_detail?, target_stage? }` |
| 人工审核 | `video_review` | 后端 API | 审核人点击通过/驳回 | `{ verdict, rejection_type?, rejection_detail?, target_stage? }` |
| 任务完成 | `code_generated` | Code Worker | 代码生成完成/失败 | `{ task_id, success, code_version_id?, error? }` |
| 任务完成 | `render_completed` | Render Worker | 视频生成完成/失败 | `{ task_id, success, video_asset_id?, error? }` |
| 用户操作 | `cancel` | 后端 API | 用户主动废弃 | `{ reason? }` |

> **统一模式：** 人工审核和机器任务完成使用完全相同的 Signal 机制。Workflow 内部只做 `await wait_signal(name)`，不关心信号来自人还是机器。

### 4.2 工作流完整伪代码

```python
@workflow.defn
class VideoProductionWorkflow:

    @workflow.run
    async def run(self, project_id: str):

        # ═══════════════════════════════════════════
        #  Phase 1: 叙事与代码生成循环
        # ═══════════════════════════════════════════
        while True:
            result = await self._generate_and_review_script(project_id)
            if result == "approved":
                break
            elif result == "abandoned":
                await self._update_status(project_id, "abandoned")
                return
            # else: "rejected" → 循环重新生成

        # ═══════════════════════════════════════════
        #  Phase 2: 视频生成循环
        # ═══════════════════════════════════════════
        while True:
            result = await self._generate_and_review_video(project_id)
            if result == "approved":
                break
            elif result == "abandoned":
                await self._update_status(project_id, "abandoned")
                return
            elif result == "back_to_script":
                # 退回脚本阶段，重入 Phase 1
                while True:
                    r = await self._generate_and_review_script(project_id)
                    if r == "approved":
                        break
                    elif r == "abandoned":
                        await self._update_status(project_id, "abandoned")
                        return
                # 脚本通过后继续视频生成循环

        # ═══════════════════════════════════════════
        #  Phase 3: 发布
        # ═══════════════════════════════════════════
        await self._update_status(project_id, "published")


    async def _generate_and_review_script(self, project_id: str) -> str:
        """
        生成脚本 + 等待审核。
        返回: "approved" / "rejected" / "abandoned"
        """
        # 1. 更新状态
        await self._update_status(project_id, "code_generating")

        # 2. 提交代码生成任务
        await workflow.execute_activity(
            submit_script_generation_task,
            args=[project_id],
            start_to_close_timeout=timedelta(seconds=30),
        )

        # 3. 等待 Worker 完成 Signal
        while True:
            result = await workflow.wait_signal("code_generated")

            if result["success"]:
                break
            else:
                # 生成失败，检查是否还可重试
                can_retry = await self._handle_task_failure(
                    project_id, "code_generating", result["error"]
                )
                if not can_retry:
                    await self._update_status(project_id, "code_failed")
                    return "abandoned"
                # 重新提交任务
                await workflow.execute_activity(
                    submit_script_generation_task,
                    args=[project_id],
                    start_to_close_timeout=timedelta(seconds=30),
                )

        # 4. 更新状态为待审核
        await self._update_status(project_id, "code_review")

        # 5. 等待人工审核 Signal（无超时）
        review = await workflow.wait_signal("code_review")

        return review["verdict"]


    async def _generate_and_review_video(self, project_id: str) -> str:
        """
        生成视频 + 等待审核。
        返回: "approved" / "back_to_script" / "abandoned"
        """
        # 1. 更新状态
        await self._update_status(project_id, "video_generating")

        # 2. 提交视频生成任务（单个任务，内部完成 TTS + 渲染 + 注入音频）
        await workflow.execute_activity(
            submit_video_generation_task,
            args=[project_id],
            start_to_close_timeout=timedelta(seconds=30),
        )

        # 3. 等待 Worker 完成 Signal
        while True:
            result = await workflow.wait_signal("render_completed")

            if result["success"]:
                break
            else:
                can_retry = await self._handle_task_failure(
                    project_id, "video_generating", result["error"]
                )
                if not can_retry:
                    await self._update_status(project_id, "video_failed")
                    return "abandoned"
                await workflow.execute_activity(
                    submit_video_generation_task,
                    args=[project_id],
                    start_to_close_timeout=timedelta(seconds=30),
                )

        # 4. 更新状态为待审核
        await self._update_status(project_id, "video_review")

        # 5. 等待人工审核 Signal
        review = await workflow.wait_signal("video_review")

        if review["verdict"] == "approved":
            return "approved"
        elif review["verdict"] == "abandoned":
            return "abandoned"
        else:
            return "back_to_script"


    async def _update_status(self, project_id: str, new_status: str):
        await workflow.execute_activity(
            update_project_status,
            args=[project_id, new_status],
            start_to_close_timeout=timedelta(seconds=10),
        )

    async def _handle_task_failure(
        self, project_id: str, stage: str, error: str
    ) -> bool:
        """处理任务失败，返回是否应重试"""
        return await workflow.execute_activity(
            check_and_increment_retry,
            args=[project_id, stage, error],
            start_to_close_timeout=timedelta(seconds=10),
        )
```

### 4.3 Activity 定义

所有 Activity 都是轻量级的——只负责写数据库记录或查询数据，不执行耗时操作。

| Activity | 职责 | 超时 |
|----------|------|------|
| submit_script_generation_task | 创建 `generate_code` 类型的 worker_tasks 记录 | 30s |
| submit_video_generation_task | 创建 `render_video` 类型的 worker_tasks 记录 | 30s |
| update_project_status | 更新 video_projects.status + 写入 project_events | 10s |
| check_and_increment_retry | 检查重试次数、自增、返回是否可继续 | 10s |

**submit_video_generation_task 实现：**

```python
@activity.defn
async def submit_video_generation_task(project_id: str):
    """
    创建视频生成任务。
    单个任务，Worker 内部完成 TTS + 渲染 + 音频注入。
    """
    db = get_db_session()
    project = db.get(VideoProject, project_id)
    code_version = db.get(CodeVersion, project.current_code_version_id)

    task = WorkerTask(
        project_id=project_id,
        code_version_id=code_version.id,
        task_type="render_video",
        engine=project.render_engine,
        status="pending",
        input_payload={
            "scenes": code_version.scenes,       # 完整镜头数组
            "render_engine": project.render_engine,
            "tts_engine": "edge_tts",               # 或从配置读取
            "tts_voice": project.tts_voice,
            "output_format": "mp4",
            "resolution": _resolve_resolution(project.aspect_ratio),
            "fps": 30,
        },
        temporal_workflow_id=project.temporal_workflow_id,
        signal_name="render_completed",
    )
    db.add(task)
    db.commit()


def _resolve_resolution(aspect_ratio: str) -> list[int]:
    """根据宽高比返回分辨率"""
    return {
        "landscape": [1920, 1080],  # 16:9 横屏
        "portrait": [1080, 1920],   # 9:16 竖屏
    }[aspect_ratio]
```

### 4.4 前端发送审核信号的调用链

```
前端点击「通过」
  → POST /api/projects/{id}/review
    → 后端校验当前状态是否允许该操作
    → 写入 project_events 日志
    → 调用 Temporal Client 发送 Signal
      → Temporal Server 将 Signal 传递给对应 Workflow 实例
        → Workflow 从 wait_signal 处恢复执行
```

---

## 5. 渲染引擎抽象层

### 5.1 RenderEngine Protocol

渲染引擎接收完整的镜头数组和各镜头音频文件，内部负责代码合并和音频注入，输出带声音的最终视频。

```python
from typing import Protocol
from dataclasses import dataclass


@dataclass
class SceneAudio:
    """单个镜头的 TTS 音频信息"""
    scene_index: int
    audio_path: str              # 本地音频文件路径
    duration_seconds: float


@dataclass
class SceneInput:
    """单个镜头的完整输入"""
    scene_index: int
    narration: str               # 旁白文稿（备用）
    description: str             # 画面描述（备用）
    code: str                    # 渲染代码
    audio: SceneAudio | None     # TTS 音频（已生成后填入）


@dataclass
class RenderRequest:
    """视频渲染请求"""
    scenes: list[SceneInput]         # 镜头数组（引擎负责合并代码 + 注入音频）
    output_format: str               # "mp4" | "webm"
    resolution: tuple[int, int]      # (1920, 1080)
    fps: int = 30


@dataclass
class RenderResult:
    """渲染结果（已含音频的最终视频）"""
    success: bool
    output_path: str | None          # 成功时的文件路径
    duration_seconds: float | None
    error_message: str | None        # 失败时的错误信息
    render_log: str                  # 完整渲染日志


class RenderEngine(Protocol):
    """统一渲染引擎接口"""

    @property
    def engine_name(self) -> str:
        """引擎标识名，如 'manim' / 'remotion'"""
        ...

    async def validate_code(self, scenes: list[SceneInput]) -> tuple[bool, str]:
        """
        语法/依赖预检。
        引擎自行决定如何合并代码后校验。
        返回 (is_valid, error_msg)。
        """
        ...

    async def render(self, request: RenderRequest) -> RenderResult:
        """
        执行渲染。
        引擎内部负责：
        1. 将镜头代码合并为完整源文件（处理 import 合并、依赖关系等）
        2. 在合适的位置注入音频引用
        3. 调用引擎 CLI 渲染
        4. 输出已包含音频的最终视频
        """
        ...

    async def health_check(self) -> bool:
        """引擎是否可用"""
        ...
```

### 5.2 Manim 引擎实现

Manim 引擎内部负责代码合并和音频注入。音频在每个镜头的代码段开始位置注入（而非 Scene 子类的 construct() 开头），因为并非每个镜头都是一个完整的 Scene 类。

```python
class ManimEngine:

    @property
    def engine_name(self) -> str:
        return "manim"

    async def validate_code(self, scenes: list[SceneInput]) -> tuple[bool, str]:
        """合并代码后做语法检查"""
        try:
            import ast
            merged = self._merge_scene_codes(scenes)
            ast.parse(merged)
            return True, ""
        except SyntaxError as e:
            return False, str(e)

    async def render(self, request: RenderRequest) -> RenderResult:
        with tempfile.TemporaryDirectory() as tmpdir:
            # 1. 准备音频文件
            audio_dir = Path(tmpdir) / "audio"
            audio_dir.mkdir()
            for scene in request.scenes:
                if scene.audio:
                    dest = audio_dir / f"scene_{scene.scene_index}.mp3"
                    shutil.copy(scene.audio.audio_path, dest)

            # 2. 合并代码 + 注入音频引用
            merged_code = self._merge_scene_codes(request.scenes)
            final_code = self._inject_audio(
                merged_code, request.scenes, audio_dir
            )

            # 3. 写入代码文件并渲染
            code_path = Path(tmpdir) / "scene.py"
            code_path.write_text(final_code)

            scene_classes = self._extract_scene_classes(final_code)
            w, h = request.resolution

            cmd = [
                "manim", "render",
                "-o", "output",
                "--format", request.output_format,
                "--fps", str(request.fps),
                "-r", f"{w},{h}",
                str(code_path),
                *scene_classes,
            ]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            log = stdout.decode() + stderr.decode()

            if proc.returncode == 0:
                output_path = self._find_output(tmpdir, request.output_format)
                duration = self._get_duration(output_path)
                return RenderResult(
                    success=True,
                    output_path=str(output_path),
                    duration_seconds=duration,
                    error_message=None,
                    render_log=log,
                )
            else:
                return RenderResult(
                    success=False,
                    output_path=None,
                    duration_seconds=None,
                    error_message=log[-2000:],
                    render_log=log,
                )

    def _merge_scene_codes(self, scenes: list[SceneInput]) -> str:
        """
        将镜头代码合并为完整源文件。
        处理 import 去重、公共函数提取等引擎特定的合并逻辑。
        """
        codes = [
            scene.code
            for scene in sorted(scenes, key=lambda s: s.scene_index)
        ]
        # 实际实现中应做 import 去重等处理
        return "\n\n".join(codes)

    def _inject_audio(
        self,
        code: str,
        scenes: list[SceneInput],
        audio_dir: Path,
    ) -> str:
        """
        在每个镜头的代码段开始位置注入音频。

        支持两种策略（按优先级）：
        1. 占位符替换：AI 生成代码时预埋 {{AUDIO_SCENE_0}} 占位符
        2. 标记定位：在镜头标记注释后插入 self.add_sound()

        注意：音频注入在每个镜头的开始位置，而不是 Scene 子类的
        construct() 开头，因为一个 Scene 类可能包含多个镜头的代码。
        """
        for scene in scenes:
            if not scene.audio:
                continue

            audio_path = str(audio_dir / f"scene_{scene.scene_index}.mp3")
            placeholder = f"{{{{AUDIO_SCENE_{scene.scene_index}}}}}"

            if placeholder in code:
                # 策略 1：占位符替换
                code = code.replace(placeholder, audio_path)
            else:
                # 策略 2：在镜头标记注释后插入
                scene_marker = f"# --- SCENE {scene.scene_index} ---"
                if scene_marker in code:
                    inject_line = (
                        f'{scene_marker}\n'
                        f'        self.add_sound("{audio_path}")'
                    )
                    code = code.replace(scene_marker, inject_line)

        return code

    async def health_check(self) -> bool:
        proc = await asyncio.create_subprocess_exec(
            "manim", "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        return proc.returncode == 0
```

> **音频注入策略说明：**
>
> - **占位符替换（推荐）：** AI 生成代码时在需要插入音频的位置写入 `{{AUDIO_SCENE_0}}`，引擎替换为实际路径。对代码结构没有假设，最灵活。占位符格式作为 prompt 约定固化。
> - **标记定位（兜底）：** AI 生成代码时在每个镜头开始处插入注释标记（如 `# --- SCENE 0 ---`），引擎在标记后插入 `self.add_sound()`。两种策略共存，占位符优先、标记兜底。

### 5.3 引擎注册中心

```python
class EngineRegistry[T]:
    """通用引擎注册中心"""

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


# 应用启动时
render_registry: EngineRegistry[RenderEngine] = EngineRegistry()
render_registry.register(ManimEngine())
```

**新引擎接入步骤：**

1. 实现 `RenderEngine` Protocol（包括该引擎特定的音频注入方式）
2. 在应用启动时注册到 Registry
3. 完成。业务层代码零修改

### 5.4 TTS 引擎抽象

TTS 引擎虽然不再作为独立的异步任务，但仍通过 Protocol 抽象，由 RenderWorker 内部调用。

```python
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

TTS Registry 与 Render Registry 共用 `EngineRegistry` 泛型类。

---

## 6. Worker 实现

### 6.1 统一 Worker 框架

所有 Worker 共享同一套框架：轮询 `worker_tasks` 表认领任务 → 执行 → 回写结果 → 发送 Temporal Signal。

```python
class BaseWorker:
    """
    Worker 基类。
    子类只需实现 _execute 方法和指定 supported_task_types。
    """

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
        """主循环"""
        while True:
            task = self._claim_next_task()
            if task:
                await self._process_task(task)
            else:
                await asyncio.sleep(self.poll_interval)

    def _claim_next_task(self) -> WorkerTask | None:
        """
        原子性地认领一条 pending 任务。
        使用 SELECT ... FOR UPDATE SKIP LOCKED 防止并发抢占。
        """
        db = get_db_session()
        type_filter = ",".join(f"'{t}'" for t in self.supported_task_types)
        task = db.execute(
            text(f"""
                UPDATE worker_tasks
                SET status = 'processing',
                    worker_id = :worker_id,
                    started_at = NOW()
                WHERE id = (
                    SELECT id FROM worker_tasks
                    WHERE status = 'pending'
                      AND task_type IN ({type_filter})
                    ORDER BY created_at
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                RETURNING *
            """),
            {"worker_id": self.worker_id},
        ).fetchone()
        db.commit()
        return task

    async def _process_task(self, task: WorkerTask):
        """执行任务 → 回写结果 → 发送 Signal"""
        db = get_db_session()
        try:
            output = await self._execute(task)
            task.status = "completed"
            task.output_payload = output
            task.completed_at = datetime.utcnow()
            db.commit()

            # 发送成功 Signal
            await self._send_signal(task, {
                "task_id": str(task.id),
                "success": True,
                **output,
            })

        except Exception as e:
            task.status = "failed"
            task.output_payload = {"error_message": str(e)}
            task.completed_at = datetime.utcnow()

            # 检查是否可重试
            if task.retry_count < task.max_retries:
                task.status = "pending"
                task.retry_count += 1
                task.worker_id = None
                task.started_at = None
                task.completed_at = None
                db.commit()
                return  # 不发 Signal，等待重新认领

            db.commit()

            # 达到最大重试次数，发送失败 Signal
            await self._send_signal(task, {
                "task_id": str(task.id),
                "success": False,
                "error": str(e),
            })

    async def _send_signal(self, task: WorkerTask, payload: dict):
        """向 Temporal Workflow 发送 Signal"""
        handle = self.temporal_client.get_workflow_handle(
            task.temporal_workflow_id
        )
        await handle.signal(task.signal_name, payload)

    async def _execute(self, task: WorkerTask) -> dict:
        """子类实现"""
        raise NotImplementedError
```

### 6.2 CodeWorker

```python
class CodeWorker(BaseWorker):
    """代码生成 Worker"""
    supported_task_types = ["generate_code"]

    def __init__(self, ai_registry: EngineRegistry, **kwargs):
        super().__init__(**kwargs)
        self.ai_registry = ai_registry

    async def _execute(self, task: WorkerTask) -> dict:
        payload = task.input_payload
        ai_provider = self.ai_registry.get(task.engine)

        # 调用 AI 生成脚本
        result = await ai_provider.generate_code(
            topic_title=payload["topic_title"],
            topic_description=payload["topic_description"],
            render_engine=payload["render_engine"],
            rejection_context=payload.get("rejection_context"),
        )

        # 写入 code_versions 表
        db = get_db_session()
        version_number = db.query(
            func.coalesce(func.max(CodeVersion.version_number), 0)
        ).filter(
            CodeVersion.project_id == task.project_id
        ).scalar()

        code_version = CodeVersion(
            project_id=task.project_id,
            version_number=version_number + 1,
            scenes=result.scenes,
            fact_checks=result.fact_checks,
            render_engine=payload["render_engine"],
            ai_model=ai_provider.model_name,
            rejection_context=payload.get("rejection_context"),
        )
        db.add(code_version)

        project = db.get(VideoProject, task.project_id)
        project.current_code_version_id = code_version.id
        db.commit()

        return {
            "code_version_id": str(code_version.id),
            "scene_count": len(result.scenes),
            "fact_check_count": len(result.fact_checks),
        }
```

### 6.3 RenderWorker

视频生成的核心 Worker。单个任务内完成 TTS + 渲染 + 音频注入，输出带声音的成片。

```python
class RenderWorker(BaseWorker):
    """
    视频渲染 Worker。
    单个任务内完成：TTS 生成 → 音频注入 → 渲染 → 输出成片。
    可部署在 GPU 机器或高内存机器上。
    """
    supported_task_types = ["render_video"]

    def __init__(
        self,
        render_registry: EngineRegistry,
        tts_registry: EngineRegistry,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.render_registry = render_registry
        self.tts_registry = tts_registry

    async def _execute(self, task: WorkerTask) -> dict:
        payload = task.input_payload
        scenes = payload["scenes"]

        render_engine = self.render_registry.get(payload["render_engine"])
        tts_engine = self.tts_registry.get(payload["tts_engine"])

        with tempfile.TemporaryDirectory() as tmpdir:
            # ── Step 1: 为所有镜头生成 TTS 音频 ──
            scene_inputs: list[SceneInput] = []

            for scene in sorted(scenes, key=lambda s: s["scene_index"]):
                tts_result = await tts_engine.synthesize(TTSRequest(
                    text=scene["narration"],
                    voice=payload.get("tts_voice", "default"),
                    speed=payload.get("tts_speed", 1.0),
                ))

                if not tts_result.success:
                    raise RuntimeError(
                        f"TTS failed for scene {scene['scene_index']}: "
                        f"{tts_result.error_message}"
                    )

                # 保存到临时目录
                audio_path = Path(tmpdir) / f"scene_{scene['scene_index']}.mp3"
                shutil.move(tts_result.output_path, audio_path)

                scene_inputs.append(SceneInput(
                    scene_index=scene["scene_index"],
                    narration=scene["narration"],
                    description=scene["description"],
                    code=scene["code"],
                    audio=SceneAudio(
                        scene_index=scene["scene_index"],
                        audio_path=str(audio_path),
                        duration_seconds=tts_result.duration_seconds,
                    ),
                ))

            # ── Step 2: 预检（引擎内部合并代码后校验） ──
            valid, err = await render_engine.validate_code(scene_inputs)
            if not valid:
                raise ValueError(f"Code validation failed: {err}")

            # ── Step 3: 渲染（引擎负责合并代码 + 注入音频 + 渲染） ──
            render_result = await render_engine.render(RenderRequest(
                scenes=scene_inputs,
                output_format=payload["output_format"],
                resolution=tuple(payload["resolution"]),
                fps=payload["fps"],
            ))

            if not render_result.success:
                raise RuntimeError(render_result.error_message)

            # ── Step 4: 上传到 S3 ──
            file_key = f"videos/{task.project_id}/final.{payload['output_format']}"
            await upload_to_s3(render_result.output_path, file_key)

            # ── Step 5: 创建 video_asset 记录 ──
            db = get_db_session()
            video_asset = VideoAsset(
                project_id=task.project_id,
                code_version_id=task.code_version_id,
                video_file_key=file_key,
                duration_seconds=render_result.duration_seconds,
                resolution=f"{payload['resolution'][0]}x{payload['resolution'][1]}",
                status="completed",
            )
            db.add(video_asset)

            project = db.get(VideoProject, task.project_id)
            project.current_video_asset_id = video_asset.id
            db.commit()

            return {
                "video_file_key": file_key,
                "video_asset_id": str(video_asset.id),
                "duration_seconds": render_result.duration_seconds,
            }
```

### 6.4 Worker 部署

```bash
# 代码生成 Worker（CPU 机器即可）
python -m app.workers.code_worker --worker-id=code-01

# 视频渲染 Worker（建议高性能机器）
python -m app.workers.render_worker --worker-id=render-01
```

> **开发/小规模部署**可以把两种 Worker 合并到一个进程中，创建一个 `CombinedWorker`，其 `supported_task_types` 包含 `["generate_code", "render_video"]`。

---

## 7. 关键接口设计

### 7.1 后端 API 概览（RESTful）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/topics | 获取选题列表（支持筛选、排序、分页） |
| POST | /api/topics | 创建选题 |
| PATCH | /api/topics/{id} | 更新选题（打分、状态变更） |
| POST | /api/topics/brainstorm | AI 批量生成候选选题 |
| GET | /api/projects | 获取视频项目列表（支持状态筛选） |
| POST | /api/projects | 从选题创建视频项目（启动 Temporal 工作流） |
| GET | /api/projects/{id} | 获取项目详情（含当前脚本、视频、事件历史） |
| POST | /api/projects/{id}/review | 提交审核结果（发送 Temporal Signal） |
| GET | /api/projects/{id}/code-versions | 获取代码历史版本 |
| GET | /api/projects/{id}/events | 获取项目事件日志 |
| POST | /api/projects/{id}/performance | 录入发布表现数据 |
| GET | /api/projects/{id}/preview-url | 获取视频预览签名 URL |
| GET | /api/worker-tasks?project_id={id} | 获取项目的异步任务列表（进度/调试） |

### 7.2 审核接口详细设计

```
POST /api/projects/{id}/review

Request Body:
{
  "gate": "code" | "video",
  "verdict": "approved" | "rejected" | "abandoned",
  "rejection_type": "topic_invalid" | "fact_error"
    | "code_issue" | "sync_issue",            // rejected 时必填
  "rejection_detail": "string, 具体问题描述",    // rejected 时必填
  "target_stage": "code_generating",          // rejected 时可选（有默认值）
  "fact_check_verdicts": [                      // gate=code 且 verdict=approved 时必填
    { "index": 0, "verdict": "approved", "note": "" },
    { "index": 1, "verdict": "approved", "note": "来源已确认" }
  ]
}
```

**后端处理流程：**

1. **状态校验：** 验证当前项目状态是否允许该审核操作
2. **核查表校验：** 如果 `gate=code` 且 `verdict=approved`，校验所有核查条目已审核且无 `rejected`
3. **事件记录：** 写入 `project_events` 表
4. **信号发送：** 向 Temporal Workflow 实例发送 Signal
5. **核查表回写：** 更新 `code_versions.fact_checks` 中的审核结果字段

### 7.3 创建项目接口

```
POST /api/projects

Request Body:
{
  "topic_id": "uuid",
  "render_engine": "manim" | "remotion",
  "tts_voice": "zh-CN-XiaoxiaoNeural",
  "aspect_ratio": "landscape" | "portrait"
}
```

**后端处理流程：**

1. 校验选题状态为 `stocked` 且 `score_defensibility >= 3`
2. 创建 `video_projects` 记录（状态 `draft`）
3. 启动 Temporal Workflow 实例
4. 回写 `temporal_workflow_id`
5. 返回创建的项目

同一选题可创建多个视频项目，项目生命周期不改变选题状态。

---

## 8. 前端架构

### 8.1 状态管理

```
TanStack Query
  ├── useTopics()          → GET /api/topics
  ├── useTopic(id)         → GET /api/topics/{id}
  ├── useProjects()        → GET /api/projects
  ├── useProject(id)       → GET /api/projects/{id}
  ├── useCodeVersions(projectId) → GET /api/projects/{id}/code-versions
  ├── useProjectEvents(projectId)  → GET /api/projects/{id}/events
  └── useWorkerTasks(projectId)    → GET /api/worker-tasks?project_id={id}
```

- 项目详情页使用 `refetchInterval` 轮询（生成中状态 3s，审核中状态 30s）
- 生成进度通过轮询 `worker_tasks` 的状态在前端展示

### 8.2 核心组件

| 组件 | 路径 | 职责 |
|------|------|------|
| TopicList | components/topics/ | 选题列表、筛选、排序 |
| TopicForm | components/topics/ | 新建/编辑选题弹窗 |
| BrainstormDialog | components/topics/ | AI 头脑风暴弹窗 |
| ProjectList | components/projects/ | 项目卡片列表 |
| ProjectDetail | components/projects/ | 项目详情页主框架 |
| StatusProgressBar | components/projects/ | 状态进度条 |
| ScriptViewer | components/review/ | 镜头式脚本查看器 |
| FactCheckTable | components/review/ | 事实核查表（逐条审核） |
| ReviewPanel | components/review/ | 审核操作面板 |
| RejectionDialog | components/review/ | 驳回弹窗 |
| VideoPlayer | components/review/ | 成片预览播放器 |
| EventTimeline | components/projects/ | 事件时间线 |
| PerformanceForm | components/projects/ | 表现数据录入表单 |
| TaskProgress | components/projects/ | 异步任务进度展示 |

---

## 9. 项目目录结构

```
video-workflow-platform/
├── backend/
│   ├── app/
│   │   ├── api/                      # FastAPI routers
│   │   │   ├── topics.py
│   │   │   ├── projects.py
│   │   │   ├── reviews.py
│   │   │   └── worker_tasks.py
│   │   ├── models/                   # SQLAlchemy models
│   │   │   ├── topic.py
│   │   │   ├── project.py
│   │   │   ├── code_version.py
│   │   │   ├── video_asset.py
│   │   │   ├── worker_task.py
│   │   │   └── project_event.py
│   │   ├── schemas/                  # Pydantic schemas
│   │   │   ├── topic.py
│   │   │   ├── project.py
│   │   │   ├── review.py
│   │   │   └── worker_task.py
│   │   ├── services/                 # Business logic
│   │   │   ├── topic_service.py
│   │   │   └── project_service.py
│   │   ├── engines/                  # ★ 可插拔引擎层
│   │   │   ├── render/
│   │   │   │   ├── base.py           # RenderEngine Protocol + SceneAudio
│   │   │   │   ├── manim_engine.py
│   │   │   │   ├── remotion_engine.py
│   │   │   │   └── registry.py
│   │   │   ├── tts/
│   │   │   │   ├── base.py           # TTSEngine Protocol
│   │   │   │   ├── edge_tts_engine.py
│   │   │   │   └── registry.py
│   │   │   └── ai/
│   │   │       ├── base.py           # AIProvider Protocol
│   │   │       ├── claude_provider.py
│   │   │       └── registry.py
│   │   ├── workflows/                # Temporal workflows & activities
│   │   │   ├── video_production.py   # Main workflow
│   │   │   └── activities.py         # Activity definitions (轻量级)
│   │   ├── workers/                  # ★ 独立 Worker 进程
│   │   │   ├── base.py               # BaseWorker
│   │   │   ├── script_worker.py
│   │   │   ├── render_worker.py      # 内部完成 TTS + 渲染
│   │   │   └── combined_worker.py    # 合并 Worker（开发用）
│   │   └── config.py
│   ├── alembic/                      # DB migrations
│   ├── tests/
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── topics/
│   │   │   ├── projects/
│   │   │   ├── review/
│   │   │   │   ├── FactCheckTable.tsx
│   │   │   │   ├── ScriptViewer.tsx
│   │   │   │   ├── ReviewPanel.tsx
│   │   │   │   ├── RejectionDialog.tsx
│   │   │   │   └── VideoPlayer.tsx
│   │   │   └── ui/                   # shadcn 组件
│   │   ├── hooks/
│   │   │   ├── useTopics.ts
│   │   │   ├── useProjects.ts
│   │   │   └── useWorkerTasks.ts
│   │   ├── pages/
│   │   │   ├── TopicsPage.tsx
│   │   │   ├── ProjectsPage.tsx
│   │   │   ├── ProjectDetailPage.tsx
│   │   │   └── PerformancePage.tsx
│   │   └── types/
│   │       └── index.ts
│   └── package.json
├── docker-compose.yml                # PG + Temporal + MinIO
└── README.md
```

---

## 10. 部署架构

### 10.1 本地开发（docker-compose）

| 服务 | 镜像 | 端口 | 说明 |
|------|------|------|------|
| PostgreSQL | postgres:16 | 5432 | 主数据库 |
| Temporal Server | temporalio/auto-setup | 7233 | 工作流引擎 |
| Temporal Web UI | temporalio/ui | 8080 | 工作流可视化监控 |
| MinIO | minio/minio | 9000/9001 | 对象存储 |
| Backend (FastAPI) | 本地构建 | 8000 | uvicorn |
| Temporal Worker | 本地构建 | — | temporal worker（执行 Workflow + Activity） |
| Task Workers | 本地构建 | — | 脚本 Worker + 渲染 Worker（可合并为一个进程） |
| Frontend (Vite) | 本地构建 | 5173 | vite dev |

### 10.2 docker-compose.yml 要点

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: video_workflow
      POSTGRES_USER: app
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    ports: ["5432:5432"]
    volumes: ["pgdata:/var/lib/postgresql/data"]

  temporal:
    image: temporalio/auto-setup:latest
    environment:
      DB: postgres12
      DB_PORT: 5432
      POSTGRES_USER: temporal
      POSTGRES_PWD: ${TEMPORAL_DB_PASSWORD}
      POSTGRES_SEEDS: postgres
    depends_on: [postgres]
    ports: ["7233:7233"]

  temporal-ui:
    image: temporalio/ui:latest
    environment:
      TEMPORAL_ADDRESS: temporal:7233
    depends_on: [temporal]
    ports: ["8080:8080"]

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    ports: ["9000:9000", "9001:9001"]
    volumes: ["minio_data:/data"]

volumes:
  pgdata:
  minio_data:
```

---

## 11. 实施路线图

| 阶段 | 时间 | 交付物 | 里程碑 |
|------|------|--------|--------|
| Sprint 0 | 1 周 | 基础设施搭建 | docker-compose 一键启动、DB migration、空 FastAPI 骨架、空 React 骨架、BaseWorker 框架 |
| Sprint 1 | 2 周 | 选题池 + 项目状态机 | 可创建选题、打分、从选题创建项目、Temporal Workflow 空壳跑通 |
| Sprint 2 | 2 周 | 叙事与代码生成 + 内容审核 | NarrativeWorker、CodeWorker 跑通，完成叙事/代码审核 UI |
| Sprint 3 | 2 周 | 视频生成 + 视频审核 | RenderEngine 抽象层 + Manim 实现（含音频注入）、RenderWorker 跑通、视频预览审核 |
| Sprint 4 | 1 周 | 发布与数据回流 | 标记发布、表现数据录入、回写选题评分 |
| Sprint 5 | 1 周 | 端到端测试 + 优化 | 全流程跑通、修复问题、发布 v1.0 |

> **关键节点：** Sprint 2 结束时应该能跑通「选题 → 脚本 → 审核」半条线。Sprint 3 补上视频。不要先花时间在看板、数据看板等 P1/P2 功能上。

---

## 12. 风险与应对

| 风险 | 影响 | 应对措施 |
|------|------|----------|
| AI 生成的 Manim 代码渲染失败率高 | 生产效率低 | validate_code 预检 + 失败时将错误信息反馈给 AI 重试 + 积累常见错误写入 prompt |
| 音频注入后音画不同步 | 成片质量差 | Manim add_sound 原生对齐；AI 生成代码时预估时长应与 TTS 实际时长匹配；可在 RenderEngine 内部做时长校准 |
| AI 生成核查表写得「满分」但实际不对 | 内容可信度受损 | 审核人必须独立核实来源 + 核查表附带 source_url 方便一键跳转 |
| Worker 崩溃导致任务卡在 processing | 任务僵死 | 定时清理：超过 N 分钟仍为 processing 的任务自动重置为 pending |
| Temporal 运维复杂度 | 开发投入大 | docker-compose 一键部署、后续可考虑 Temporal Cloud 托管 |
| 单人运营审核成为瓶颈 | 生产速度受限 | 正常现象。核查表已大幅提效，后续可加 AI 辅助预审 |

---

## 13. 附录：前端核心类型定义

```typescript
// ═══ 选题 ═══
interface Topic {
  id: string;
  title: string;
  description: string;
  source: 'manual' | 'ai_brainstorm' | 'audience' | 'competitor';
  status: 'pending' | 'stocked' | 'used' | 'abandoned';
  scores: {
    counterintuitive: number;
    defensibility: number;
    visual: number;
    freshness: number;
  };
  compositeScore: number;
  performanceScore: number | null;
  tags: string[];
  needsRecheck: boolean;
  createdAt: string;
  updatedAt: string;
}

// ═══ 视频项目 ═══
type ProjectStatus =
  | 'draft'
  | 'code_generating' | 'code_failed' | 'code_review'
  | 'video_generating' | 'video_failed' | 'video_review'
  | 'published' | 'abandoned';

interface VideoProject {
  id: string;
  topicId: string;
  status: ProjectStatus;
  renderEngine: 'manim' | 'remotion';
  ttsVoice: string;
  aspectRatio: 'landscape' | 'portrait';
  currentCodeVersion: CodeVersion | null;
  currentVideoAsset: VideoAsset | null;
  retryCount: number;
  createdAt: string;
  updatedAt: string;
}

// ═══ 镜头 ═══
interface Scene {
  sceneIndex: number;
  narration: string;
  description: string;
  code: string;
  estimatedDurationSeconds: number;
}

// ═══ 代码版本 ═══
interface CodeVersion {
  id: string;
  projectId: string;
  versionNumber: number;
  scenes: Scene[];
  factChecks: FactCheckItem[];
  renderEngine: 'manim' | 'remotion';
  aiModel: string;
  rejectionContext: RejectionContext | null;
  createdAt: string;
}

// ═══ 事实核查条目 ═══
interface FactCheckItem {
  claimText: string;
  sceneIndex: number;
  sourceUrl: string | null;
  sourceDescription: string;
  confidence: 'high' | 'medium' | 'low';
  isHypothesis: boolean;
  assumptions: string | null;
  controversy: string | null;
  reviewerVerdict: 'approved' | 'rejected' | 'needs_revision' | null;
  reviewerNote: string | null;
}

// ═══ 审核请求 ═══
interface ReviewRequest {
  gate: 'code' | 'video';
  verdict: 'approved' | 'rejected' | 'abandoned';
  rejectionType?: 'topic_invalid' | 'fact_error' | 'code_issue' | 'sync_issue';
  rejectionDetail?: string;
  targetStage?: 'code_generating';
  factCheckVerdicts?: Array<{
    index: number;
    verdict: 'approved' | 'rejected' | 'needs_revision';
    note: string;
  }>;
}

// ═══ 驳回上下文 ═══
interface RejectionContext {
  rejectionType: string;
  rejectionDetail: string;
  targetStage: string;
  rejectedAt: string;
}

// ═══ 异步任务 ═══
interface WorkerTask {
  id: string;
  projectId: string;
  taskType: 'generate_code' | 'render_video';
  engine: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  retryCount: number;
  maxRetries: number;
  createdAt: string;
  startedAt: string | null;
  completedAt: string | null;
}

// ═══ 视频产物 ═══
interface VideoAsset {
  id: string;
  projectId: string;
  codeVersionId: string;
  videoFileKey: string;
  durationSeconds: number;
  resolution: string;
  status: 'rendering' | 'completed' | 'failed';
  createdAt: string;
}

// ═══ 项目事件 ═══
interface ProjectEvent {
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
interface PerformanceRecord {
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
