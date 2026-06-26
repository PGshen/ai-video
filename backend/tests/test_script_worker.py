import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
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


FAKE_SCENES = [
    {
        "scene_index": 0,
        "narration": "旁白",
        "description": "画面",
        "code": "class S(Scene): pass",
        "estimated_duration_seconds": 5.0,
    }
]
FAKE_FACT_CHECKS = [
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
]


@pytest.mark.asyncio
async def test_execute_creates_script_version():
    task = make_task()
    project = make_project(id=task.project_id)

    added_objects = []

    mock_db = MagicMock()
    mock_db.get.return_value = project
    mock_db.add.side_effect = added_objects.append
    mock_result = MagicMock()
    mock_result.scalar.return_value = None  # no existing versions
    mock_db.execute.return_value = mock_result

    fake_ai_result = ScriptGenerationResult(scenes=FAKE_SCENES, fact_checks=FAKE_FACT_CHECKS)
    mock_provider = AsyncMock()
    mock_provider.model_name = "test-model"
    mock_provider.generate_script = AsyncMock(return_value=fake_ai_result)

    worker = ScriptWorker(worker_id="test-worker", temporal_client=AsyncMock())

    with (
        patch("app.workers.script_worker.get_sync_session", return_value=mock_db),
        patch("app.workers.script_worker.get_ai_provider", return_value=mock_provider),
    ):
        output = await worker._execute(task)

    assert output["scene_count"] == 1
    assert output["fact_check_count"] == 1
    assert "script_version_id" in output

    assert project.current_script_version_id is not None

    from app.models.script_version import ScriptVersion
    script_versions = [o for o in added_objects if isinstance(o, ScriptVersion)]
    assert len(script_versions) == 1
    sv = script_versions[0]
    assert sv.version_number == 1
    assert sv.scenes == FAKE_SCENES
    assert sv.fact_checks == FAKE_FACT_CHECKS
    assert sv.render_engine == "manim"
    assert sv.ai_model == "test-model"


@pytest.mark.asyncio
async def test_execute_increments_version_number():
    """第二次生成时 version_number 应为 2"""
    task = make_task()
    project = make_project(id=task.project_id)

    added_objects = []

    mock_db = MagicMock()
    mock_db.get.return_value = project
    mock_db.add.side_effect = added_objects.append
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

    with (
        patch("app.workers.script_worker.get_sync_session", return_value=mock_db),
        patch("app.workers.script_worker.get_ai_provider", return_value=mock_provider),
    ):
        await worker._execute(task)

    from app.models.script_version import ScriptVersion
    sv = next(o for o in added_objects if isinstance(o, ScriptVersion))
    assert sv.version_number == 2


@pytest.mark.asyncio
async def test_execute_passes_rejection_context_to_ai():
    """rejection_context 应传递给 AI provider"""
    task = make_task()
    task.input_payload["rejection_context"] = {"rejection_type": "fact_error", "rejection_detail": "有误"}
    project = make_project(id=task.project_id)

    mock_db = MagicMock()
    mock_db.get.return_value = project
    mock_result = MagicMock()
    mock_result.scalar.return_value = None
    mock_db.execute.return_value = mock_result

    fake_ai_result = ScriptGenerationResult(scenes=FAKE_SCENES, fact_checks=FAKE_FACT_CHECKS)
    mock_provider = AsyncMock()
    mock_provider.model_name = "m"
    mock_provider.generate_script = AsyncMock(return_value=fake_ai_result)

    worker = ScriptWorker(worker_id="w", temporal_client=AsyncMock())

    with (
        patch("app.workers.script_worker.get_sync_session", return_value=mock_db),
        patch("app.workers.script_worker.get_ai_provider", return_value=mock_provider),
    ):
        await worker._execute(task)

    call_kwargs = mock_provider.generate_script.call_args[1]
    assert call_kwargs["rejection_context"] == {"rejection_type": "fact_error", "rejection_detail": "有误"}
