# Sprint 2: 脚本生成 + 内容审核 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 ScriptWorker AI 脚本生成全流程（Activity 补全 → Worker 执行 → Signal 回调），并完成前端脚本审核 UI（镜头浏览 + 逐条事实核查标注 + 通过/驳回/废弃）。

**Architecture:** ScriptWorker 轮询 `worker_tasks` 表，认领 `generate_script` 任务后调用 `ChatAIProvider.generate_script`，将结果写入 `script_versions`，通过 Temporal Signal 通知 Workflow。前端 `ProjectDetailPage` 展示镜头列表和事实核查表，用户逐条标注后一次性提交审核。

**Tech Stack:** Python FastAPI, SQLAlchemy (sync session in Workers/Activities), Temporal Python SDK, React + TypeScript, TanStack Query, shadcn/ui

## Global Constraints

- Python 包管理使用 `/Users/peng/.local/bin/uv run` 执行命令，不用裸 `uv`
- 前端使用 `PATH="/Users/peng/.nvm/versions/node/v24.11.0/bin:$PATH" pnpm`
- 不使用数据库外键约束，关联在应用层维护
- Worker 使用 `get_sync_session()`（同步 SQLAlchemy session），API 路由使用 `get_async_session()`
- Pydantic schemas 使用 `alias_generator=to_camel`，前端字段名为 camelCase
- 测试运行命令：`cd backend && /Users/peng/.local/bin/uv run pytest tests/ -v`
- 单测运行：`/Users/peng/.local/bin/uv run pytest tests/test_xxx.py::test_name -v`

---

## File Map

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/workflows/activities.py` | Modify | `submit_script_generation_task` 补全 input_payload |
| `backend/app/engines/ai/chat_provider.py` | Modify | `generate_script` 按引擎定制 prompt |
| `backend/app/workers/script_worker.py` | Modify | 实现 `_execute` |
| `backend/app/api/projects.py` | Modify | 新增 `GET /{id}/script` 端点 |
| `backend/app/api/reviews.py` | Modify | 写回 fact_check verdicts 后再发 Signal |
| `backend/tests/test_activities.py` | Create | Activity 单测 |
| `backend/tests/test_script_worker.py` | Create | ScriptWorker 单测 |
| `backend/tests/test_projects.py` | Modify | 补充 script 端点测试 |
| `backend/tests/test_reviews.py` | Create | review 写回 verdicts 测试 |
| `frontend/src/hooks/useProjects.ts` | Modify | 新增 `useProjectScript` hook |
| `frontend/src/components/review/FactCheckCard.tsx` | Create | 单条核查项组件 |
| `frontend/src/pages/ProjectDetailPage.tsx` | Modify | 完整审核 UI |

---

### Task 1: 补全 `submit_script_generation_task` Activity

**Files:**
- Modify: `backend/app/workflows/activities.py`
- Create: `backend/tests/test_activities.py`

**Interfaces:**
- Produces: `WorkerTask.input_payload` 含 `topic_title`, `topic_description`, `render_engine`, `rejection_context`（后续 Task 3 的 ScriptWorker 从这里读取）

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/test_activities.py`：

```python
import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4


def make_project(topic_id=None, render_engine="manim", temporal_workflow_id="wf-1"):
    p = MagicMock()
    p.id = uuid4()
    p.topic_id = topic_id or uuid4()
    p.render_engine = render_engine
    p.temporal_workflow_id = temporal_workflow_id
    return p


def make_topic(title="选题标题", description="选题描述"):
    t = MagicMock()
    t.title = title
    t.description = description
    return t


def test_submit_script_generation_task_populates_input_payload():
    """Activity 应从 topics 表读取 title/description 写入 input_payload"""
    project = make_project()
    topic = make_topic(title="生命中点", description="关于时间感知的选题")

    added_task = None

    def fake_add(obj):
        nonlocal added_task
        added_task = obj

    mock_db = MagicMock()
    mock_db.get.side_effect = lambda model, pk: (
        project if model.__name__ == "VideoProject" else topic
    )
    mock_db.add.side_effect = fake_add

    # 没有历史 rejection event
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = None
    mock_db.execute.return_value = mock_result

    with patch("app.workflows.activities.get_sync_session", return_value=mock_db):
        import asyncio
        from app.workflows.activities import submit_script_generation_task
        asyncio.run(submit_script_generation_task(str(project.id)))

    assert added_task is not None
    payload = added_task.input_payload
    assert payload["topic_title"] == "生命中点"
    assert payload["topic_description"] == "关于时间感知的选题"
    assert payload["render_engine"] == "manim"
    assert payload["rejection_context"] is None


def test_submit_script_generation_task_includes_rejection_context():
    """有历史驳回事件时，rejection_context 应被填入"""
    project = make_project()
    topic = make_topic()

    rejected_event = MagicMock()
    rejected_event.payload = {
        "rejection_type": "fact_error",
        "rejection_detail": "第2条事实有误",
    }

    added_task = None

    def fake_add(obj):
        nonlocal added_task
        added_task = obj

    mock_db = MagicMock()
    mock_db.get.side_effect = lambda model, pk: (
        project if model.__name__ == "VideoProject" else topic
    )
    mock_db.add.side_effect = fake_add
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = rejected_event
    mock_db.execute.return_value = mock_result

    with patch("app.workflows.activities.get_sync_session", return_value=mock_db):
        import asyncio
        from app.workflows.activities import submit_script_generation_task
        asyncio.run(submit_script_generation_task(str(project.id)))

    assert added_task.input_payload["rejection_context"] == rejected_event.payload
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && /Users/peng/.local/bin/uv run pytest tests/test_activities.py -v
```

预期：FAIL，`submit_script_generation_task` 的 `input_payload` 为 None。

- [ ] **Step 3: 实现 Activity 补全**

修改 `backend/app/workflows/activities.py`，替换 `submit_script_generation_task`：

