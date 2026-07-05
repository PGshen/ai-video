# 卡死阶段重置功能 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让运维人员在 project 卡死于 `narrative_generating`/`code_generating`/`video_generating` 三个自动化阶段时，通过一个 API 端点手动重置，使其恢复正常执行，且不引入信号重复消费的竞态问题。

**Architecture:** 新增一个纯 DB 操作的 activity 函数 `reset_stuck_stage`，直接复用已有的 `submit_narrative_task`/`submit_code_task`/`submit_video_generation_task` 函数重新入队任务；workflow 本身不动，等新任务完成后走既有信号路径自然恢复。为防止旧的（可能仍在运行）worker 完成时发出多余信号，在 `BaseWorker._process_task` 中增加"执行完成后重新检查任务是否已被标记 cancelled"的校验。

**Tech Stack:** FastAPI, SQLAlchemy (sync `Session` in `app/workflows/activities.py` + async `AsyncSession` in API layer), pytest + pytest-asyncio, unittest.mock。

## Global Constraints

- 使用绝对路径调用工具：`/Users/peng/.local/bin/uv run pytest tests/ -v`（沙箱 PATH 不含 `~/.local/bin`）。
- 不修改 `VideoProductionWorkflow`（`app/workflows/video_production.py`）的信号处理逻辑。
- 不修改 `project.retry_count`。
- `WorkerTask.status` 新增取值 `"cancelled"`，该列是自由 `String(20)`，不需要 Alembic 迁移。
- 遵循现有测试风格：`app/workflows/activities.py` 相关测试 mock `get_sync_session`；API 路由测试使用 `tests/conftest.py` 里的 `client`/`mock_db`/`mock_temporal` fixture。

---

### Task 1: `BaseWorker` 增加 cancelled 竞态校验

**Files:**
- Modify: `backend/app/workers/base.py`
- Test: `backend/tests/test_base_worker.py`

**Interfaces:**
- Consumes: 无新依赖，仅在已有 `_process_task` 中增加逻辑。
- Produces: `BaseWorker._is_cancelled(db, task_id) -> bool`，供本任务内部使用；后续任务不直接依赖它。

- [ ] **Step 1: 写失败测试——任务在执行期间被标记 cancelled 时，成功路径不应写回 completed / 不应发信号**

在 `backend/tests/test_base_worker.py` 末尾追加：

```python
@pytest.mark.asyncio
async def test_process_task_success_skips_signal_when_cancelled_during_execution(worker, mock_task, mock_temporal_client):
    with patch("app.workers.base.get_sync_session") as mock_session_fn:
        mock_db = MagicMock()
        mock_db.get.return_value = mock_task
        mock_db.execute.return_value.scalar_one_or_none.return_value = "cancelled"
        mock_session_fn.return_value = mock_db

        await worker._process_task(mock_task)

    assert mock_task.status == "processing"
    mock_temporal_client.get_workflow_handle.return_value.signal.assert_not_called()


@pytest.mark.asyncio
async def test_process_task_failure_skips_retry_when_cancelled_during_execution(worker, mock_task, mock_temporal_client):
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
        mock_db.get.return_value = mock_task
        mock_db.execute.return_value.scalar_one_or_none.return_value = "cancelled"
        mock_session_fn.return_value = mock_db
        await failing_worker._process_task(mock_task)

    assert mock_task.status == "processing"
    mock_temporal_client.get_workflow_handle.return_value.signal.assert_not_called()
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && /Users/peng/.local/bin/uv run pytest tests/test_base_worker.py -v`
Expected: 新增的两个测试 FAIL（因为 `mock_task.status` 目前会被写成 `"completed"` / `"pending"`，而不是保持 `"processing"`）。

- [ ] **Step 3: 实现最小改动**

修改 `backend/app/workers/base.py`：

在文件顶部导入区加入 `select`（其余导入不变）：

