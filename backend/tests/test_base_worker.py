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
    client = MagicMock()
    handle = AsyncMock()
    client.get_workflow_handle = MagicMock(return_value=handle)
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
        mock_db.get.return_value = mock_task
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
        mock_db.get.return_value = mock_task
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
        mock_db.get.return_value = mock_task
        mock_session_fn.return_value = mock_db
        await failing_worker._process_task(mock_task)

    assert mock_task.status == "failed"
    handle = mock_temporal_client.get_workflow_handle.return_value
    handle.signal.assert_called_once()
    signal_args = handle.signal.call_args
    assert signal_args[0][1]["success"] is False