```python
import uuid
from datetime import datetime, timezone
from sqlalchemy import select, desc
from temporalio import activity
from app.db import get_sync_session
from app.models.project import VideoProject
from app.models.project_event import ProjectEvent
from app.models.topic import Topic
from app.models.worker_task import WorkerTask


@activity.defn
async def submit_script_generation_task(project_id: str) -> None:
    db = get_sync_session()
    try:
        project = db.get(VideoProject, uuid.UUID(project_id))
        if project is None:
            return
        topic = db.get(Topic, project.topic_id)

        # 读取最近一次驳回事件作为 rejection_context
        rejection_event = db.execute(
            select(ProjectEvent)
            .where(
                ProjectEvent.project_id == project.id,
                ProjectEvent.event_type == "review_rejected",
            )
            .order_by(desc(ProjectEvent.created_at))
        ).scalars().first()
        rejection_context = rejection_event.payload if rejection_event else None

        task = WorkerTask(
            project_id=project.id,
            task_type="generate_script",
            engine=project.render_engine,
            status="pending",
            input_payload={
                "topic_title": topic.title if topic else "",
                "topic_description": topic.description if topic else "",
                "render_engine": project.render_engine,
                "rejection_context": rejection_context,
            },
            temporal_workflow_id=f"video-production-{project_id}",
            signal_name="script_generated",
            max_retries=3,
        )
        db.add(task)
        db.commit()
    finally:
        db.close()
```

注意：文件顶部已有部分 import，合并时去重，不要重复导入。

- [ ] **Step 4: 运行测试确认通过**

```bash
cd backend && /Users/peng/.local/bin/uv run pytest tests/test_activities.py -v
```

预期：PASS

- [ ] **Step 5: 运行全量测试确认无回归**

```bash
cd backend && /Users/peng/.local/bin/uv run pytest tests/ -v
```

预期：全部 PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/workflows/activities.py backend/tests/test_activities.py
git commit -m "feat: populate input_payload in submit_script_generation_task activity"
```

---

### Task 2: 按渲染引擎定制 `generate_script` Prompt

**Files:**
- Modify: `backend/app/engines/ai/chat_provider.py`
- Create: `backend/tests/test_script_prompt.py`

**Interfaces:**
- Consumes: `generate_script(topic_title, topic_description, render_engine, rejection_context)` — 已有签名不变
- Produces: system prompt 中的 code 字段说明包含引擎特定指令（Task 3 的 ScriptWorker 间接依赖此质量）

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/test_script_prompt.py`：

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.engines.ai.chat_provider import ChatAIProvider


def make_provider(response_json: str) -> ChatAIProvider:
    client = MagicMock()
    client.engine_name = "test"
    client.model_name = "test-model"
    client.create_chat_completion = AsyncMock(return_value=response_json)
    return ChatAIProvider(client=client)


VALID_SCRIPT_JSON = '''{
  "scenes": [
    {
      "scene_index": 0,
      "narration": "旁白",
      "description": "画面",
      "code": "class S(Scene): pass",
      "estimated_duration_seconds": 5.0
    }
  ],
  "fact_checks": [
    {
      "claim_text": "论断",
      "scene_index": 0,
      "source_url": null,
      "source_description": "来源",
      "confidence": "medium",
      "is_hypothesis": false,
      "assumptions": null,
      "controversy": null,
      "reviewer_verdict": null,
      "reviewer_note": null
    }
  ]
}'''


@pytest.mark.asyncio
async def test_generate_script_manim_prompt_contains_engine_hint():
    provider = make_provider(VALID_SCRIPT_JSON)
    await provider.generate_script(
        topic_title="测试选题",
        topic_description="描述",
        render_engine="manim",
    )
    call_args = provider.client.create_chat_completion.call_args
    messages = call_args[1]["messages"] if call_args[1] else call_args[0][0]
    system_content = messages[0]["content"]
    assert "Manim" in system_content or "manim" in system_content
    assert "Scene" in system_content


@pytest.mark.asyncio
async def test_generate_script_remotion_prompt_contains_engine_hint():
    provider = make_provider(VALID_SCRIPT_JSON)
    await provider.generate_script(
        topic_title="测试选题",
        topic_description="描述",
        render_engine="remotion",
    )
    call_args = provider.client.create_chat_completion.call_args
    messages = call_args[1]["messages"] if call_args[1] else call_args[0][0]
    system_content = messages[0]["content"]
    assert "Remotion" in system_content or "remotion" in system_content


@pytest.mark.asyncio
async def test_generate_script_unknown_engine_uses_fallback():
    """未知引擎不应抛异常，走通用 prompt"""
    provider = make_provider(VALID_SCRIPT_JSON)
    result = await provider.generate_script(
        topic_title="测试选题",
        topic_description="描述",
        render_engine="unknown_engine",
    )
    assert len(result.scenes) == 1
    assert len(result.fact_checks) == 1


