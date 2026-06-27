import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from app.workers.narrative_worker import NarrativeWorker
from app.engines.ai.base import NarrativeResult


def make_task(**kwargs):
    task = MagicMock()
    task.project_id = kwargs.get("project_id", uuid.uuid4())
    task.input_payload = kwargs.get("input_payload", {
        "topic_title": "测试选题",
        "topic_description": "测试描述",
        "render_engine": "manim",
        "rejection_context": None,
    })
    return task


@pytest.mark.asyncio
async def test_narrative_worker_supported_task_types():
    assert "generate_narrative" in NarrativeWorker.supported_task_types


@pytest.mark.asyncio
async def test_narrative_worker_execute_writes_narrative_version():
    task = make_task()
    mock_provider = AsyncMock()
    mock_provider.model_name = "stub-model"
    mock_provider.generate_narrative = AsyncMock(
        return_value=NarrativeResult(
            scenes=[{"scene_index": 0, "narration": "旁白", "description": "描述"}],
            fact_checks=[],
        )
    )

    mock_project = MagicMock()
    mock_project.id = task.project_id
    mock_project.current_narrative_version_id = None

    mock_db = MagicMock()
    mock_db.get.return_value = mock_project
    mock_db.execute.return_value.scalar.return_value = None

    with patch("app.workers.narrative_worker.get_ai_provider", return_value=mock_provider), \
         patch("app.workers.narrative_worker.get_sync_session", return_value=mock_db):
        worker = NarrativeWorker(worker_id="test", temporal_client=AsyncMock())
        result = await worker._execute(task)

    assert "narrative_version_id" in result
    assert result["scene_count"] == 1
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