```python
import asyncio
from datetime import datetime, timezone
import logging
from typing import Any
from fastapi import logger
from temporalio.client import Client
from sqlalchemy import select, text
from app.db import get_sync_session
```

在类内新增一个私有方法（放在 `_process_task` 之前）：

```python
    def _is_cancelled(self, db: Any, task_id: Any) -> bool:
        from app.models.worker_task import WorkerTask
        current_status = db.execute(
            select(WorkerTask.status).where(WorkerTask.id == task_id)
        ).scalar_one_or_none()
        return current_status == "cancelled"
```

修改 `_process_task` 成功路径（在 `output = await self._execute(orm_task)` 之后、写回 `orm_task.status = "completed"` 之前插入校验）：

```python
            output = await self._execute(orm_task)
            if self._is_cancelled(db, task_id):
                logger.info(
                    "[BaseWorker] task=%s was cancelled during execution, discarding result",
                    task_id,
                )
                return
            orm_task.status = "completed"
            orm_task.output_payload = output
            orm_task.completed_at = datetime.now(timezone.utc)
            db.commit()
```

修改 `_process_task` 异常路径（在 `if orm_task is None: return` 之后、`if orm_task.retry_count < orm_task.max_retries:` 之前插入校验）：

```python
            if orm_task is None:
                return

            if self._is_cancelled(db, task_id):
                logger.info(
                    "[BaseWorker] task=%s was cancelled during execution, discarding failure",
                    task_id,
                )
                return

            if orm_task.retry_count < orm_task.max_retries:
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd backend && /Users/peng/.local/bin/uv run pytest tests/test_base_worker.py -v`
Expected: 全部 5 个测试（3 个已有 + 2 个新增）PASS。

- [ ] **Step 5: 提交**

```bash
cd /Users/peng/Me/Ai/ai-video
git add backend/app/workers/base.py backend/tests/test_base_worker.py
git commit -m "feat: guard BaseWorker against stale signals from cancelled tasks"
```

---

### Task 2: 新增 `reset_stuck_stage` activity 函数

**Files:**
- Modify: `backend/app/workflows/activities.py`
- Test: `backend/tests/test_workflow_activities.py`

**Interfaces:**
- Consumes: `app.models.project.VideoProject`（已导入）、`app.models.worker_task.WorkerTask`（已导入）、`app.models.project_event.ProjectEvent`（已导入）、`select`（已导入）、已有的 `submit_narrative_task(project_id: str) -> None`、`submit_code_task(project_id: str) -> None`、`submit_video_generation_task(project_id: str) -> None`。
- Produces: `async def reset_stuck_stage(project_id: str) -> dict`，返回 `{"stage": str, "cancelled_task_ids": list[str]}`；抛出 `LookupError`（project 不存在）或 `ValueError`（当前状态不可重置）。供 Task 3 的 API 路由调用。

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_workflow_activities.py` 顶部导入区加入：

```python
from unittest.mock import AsyncMock
from app.workflows.activities import reset_stuck_stage
```

在文件末尾追加：

```python
@pytest.mark.asyncio
async def test_reset_stuck_stage_cancels_old_tasks_and_resubmits():
    project_id = uuid4()
    project = SimpleNamespace(id=project_id, status="code_generating")
    stuck_task = SimpleNamespace(id=uuid4(), status="processing")
    db = MagicMock()
    db.get.return_value = project
    db.execute.return_value.scalars.return_value.all.return_value = [stuck_task]

    with patch("app.workflows.activities.get_sync_session", return_value=db), \
         patch("app.workflows.activities.submit_code_task", new_callable=AsyncMock) as mock_submit:
        result = await reset_stuck_stage(str(project_id))

    assert stuck_task.status == "cancelled"
    mock_submit.assert_awaited_once_with(str(project_id))
    event = db.add.call_args.args[0]
    assert event.event_type == "stuck_reset"
    assert event.payload["stage"] == "generate_code"
    assert event.payload["cancelled_task_ids"] == [str(stuck_task.id)]
    assert result == {"stage": "generate_code", "cancelled_task_ids": [str(stuck_task.id)]}