@pytest.mark.asyncio
async def test_generate_script_with_rejection_context():
    """驳回重生成时，rejection_context 应出现在 user message 中"""
    provider = make_provider(VALID_SCRIPT_JSON)
    rejection_context = {"rejection_type": "fact_error", "rejection_detail": "第1条事实有误"}
    await provider.generate_script(
        topic_title="测试选题",
        topic_description="描述",
        render_engine="manim",
        rejection_context=rejection_context,
    )
    call_args = provider.client.create_chat_completion.call_args
    messages = call_args[1]["messages"] if call_args[1] else call_args[0][0]
    user_content = messages[-1]["content"]
    assert "fact_error" in user_content or "rejection" in user_content.lower()
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && /Users/peng/.local/bin/uv run pytest tests/test_script_prompt.py -v
```

预期：2 个引擎 hint 测试 FAIL（当前 prompt 无引擎特定内容）。

- [ ] **Step 3: 实现引擎特定 prompt**

修改 `backend/app/engines/ai/chat_provider.py`，在 `ChatAIProvider` 类中添加引擎映射，并更新 `generate_script`：

```python
# 在 ChatAIProvider 类定义中添加（类级别常量）
_ENGINE_CODE_PROMPTS: dict[str, str] = {
    "manim": """\
- code 字段使用 Python Manim 代码。每个镜头定义一个继承自 Scene 的类，在 construct() 方法中编写动画逻辑。
- 在需要音频的位置使用占位符 {{AUDIO_SCENE_N}}（N 为 scene_index），例如 {{AUDIO_SCENE_0}}。
- 示例：
  class TitleScene(Scene):
      def construct(self):
          {{AUDIO_SCENE_0}}
          title = Text("标题").scale(1.5)
          self.play(Write(title))""",
    "remotion": """\
- code 字段使用 React/TypeScript Remotion 组件。每个镜头导出一个函数组件，使用 useCurrentFrame 和 useVideoConfig hook。
- 音频通过 <Audio src={AUDIO_SCENE_N} /> 组件注入（N 为 scene_index），需从 props 接收 audioSrc。
- 示例：
  export const TitleScene: React.FC<{audioSrc?: string}> = ({audioSrc}) => {
    const frame = useCurrentFrame();
    return <AbsoluteFill>{audioSrc && <Audio src={audioSrc} />}<h1>标题</h1></AbsoluteFill>;
  };""",
}
_ENGINE_CODE_PROMPT_FALLBACK = "- code 字段填写适合所选渲染引擎的代码，在需要音频处使用 {{AUDIO_SCENE_N}} 占位符。"
```

然后更新 `generate_script` 方法中的 `system_prompt`，将引擎特定部分拼入：

```python
async def generate_script(
    self,
    topic_title: str,
    topic_description: str,
    render_engine: str,
    rejection_context: dict | None = None,
) -> ScriptGenerationResult:
    engine_hint = self._ENGINE_CODE_PROMPTS.get(render_engine, self._ENGINE_CODE_PROMPT_FALLBACK)

    system_prompt = f"""\
你是知识视频脚本生成器。请严格输出 JSON object，不要输出 Markdown。

JSON 格式示例：
{{
  "scenes": [
    {{
      "scene_index": 0,
      "narration": "旁白文稿",
      "description": "画面描述",
      "code": "渲染代码",
      "estimated_duration_seconds": 12.5
    }}
  ],
  "fact_checks": [
    {{
      "claim_text": "需要核查的具体论断",
      "scene_index": 0,
      "source_url": null,
      "source_description": "建议核查来源或说明",
      "confidence": "medium",
      "is_hypothesis": false,
      "assumptions": null,
      "controversy": null,
      "reviewer_verdict": null,
      "reviewer_note": null
    }}
  ]
}}

渲染引擎：{render_engine}
{engine_hint}

要求：
- scenes 是镜头数组，scene_index 从 0 连续递增。
- 每个镜头包含 narration、description、code、estimated_duration_seconds。
- fact_checks 覆盖脚本中的关键事实论断和可能争议点。
- 只能输出合法 JSON object。"""

    user_payload: dict = {
        "topic_title": topic_title,
        "topic_description": topic_description,
        "render_engine": render_engine,
    }
    if rejection_context:
        user_payload["rejection_context"] = rejection_context
        user_note = "（注意：这是一次重新生成，请参考 rejection_context 中的驳回原因修正问题）"
    else:
        user_note = ""

    content = await self.client.create_chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"请为以下选题生成知识视频脚本 JSON{user_note}：\n"
                + json.dumps(user_payload, ensure_ascii=False),
            },
        ],
        response_format={"type": "json_object"},
        max_tokens=self.script_max_tokens,
    )
    payload = parse_json_object(content)
    scenes = payload.get("scenes")
    fact_checks = payload.get("fact_checks")
    if not isinstance(scenes, list) or not isinstance(fact_checks, list):
        raise ValueError("Script response must contain scenes and fact_checks arrays")
    return ScriptGenerationResult(scenes=scenes, fact_checks=fact_checks)
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd backend && /Users/peng/.local/bin/uv run pytest tests/test_script_prompt.py -v
```

预期：PASS

- [ ] **Step 5: 运行全量测试**

```bash
cd backend && /Users/peng/.local/bin/uv run pytest tests/ -v
```

预期：全部 PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/engines/ai/chat_provider.py backend/tests/test_script_prompt.py
git commit -m "feat: add render-engine-specific prompts to generate_script"
```

---

### Task 3: 实现 `ScriptWorker._execute`

**Files:**
- Modify: `backend/app/workers/script_worker.py`
- Create: `backend/tests/test_script_worker.py`

