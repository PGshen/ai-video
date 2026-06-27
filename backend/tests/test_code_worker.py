import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from app.workers.code_worker import CodeWorker
from app.engines.ai.base import CodeGenerationResult


def make_task(**kwargs):
    task = MagicMock()
    task.project_id = kwargs.get("project_id", uuid.uuid4())
    task.input_payload = kwargs.get("input_payload", {"render_engine": "manim"})
    return task


@pytest.mark.asyncio
async def test_code_worker_supported_task_types():
    assert "generate_code" in CodeWorker.supported_task_types


@pytest.mark.asyncio
async def test_code_worker_execute_creates_script_version():
    task = make_task()
    narrative_scenes = [
        {"scene_index": 0, "narration": "旁白", "description": "描述", "estimated_duration_seconds": 5.0}
    ]

    mock_provider = AsyncMock()
    mock_provider.model_name = "stub-model"
    mock_provider.generate_code = AsyncMock(
        return_value=CodeGenerationResult(codes=["# code 0"])
    )

    mock_narrative = MagicMock()
    mock_narrative.scenes = narrative_scenes
    mock_narrative.fact_checks = []

    mock_project = MagicMock()
    mock_project.id = task.project_id
    mock_project.current_narrative_version_id = uuid.uuid4()
    mock_project.render_engine = "manim"
    mock_project.current_script_version_id = None

    mock_db = MagicMock()
    mock_db.get.side_effect = lambda model, pk: (
        mock_project if model.__name__ == "VideoProject" else mock_narrative
    )
    mock_db.execute.return_value.scalar.return_value = None

    with patch("app.workers.code_worker.get_ai_provider", return_value=mock_provider), \
         patch("app.workers.code_worker.get_sync_session", return_value=mock_db):
        worker = CodeWorker(worker_id="test", temporal_client=AsyncMock())
        result = await worker._execute(task)

    assert "script_version_id" in result
    assert result["scene_count"] == 1
    mock_db.add.assert_called_once()