@pytest.mark.asyncio
async def test_reset_stuck_stage_rejects_non_resettable_status():
    project_id = uuid4()
    project = SimpleNamespace(id=project_id, status="script_review")
    db = MagicMock()
    db.get.return_value = project

    with patch("app.workflows.activities.get_sync_session", return_value=db):
        with pytest.raises(ValueError):
            await reset_stuck_stage(str(project_id))


@pytest.mark.asyncio
async def test_reset_stuck_stage_missing_project_raises_lookup_error():
    db = MagicMock()
    db.get.return_value = None

    with patch("app.workflows.activities.get_sync_session", return_value=db):
        with pytest.raises(LookupError):
            await reset_stuck_stage(str(uuid4()))
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && /Users/peng/.local/bin/uv run pytest tests/test_workflow_activities.py -v`
Expected: 新增的 3 个测试 FAIL，报错 `ImportError: cannot import name 'reset_stuck_stage'`。

- [ ] **Step 3: 实现最小实现**

修改 `backend/app/workflows/activities.py`，在 `submit_code_task` 函数定义之后（文件末尾）追加：

```python
_RESETTABLE_STAGES: dict[str, str] = {
    "narrative_generating": "generate_narrative",
    "code_generating": "generate_code",
    "video_generating": "render_video",
}


async def reset_stuck_stage(project_id: str) -> dict:
    db = get_sync_session()
    try:
        project = db.get(VideoProject, uuid.UUID(project_id))
        if project is None:
            raise LookupError(f"Project {project_id} not found")

        task_type = _RESETTABLE_STAGES.get(project.status)
        if task_type is None:
            raise ValueError(
                f"Project status '{project.status}' is not a resettable stage"
            )

        stuck_tasks = db.execute(
            select(WorkerTask).where(
                WorkerTask.project_id == project.id,
                WorkerTask.task_type == task_type,
                WorkerTask.status.in_(["pending", "processing"]),
            )
        ).scalars().all()
        cancelled_ids = [str(t.id) for t in stuck_tasks]
        for t in stuck_tasks:
            t.status = "cancelled"

        db.add(ProjectEvent(
            project_id=project.id,
            event_type="stuck_reset",
            from_status=project.status,
            to_status=project.status,
            actor="operator",
            payload={"stage": task_type, "cancelled_task_ids": cancelled_ids},
        ))
        db.commit()
    finally:
        db.close()

    if task_type == "generate_narrative":
        await submit_narrative_task(project_id)
    elif task_type == "generate_code":
        await submit_code_task(project_id)
    elif task_type == "render_video":
        await submit_video_generation_task(project_id)

    return {"stage": task_type, "cancelled_task_ids": cancelled_ids}
```

注意：`reset_stuck_stage` 不加 `@activity.defn` 装饰器——它不通过 Temporal 调用，只是被 API 层直接 `await`，装饰它会误导为"这是一个需要在 Temporal Worker 中注册的 activity"。

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd backend && /Users/peng/.local/bin/uv run pytest tests/test_workflow_activities.py -v`
Expected: 全部测试 PASS（含之前已有的 `test_script_review_status_event_keeps_exact_version_reference`）。

- [ ] **Step 5: 提交**

```bash
cd /Users/peng/Me/Ai/ai-video
git add backend/app/workflows/activities.py backend/tests/test_workflow_activities.py
git commit -m "feat: add reset_stuck_stage activity to recover projects stuck in automated stages"
```

---

### Task 3: 新增 `POST /api/projects/{project_id}/reset` API 端点

**Files:**
- Modify: `backend/app/api/reviews.py`
- Test: `backend/tests/test_reviews.py`