**Interfaces:**
- Consumes: `task.input_payload` = `{topic_title, topic_description, render_engine, rejection_context}` (from Task 1)
- Consumes: `get_ai_provider().generate_script(...)` → `ScriptGenerationResult` (from Task 2)
- Produces: `{"script_version_id": str, "scene_count": int, "fact_check_count": int}` — BaseWorker 将此作为 Signal payload 的一部分

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/test_script_worker.py`：

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime, timezone
from app.workers.script_worker import ScriptWorker
from app.engines.ai.base import ScriptGenerationResult


def make_task(project_id=None, render_engine="manim"):
    t = MagicMock()
    t.id = uuid4()
    t.project_id = project_id or uuid4()
    t.input_payload = {
        "topic_title": "测试选题",
        "topic_description": "描述",
        "render_engine": render_engine,
        "rejection_context": None,
    }
    return t


def make_project(id=None, topic_id=None, render_engine="manim"):
    p = MagicMock()
    p.id = id or uuid4()
    p.topic_id = topic_id or uuid4()
    p.render_engine = render_engine
    p.current_script_version_id = None
    return p


@pytest.mark.asyncio
async def test_execute_creates_script_version():
    task = make_task()
    project = make_project(id=task.project_id)

    added_objects = []

    def fake_add(obj):
        added_objects.append(obj)

    mock_db = MagicMock()
    mock_db.get.return_value = project
    mock_db.add.side_effect = fake_add
    # max version_number query returns None (no existing versions)
    mock_result = MagicMock()
    mock_result.scalar.return_value = None
    mock_db.execute.return_value = mock_result

    fake_ai_result = ScriptGenerationResult(
        scenes=[
            {
                "scene_index": 0,
                "narration": "旁白",
                "description": "画面",
                "code": "class S(Scene): pass",
                "estimated_duration_seconds": 5.0,
            }
        ],
        fact_checks=[
            {
                "claim_text": "论断",
                "scene_index": 0,
                "source_url": None,
                "source_description": "来源",
                "confidence": "medium",
                "is_hypothesis": False,
                "assumptions": None,
                "controversy": None,
                "reviewer_verdict": None,
                "reviewer_note": None,
            }
        ],
    )

    mock_provider = AsyncMock()
    mock_provider.model_name = "test-model"
    mock_provider.generate_script = AsyncMock(return_value=fake_ai_result)

    worker = ScriptWorker(
        worker_id="test-worker",
        temporal_client=AsyncMock(),
    )

    with (
        patch("app.workers.script_worker.get_sync_session", return_value=mock_db),
        patch("app.workers.script_worker.get_ai_provider", return_value=mock_provider),
    ):
        output = await worker._execute(task)

    assert output["scene_count"] == 1
    assert output["fact_check_count"] == 1
    assert "script_version_id" in output

    # project.current_script_version_id should be updated
    assert project.current_script_version_id is not None

    # a ScriptVersion should have been added
    from app.models.script_version import ScriptVersion
    script_versions = [o for o in added_objects if isinstance(o, ScriptVersion)]
    assert len(script_versions) == 1
    sv = script_versions[0]
    assert sv.version_number == 1
    assert sv.scenes == fake_ai_result.scenes
    assert sv.fact_checks == fake_ai_result.fact_checks
    assert sv.render_engine == "manim"
    assert sv.ai_model == "test-model"


@pytest.mark.asyncio
async def test_execute_increments_version_number():
    """第二次生成时 version_number 应为 2"""
    task = make_task()
    project = make_project(id=task.project_id)

    mock_db = MagicMock()
    mock_db.get.return_value = project
    mock_result = MagicMock()
    mock_result.scalar.return_value = 1  # existing max version = 1
    mock_db.execute.return_value = mock_result

    fake_ai_result = ScriptGenerationResult(
        scenes=[{"scene_index": 0, "narration": "", "description": "", "code": "", "estimated_duration_seconds": 1.0}],
        fact_checks=[],
    )
    mock_provider = AsyncMock()
    mock_provider.model_name = "m"
    mock_provider.generate_script = AsyncMock(return_value=fake_ai_result)

    worker = ScriptWorker(worker_id="w", temporal_client=AsyncMock())

    added_objects = []
    mock_db.add.side_effect = added_objects.append

    with (
        patch("app.workers.script_worker.get_sync_session", return_value=mock_db),
        patch("app.workers.script_worker.get_ai_provider", return_value=mock_provider),
    ):
        await worker._execute(task)

    from app.models.script_version import ScriptVersion
    sv = next(o for o in added_objects if isinstance(o, ScriptVersion))
    assert sv.version_number == 2
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && /Users/peng/.local/bin/uv run pytest tests/test_script_worker.py -v
```

预期：FAIL，`_execute` 抛 `NotImplementedError`。

- [ ] **Step 3: 实现 ScriptWorker._execute**

替换 `backend/app/workers/script_worker.py` 全部内容：

```python
from sqlalchemy import func, select
from app.db import get_sync_session
from app.engines.ai.factory import get_ai_provider
from app.models.project import VideoProject
from app.models.script_version import ScriptVersion
from app.workers.base import BaseWorker


class ScriptWorker(BaseWorker):
    supported_task_types = ["generate_script"]

    async def _execute(self, task) -> dict:
        payload = task.input_payload or {}
        topic_title = payload.get("topic_title", "")
        topic_description = payload.get("topic_description", "")
        render_engine = payload.get("render_engine", "manim")
        rejection_context = payload.get("rejection_context")

        provider = get_ai_provider()
        result = await provider.generate_script(
            topic_title=topic_title,
            topic_description=topic_description,
            render_engine=render_engine,
            rejection_context=rejection_context,
        )

        db = get_sync_session()
        try:
            project = db.get(VideoProject, task.project_id)
            if project is None:
                raise ValueError(f"Project {task.project_id} not found")

            max_version = db.execute(
                select(func.max(ScriptVersion.version_number)).where(
                    ScriptVersion.project_id == task.project_id
                )
            ).scalar()
            next_version = (max_version or 0) + 1

            sv = ScriptVersion(
                project_id=task.project_id,
                version_number=next_version,
                scenes=result.scenes,
                fact_checks=result.fact_checks,
                render_engine=render_engine,
                ai_model=provider.model_name,
                rejection_context=rejection_context,
            )
            db.add(sv)
            db.flush()  # get sv.id before commit

            project.current_script_version_id = sv.id
            db.commit()

            return {
                "script_version_id": str(sv.id),
                "scene_count": len(result.scenes),
                "fact_check_count": len(result.fact_checks),
            }
        finally:
            db.close()
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd backend && /Users/peng/.local/bin/uv run pytest tests/test_script_worker.py -v
```

预期：PASS

- [ ] **Step 5: 运行全量测试**

```bash
cd backend && /Users/peng/.local/bin/uv run pytest tests/ -v
```

预期：全部 PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/workers/script_worker.py backend/tests/test_script_worker.py
git commit -m "feat: implement ScriptWorker._execute with AI script generation"
```

---

### Task 4: 新增 `GET /api/projects/{id}/script` 端点

**Files:**
- Modify: `backend/app/api/projects.py`
- Modify: `backend/tests/test_projects.py`

**Interfaces:**
- Produces: `ScriptVersionSchema` JSON（前端 Task 6 的 `useProjectScript` 消费）

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_projects.py` 末尾追加：

```python
def test_get_script_returns_script_version(client, auth_headers, mock_db):
    from app.models.project import VideoProject
    from app.models.script_version import ScriptVersion
    from datetime import datetime, timezone
    from uuid import uuid4

    project_id = uuid4()
    script_id = uuid4()

    project = MagicMock()
    project.id = project_id
    project.current_script_version_id = script_id

    sv = MagicMock()
    sv.id = script_id
    sv.project_id = project_id
    sv.version_number = 1
    sv.scenes = [{"scene_index": 0, "narration": "旁白", "description": "画面", "code": "", "estimated_duration_seconds": 5.0}]
    sv.fact_checks = []
    sv.render_engine = "manim"
    sv.ai_model = "test-model"
    sv.rejection_context = None
    sv.created_at = datetime.now(timezone.utc)

    mock_db.get.side_effect = lambda model, pk: project if pk == project_id else sv

    response = client.get(f"/api/projects/{project_id}/script", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["versionNumber"] == 1
    assert len(data["scenes"]) == 1


def test_get_script_returns_404_if_no_script(client, auth_headers, mock_db):
    from uuid import uuid4
    project = MagicMock()
    project.current_script_version_id = None
    mock_db.get.return_value = project

    response = client.get(f"/api/projects/{uuid4()}/script", headers=auth_headers)
    assert response.status_code == 404


def test_get_script_returns_404_if_project_missing(client, auth_headers, mock_db):
    mock_db.get.return_value = None
    from uuid import uuid4
    response = client.get(f"/api/projects/{uuid4()}/script", headers=auth_headers)
    assert response.status_code == 404
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && /Users/peng/.local/bin/uv run pytest tests/test_projects.py::test_get_script_returns_script_version tests/test_projects.py::test_get_script_returns_404_if_no_script -v
```

预期：FAIL（404，端点不存在）

- [ ] **Step 3: 实现端点**

在 `backend/app/api/projects.py` 的 `list_script_versions` 路由之前（或之后）添加：

```python
from app.models.script_version import ScriptVersion
from app.schemas.project import ScriptVersionSchema

@router.get("/{project_id}/script", response_model=ScriptVersionSchema)
async def get_current_script(
    project_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_api_key),
):
    project = await db.get(VideoProject, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.current_script_version_id:
        raise HTTPException(status_code=404, detail="No script generated yet")
    sv = await db.get(ScriptVersion, project.current_script_version_id)
    if sv is None:
        raise HTTPException(status_code=404, detail="Script version not found")
    return sv
```

同时在文件顶部的 import 中补充（如尚未 import）：
```python
from app.models.script_version import ScriptVersion
from app.schemas.project import ScriptVersionSchema
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd backend && /Users/peng/.local/bin/uv run pytest tests/test_projects.py -v
```

预期：全部 PASS

- [ ] **Step 5: 运行全量测试**

```bash
cd backend && /Users/peng/.local/bin/uv run pytest tests/ -v
```

预期：全部 PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/projects.py backend/tests/test_projects.py
git commit -m "feat: add GET /api/projects/{id}/script endpoint"
```

---

### Task 5: 扩展审核 API — 写回 fact_check verdicts

**Files:**
- Modify: `backend/app/api/reviews.py`
- Create: `backend/tests/test_reviews.py`

**Interfaces:**
- Consumes: `ReviewRequest.fact_check_verdicts: list[FactCheckVerdict] | None`（schema 已有）
- Produces: `script_versions.fact_checks` JSONB 中每条 item 的 `reviewer_verdict`/`reviewer_note` 被更新

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/test_reviews.py`：

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from datetime import datetime, timezone
from app.config import settings


def make_project(temporal_workflow_id="wf-1", script_version_id=None):
    p = MagicMock()
    p.id = uuid4()
    p.temporal_workflow_id = temporal_workflow_id
    p.current_script_version_id = script_version_id or uuid4()
    return p


def make_script_version(fact_checks=None):
    sv = MagicMock()
    sv.id = uuid4()
    sv.fact_checks = fact_checks or [
        {"claim_text": "论断0", "scene_index": 0, "source_url": None,
         "source_description": "来源", "confidence": "medium", "is_hypothesis": False,
         "assumptions": None, "controversy": None,
         "reviewer_verdict": None, "reviewer_note": None},
        {"claim_text": "论断1", "scene_index": 0, "source_url": None,
         "source_description": "来源", "confidence": "low", "is_hypothesis": False,
         "assumptions": None, "controversy": None,
         "reviewer_verdict": None, "reviewer_note": None},
    ]
    return sv


def auth_headers():
    return {"X-API-Key": settings.API_KEY}


def test_review_with_verdicts_updates_fact_checks(client, mock_db, mock_temporal):
    project = make_project()
    sv = make_script_version()

    def db_get(model, pk):
        if str(pk) == str(project.id):
            return project
        return sv

    mock_db.get = AsyncMock(side_effect=db_get)
    mock_handle = AsyncMock()
    mock_temporal.get_workflow_handle = MagicMock(return_value=mock_handle)

    response = client.post(
        f"/api/projects/{project.id}/review",
        headers=auth_headers(),
        json={
            "gate": "script",
            "verdict": "approved",
            "factCheckVerdicts": [
                {"index": 0, "verdict": "approved", "note": ""},
                {"index": 1, "verdict": "rejected", "note": "来源不可靠"},
            ],
        },
    )
    assert response.status_code == 200

    # fact_checks should be updated
    updated = sv.fact_checks
    assert updated[0]["reviewer_verdict"] == "approved"
    assert updated[1]["reviewer_verdict"] == "rejected"
    assert updated[1]["reviewer_note"] == "来源不可靠"

    # signal should be sent
    mock_handle.signal.assert_called_once()


def test_review_without_verdicts_still_sends_signal(client, mock_db, mock_temporal):
    project = make_project()
    mock_db.get = AsyncMock(return_value=project)
    mock_handle = AsyncMock()
    mock_temporal.get_workflow_handle = MagicMock(return_value=mock_handle)

    response = client.post(
        f"/api/projects/{project.id}/review",
        headers=auth_headers(),
        json={"gate": "script", "verdict": "approved"},
    )
    assert response.status_code == 200
    mock_handle.signal.assert_called_once()


def test_review_abandoned_sends_signal_without_script_load(client, mock_db, mock_temporal):
    """废弃操作不需要加载 script_version"""
    project = make_project()
    mock_db.get = AsyncMock(return_value=project)
    mock_handle = AsyncMock()
    mock_temporal.get_workflow_handle = MagicMock(return_value=mock_handle)

    response = client.post(
        f"/api/projects/{project.id}/review",
        headers=auth_headers(),
        json={"gate": "script", "verdict": "abandoned"},
    )
    assert response.status_code == 200
    call_args = mock_handle.signal.call_args[0]
    assert call_args[1]["verdict"] == "abandoned"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && /Users/peng/.local/bin/uv run pytest tests/test_reviews.py -v