**Interfaces:**
- Consumes: `reset_stuck_stage(project_id: str) -> dict`（Task 2 产出），异常类型 `LookupError` / `ValueError`。
- Produces: HTTP 端点 `POST /api/projects/{project_id}/reset`，成功返回 `{"status": "reset", "project_id": str, "stage": str, "cancelled_task_count": int}`；project 不存在 404；状态不可重置 400。此端点是本功能的最终对外接口，无后续任务依赖它。

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_reviews.py` 顶部导入区加入：

```python
from unittest.mock import patch
```

（如果已存在 `from unittest.mock import AsyncMock, MagicMock`，改成 `from unittest.mock import AsyncMock, MagicMock, patch`。）

在文件末尾追加：

```python
def test_reset_project_returns_stage_and_cancelled_count(client):
    project_id = uuid4()

    async def fake_reset(pid):
        assert pid == str(project_id)
        return {"stage": "generate_code", "cancelled_task_ids": ["t1", "t2"]}

    with patch("app.api.reviews.reset_stuck_stage", new=fake_reset):
        response = client.post(
            f"/api/projects/{project_id}/reset",
            headers=_auth(),
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "reset"
    assert body["projectId"] == str(project_id)
    assert body["stage"] == "generate_code"
    assert body["cancelledTaskCount"] == 2


def test_reset_project_not_found_returns_404(client):
    project_id = uuid4()

    async def fake_reset(pid):
        raise LookupError(f"Project {pid} not found")

    with patch("app.api.reviews.reset_stuck_stage", new=fake_reset):
        response = client.post(
            f"/api/projects/{project_id}/reset",
            headers=_auth(),
        )

    assert response.status_code == 404


def test_reset_project_non_resettable_status_returns_400(client):
    project_id = uuid4()

    async def fake_reset(pid):
        raise ValueError("Project status 'script_review' is not a resettable stage")

    with patch("app.api.reviews.reset_stuck_stage", new=fake_reset):
        response = client.post(
            f"/api/projects/{project_id}/reset",
            headers=_auth(),
        )

    assert response.status_code == 400
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd backend && /Users/peng/.local/bin/uv run pytest tests/test_reviews.py -v`
Expected: 新增的 3 个测试 FAIL，`404 Not Found`（因为路由尚不存在，会命中 FastAPI 默认 404）或 `AttributeError` 之类。

- [ ] **Step 3: 实现最小实现**

修改 `backend/app/api/reviews.py`，在导入区加入：

```python
from app.workflows.activities import reset_stuck_stage
```

在 `submit_review` 函数之后（文件末尾）追加新路由：

```python
@router.post("/{project_id}/reset")
async def reset_project(
    project_id: UUID,
    _=Depends(verify_api_key),
):
    try:
        result = await reset_stuck_stage(str(project_id))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "status": "reset",
        "projectId": str(project_id),
        "stage": result["stage"],
        "cancelledTaskCount": len(result["cancelled_task_ids"]),
    }
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `cd backend && /Users/peng/.local/bin/uv run pytest tests/test_reviews.py -v`
Expected: 全部测试 PASS。

- [ ] **Step 5: 跑全量后端测试确认无回归**

Run: `cd backend && /Users/peng/.local/bin/uv run pytest tests/ -v`
Expected: 全部测试 PASS，无失败。

- [ ] **Step 6: 提交**

```bash
cd /Users/peng/Me/Ai/ai-video
git add backend/app/api/reviews.py backend/tests/test_reviews.py
git commit -m "feat: add POST /api/projects/{id}/reset endpoint to recover stuck projects"
```

---

## 完成后核对

- [ ] `narrative_generating` / `code_generating` / `video_generating` 三种状态均可通过接口重置（Task 2 测试已分别覆盖 `generate_code` 路径，其余两条路径逻辑相同，映射表已包含）。
- [ ] 非法状态（如 `script_review`、`draft`）调用返回 400。
- [ ] project 不存在返回 404。
- [ ] 旧的 `processing`/`pending` `WorkerTask` 行被标记为 `cancelled`，且 `BaseWorker` 在这些行被 cancel 后不会再发送信号或改写状态。
- [ ] 全量测试套件 `pytest tests/ -v` 通过。