```

预期：`test_review_with_verdicts_updates_fact_checks` FAIL（当前实现不写回 verdicts）

- [ ] **Step 3: 实现 verdict 写回**

替换 `backend/app/api/reviews.py` 全部内容：

```python
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from temporalio.client import Client as TemporalClient
from app.auth import verify_api_key
from app.db import get_async_session
from app.deps import get_temporal_client
from app.models.project import VideoProject
from app.models.script_version import ScriptVersion
from app.schemas.review import ReviewRequest

router = APIRouter(prefix="/api/projects", tags=["reviews"])


@router.post("/{project_id}/review")
async def submit_review(
    project_id: UUID,
    body: ReviewRequest,
    db: AsyncSession = Depends(get_async_session),
    temporal: TemporalClient = Depends(get_temporal_client),
    _=Depends(verify_api_key),
):
    project = await db.get(VideoProject, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.temporal_workflow_id:
        raise HTTPException(status_code=400, detail="Project has no active workflow")

    # 写回 fact_check verdicts（仅 script gate 且有标注时）
    if body.gate == "script" and body.fact_check_verdicts:
        sv = await db.get(ScriptVersion, project.current_script_version_id)
        if sv and isinstance(sv.fact_checks, list):
            verdict_map = {v.index: v for v in body.fact_check_verdicts}
            updated = []
            for item in sv.fact_checks:
                item = dict(item)
                idx = item.get("scene_index") if "scene_index" not in item else None
                # fact_checks are indexed by position in list
                updated.append(item)
            # index by list position
            fact_checks = list(sv.fact_checks)
            for v in body.fact_check_verdicts:
                if 0 <= v.index < len(fact_checks):
                    fact_checks[v.index] = {
                        **dict(fact_checks[v.index]),
                        "reviewer_verdict": v.verdict,
                        "reviewer_note": v.note or None,
                    }
            sv.fact_checks = fact_checks
            # SQLAlchemy JSONB mutation detection requires flag_modified
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(sv, "fact_checks")
            await db.commit()

    signal_name = "script_review" if body.gate == "script" else "video_review"
    payload = {
        "verdict": body.verdict,
        "rejection_type": body.rejection_type,
        "rejection_detail": body.rejection_detail,
        "target_stage": body.target_stage,
    }

    handle = temporal.get_workflow_handle(project.temporal_workflow_id)
    await handle.signal(signal_name, payload)
    return {"status": "ok"}
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd backend && /Users/peng/.local/bin/uv run pytest tests/test_reviews.py -v
```

预期：PASS

- [ ] **Step 5: 运行全量测试**

```bash
cd backend && /Users/peng/.local/bin/uv run pytest tests/ -v
```

预期：全部 PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/reviews.py backend/tests/test_reviews.py
git commit -m "feat: write fact_check verdicts back to script_version on review submit"
```

---

### Task 6: 前端 — `useProjectScript` hook + 类型确认

**Files:**
- Modify: `frontend/src/hooks/useProjects.ts`

**Interfaces:**
- Produces: `useProjectScript(projectId)` → TanStack Query，返回 `ScriptVersion | undefined`（Task 7 的 ProjectDetailPage 消费）

- [ ] **Step 1: 在 `useProjects.ts` 末尾追加 hook**

```typescript
export function useProjectScript(projectId: string) {
  return useQuery<ScriptVersion>({
    queryKey: ["projects", projectId, "script"],
    queryFn: () => api.get<ScriptVersion>(`/api/projects/${projectId}/script`),
    enabled: !!projectId,
    retry: false,  // 404（未生成）不重试
  });
}
```

同时在文件顶部 import 中补充 `ScriptVersion`：

```typescript
import type { VideoProject, ProjectEvent, ReviewRequest, ScriptVersion } from "@/types";
```

- [ ] **Step 2: 验证类型一致性**

确认 `frontend/src/types/index.ts` 中 `ScriptVersion` 的字段名与后端 `ScriptVersionSchema` camelCase 对应：

| 后端 snake_case | 前端 camelCase | 状态 |
|-----------------|---------------|------|
| `version_number` | `versionNumber` | ✓ 已有 |
| `fact_checks` | `factChecks` | ✓ 已有 |
| `render_engine` | `renderEngine` | ✓ 已有 |
| `ai_model` | `aiModel` | ✓ 已有 |
| `rejection_context` | `rejectionContext` | ✓ 已有 |

无需修改 types。

- [ ] **Step 3: 验证前端编译**

```bash
cd frontend && PATH="/Users/peng/.nvm/versions/node/v24.11.0/bin:$PATH" pnpm build 2>&1 | tail -20
```

预期：build 成功，无 TypeScript 错误。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/hooks/useProjects.ts
git commit -m "feat: add useProjectScript hook for fetching current script version"
```

---

### Task 7: 前端 — FactCheckCard 组件 + ProjectDetailPage 完整实现

**Files:**
- Create: `frontend/src/components/review/FactCheckCard.tsx`
- Modify: `frontend/src/pages/ProjectDetailPage.tsx`

**Interfaces:**
- Consumes: `useProject(id)` → `VideoProject`（已有）
- Consumes: `useProjectScript(id)` → `ScriptVersion`（Task 6）
- Consumes: `useSubmitReview()` mutation（已有）

- [ ] **Step 1: 创建 `FactCheckCard` 组件**

新建 `frontend/src/components/review/FactCheckCard.tsx`：

```typescript
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { FactCheckItem } from "@/types";

type Verdict = "approved" | "rejected" | "needs_revision";

interface FactCheckCardProps {
  item: FactCheckItem;
  index: number;
  verdict: Verdict | null;
  note: string;
  onVerdictChange: (index: number, verdict: Verdict, note: string) => void;
}

const CONFIDENCE_COLOR: Record<string, string> = {
  high: "bg-green-100 text-green-800",
  medium: "bg-yellow-100 text-yellow-800",
  low: "bg-red-100 text-red-800",
};

export function FactCheckCard({
  item,
  index,
  verdict,
  note,
  onVerdictChange,
}: FactCheckCardProps) {
  const [localNote, setLocalNote] = useState(note);

  const handleVerdictClick = (v: Verdict) => {
    onVerdictChange(index, v, localNote);
  };

  const handleNoteChange = (n: string) => {
    setLocalNote(n);
    if (verdict) {
      onVerdictChange(index, verdict, n);
    }
  };

  return (
    <div className="border rounded-lg p-4 space-y-3">
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-medium leading-snug flex-1">{item.claimText}</p>
        <div className="flex gap-1 shrink-0">
          <Badge variant="outline" className="text-xs">镜头 {item.sceneIndex}</Badge>
          <Badge className={`text-xs ${CONFIDENCE_COLOR[item.confidence] ?? ""}`}>
            {item.confidence}
          </Badge>
          {item.isHypothesis && (
            <Badge variant="secondary" className="text-xs">假设</Badge>
          )}
        </div>
      </div>

      {item.sourceDescription && (
        <p className="text-xs text-muted-foreground">
          来源：{item.sourceUrl ? (
            <a href={item.sourceUrl} target="_blank" rel="noreferrer" className="underline">
              {item.sourceDescription}
            </a>
          ) : item.sourceDescription}
        </p>
      )}

      {item.controversy && (
        <p className="text-xs text-amber-700 bg-amber-50 rounded px-2 py-1">
          争议：{item.controversy}
        </p>
      )}

      {item.assumptions && (
        <p className="text-xs text-muted-foreground">假设条件：{item.assumptions}</p>
      )}

      {/* Verdict 选择 */}
      <div className="flex gap-2 pt-1">
        {(["approved", "needs_revision", "rejected"] as Verdict[]).map((v) => (
          <button
            key={v}
            onClick={() => handleVerdictClick(v)}
            className={[
              "px-3 py-1 rounded-full text-xs font-medium border transition-colors",
              verdict === v
                ? v === "approved"
                  ? "bg-green-500 text-white border-green-500"
                  : v === "rejected"
                  ? "bg-red-500 text-white border-red-500"
                  : "bg-yellow-500 text-white border-yellow-500"
                : "bg-background border-border text-muted-foreground hover:bg-muted",
            ].join(" ")}
          >
            {v === "approved" ? "通过" : v === "rejected" ? "驳回" : "需修改"}
          </button>
        ))}
      </div>

      {/* 备注（仅在 rejected/needs_revision 时展开） */}
      {verdict && verdict !== "approved" && (
        <div className="space-y-1">
          <Label className="text-xs">审核备注</Label>
          <Textarea
            value={localNote}
            onChange={(e) => handleNoteChange(e.target.value)}
            placeholder="请说明问题..."
            className="text-xs min-h-[60px]"
          />
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: 实现 `ProjectDetailPage`**

替换 `frontend/src/pages/ProjectDetailPage.tsx` 全部内容：

```typescript
import { useState, useMemo } from "react";
import { useParams } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import { FactCheckCard } from "@/components/review/FactCheckCard";
import { useProject, useProjectScript, useSubmitReview } from "@/hooks/useProjects";
import type { ProjectStatus } from "@/types";

type Verdict = "approved" | "rejected" | "needs_revision";

interface VerdictState {
  verdict: Verdict;
  note: string;
}

const STATUS_LABELS: Record<ProjectStatus, string> = {
  draft: "草稿",
  script_generating: "AI 生成脚本中…",
  script_failed: "脚本生成失败",
  script_review: "待审核",
  video_generating: "视频渲染中…",
  video_failed: "视频生成失败",
  video_review: "待视频审核",
  published: "已发布",
  abandoned: "已废弃",
};

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: project, isLoading: projectLoading } = useProject(id!);
  const { data: script, isLoading: scriptLoading } = useProjectScript(id!);
  const submitReview = useSubmitReview();

  const [verdicts, setVerdicts] = useState<Record<number, VerdictState>>({});
  const [rejectionDetail, setRejectionDetail] = useState("");
  const [showRejectInput, setShowRejectInput] = useState(false);

  const allMarked = useMemo(() => {
    if (!script) return false;
    return script.factChecks.every((_, i) => verdicts[i] !== undefined);
  }, [script, verdicts]);

  const handleVerdictChange = (index: number, verdict: Verdict, note: string) => {
    setVerdicts((prev) => ({ ...prev, [index]: { verdict, note } }));
  };

  const buildVerdictList = () =>
    Object.entries(verdicts).map(([i, v]) => ({
      index: Number(i),
      verdict: v.verdict,
      note: v.note || null,
    }));

  const handleApprove = () => {
    submitReview.mutate({
      projectId: id!,
      gate: "script",
      verdict: "approved",
      factCheckVerdicts: buildVerdictList(),
    });
  };

  const handleReject = () => {
    if (!showRejectInput) {
      setShowRejectInput(true);
      return;
    }
    submitReview.mutate({
      projectId: id!,
      gate: "script",
      verdict: "rejected",
      rejectionDetail,
      factCheckVerdicts: buildVerdictList(),
    });
  };

  const handleAbandon = () => {
    if (!window.confirm("确认废弃该项目？此操作不可撤销。")) return;
    submitReview.mutate({
      projectId: id!,
      gate: "script",
      verdict: "abandoned",
    });
  };

  if (projectLoading) {
    return <div className="p-6 text-muted-foreground">加载中…</div>;
  }
  if (!project) {
    return <div className="p-6 text-destructive">项目不存在</div>;
  }

  const isScriptReview = project.status === "script_review";
  const retryCount = project.retryCount;
  const canReject = retryCount < 3;

  return (
    <div className="flex flex-col h-full">
      {/* 顶部状态栏 */}
      <div className="flex items-center gap-3 px-6 py-4 border-b">
        <h1 className="text-lg font-semibold truncate flex-1">项目详情</h1>
        <Badge variant="outline">{STATUS_LABELS[project.status] ?? project.status}</Badge>
        {retryCount > 0 && (
          <span className="text-xs text-muted-foreground">已驳回 {retryCount} 次</span>
        )}
      </div>

      {/* 非审核状态提示 */}
      {project.status === "script_generating" && (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center space-y-2">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto" />
            <p className="text-muted-foreground">AI 正在生成脚本，请稍候…</p>
          </div>
        </div>
      )}

      {project.status === "script_failed" && (
        <div className="flex-1 flex items-center justify-center">
          <p className="text-destructive">脚本生成失败，请联系管理员</p>
        </div>
      )}

      {!["script_generating", "script_failed", "script_review"].includes(project.status) &&
        project.status !== "draft" && (
          <div className="flex-1 flex items-center justify-center">
            <p className="text-muted-foreground">
              当前状态：{STATUS_LABELS[project.status] ?? project.status}
            </p>
          </div>
        )}

      {/* 脚本审核主区域（script_review 状态 或 已有脚本时展示） */}
      {(isScriptReview || script) && !["script_generating", "script_failed"].includes(project.status) && (
        <div className="flex flex-1 overflow-hidden">
          {/* 左：镜头列表 */}
          <div className="w-1/2 border-r flex flex-col">
            <div className="px-4 py-3 border-b text-sm font-medium">
              镜头列表（{script?.scenes.length ?? 0} 个）
            </div>
            <ScrollArea className="flex-1">
              <div className="p-4 space-y-4">
                {scriptLoading && (
                  <p className="text-sm text-muted-foreground">加载脚本…</p>
                )}
                {script?.scenes.map((scene) => (
                  <div key={scene.sceneIndex} className="border rounded-lg p-4 space-y-2">
                    <div className="flex items-center gap-2">
                      <Badge variant="secondary" className="text-xs">
                        镜头 {scene.sceneIndex}
                      </Badge>
                      <span className="text-xs text-muted-foreground">
                        ~{scene.estimatedDurationSeconds}s
                      </span>
                    </div>
                    <p className="text-sm font-medium">{scene.description}</p>
                    <p className="text-sm text-muted-foreground leading-relaxed">
                      {scene.narration}
                    </p>
                    <details className="text-xs">
                      <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
                        查看代码
                      </summary>
                      <pre className="mt-2 p-2 bg-muted rounded overflow-x-auto text-xs leading-relaxed">
                        {scene.code}
                      </pre>
                    </details>
                  </div>
                ))}
              </div>
            </ScrollArea>
          </div>

          {/* 右：事实核查表 */}
          <div className="w-1/2 flex flex-col">
            <div className="px-4 py-3 border-b text-sm font-medium">
              事实核查（{script?.factChecks.length ?? 0} 条）
            </div>
            <ScrollArea className="flex-1">
              <div className="p-4 space-y-4">
                {script?.factChecks.map((item, idx) => (
                  <FactCheckCard
                    key={idx}
                    item={item}
                    index={idx}
                    verdict={verdicts[idx]?.verdict ?? null}
                    note={verdicts[idx]?.note ?? ""}
                    onVerdictChange={handleVerdictChange}
                  />
                ))}
              </div>
            </ScrollArea>

            {/* 底部操作栏 */}
            {isScriptReview && (
              <div className="border-t p-4 space-y-3">
                {showRejectInput && (
                  <Textarea
                    value={rejectionDetail}
                    onChange={(e) => setRejectionDetail(e.target.value)}
                    placeholder="请说明驳回原因（AI 重新生成时会参考此信息）"
                    className="text-sm min-h-[80px]"
                  />
                )}
                <div className="flex gap-2">
                  <Button
                    onClick={handleApprove}
                    disabled={!allMarked || submitReview.isPending}
                    className="flex-1"
                  >
                    通过
                  </Button>
                  {canReject && (
                    <Button
                      variant="outline"
                      onClick={handleReject}
                      disabled={submitReview.isPending}
                      className="flex-1"
                    >
                      {showRejectInput ? "确认驳回" : "驳回重生成"}
                    </Button>
                  )}
                  <Button
                    variant="destructive"
                    onClick={handleAbandon}
                    disabled={submitReview.isPending}
                  >
                    废弃
                  </Button>
                </div>
                {!allMarked && script && script.factChecks.length > 0 && (
                  <p className="text-xs text-muted-foreground text-center">
                    请为所有核查条目标注审核结果后再提交
                  </p>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: 验证前端编译**

```bash
cd frontend && PATH="/Users/peng/.nvm/versions/node/v24.11.0/bin:$PATH" pnpm build 2>&1 | tail -30
```

预期：build 成功，无 TypeScript 错误。

- [ ] **Step 4: 手动验证（可选，需服务启动）**

如果 `make up && make dev-backend && make dev-frontend` 均已启动：
1. 创建一个选题并设为 `stocked`
2. 从选题创建项目
3. 在 Temporal UI（localhost:8080）确认 Workflow 已启动
4. 访问 `localhost:5173/projects/{id}`
5. 状态为 `script_generating` 时应显示 spinner
6. Worker 生成完毕后（或手动发 Signal）状态变 `script_review` 后页面展示镜头和核查表

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/review/FactCheckCard.tsx frontend/src/pages/ProjectDetailPage.tsx
git commit -m "feat: implement ProjectDetailPage with script review UI and FactCheckCard"
```

---

## 验收标准

1. `cd backend && /Users/peng/.local/bin/uv run pytest tests/ -v` 全部通过
2. `cd frontend && PATH=".../node/v24.11.0/bin:$PATH" pnpm build` 无报错
3. 创建项目后 Workflow 触发 → ScriptWorker 执行 → `script_versions` 有记录 → 项目状态变 `script_review`
4. ProjectDetailPage 在 `script_review` 状态展示镜头列表和事实核查表
5. 逐条标注完成后「通过」按钮可点击，提交后 `script_versions.fact_checks` 中有 `reviewer_verdict`
6. 驳回后项目重回 `script_generating`，`retry_count >= 3` 后驳回按钮消失
7. 废弃后项目状态变 `abandoned`
