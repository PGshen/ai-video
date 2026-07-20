import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from app.workers.code_worker import CodeWorker
from app.engines.ai.base import CodeGenerationResult, CodeRepairResult


def make_task(**kwargs):
    task = MagicMock()
    task.project_id = kwargs.get("project_id", uuid.uuid4())
    task.input_payload = kwargs.get(
        "input_payload",
        {"render_engine": "manim", "prompt_snapshot": {"base_prompt_version": "test"}},
    )
    return task


@pytest.mark.asyncio
async def test_code_worker_supported_task_types():
    assert "generate_code" in CodeWorker.supported_task_types


@pytest.mark.asyncio
async def test_code_worker_execute_creates_code_version():
    task = make_task()
    narrative_scenes = [
        {
            "scene_index": 0,
            "narration": "旁白",
            "description": "描述",
            "duration_seconds": 5.0,
            "beats": [
                {
                    "beat_index": 0,
                    "cue_text": "旁白",
                    "visual_action": "文字出现",
                    "alignment_status": "interpolated",
                    "speech_start_seconds": 0.0,
                    "speech_end_seconds": 5.0,
                    "animation_start_seconds": 0.0,
                    "animation_end_seconds": 5.0,
                }
            ],
        }
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
    mock_project.aspect_ratio = "portrait"
    mock_project.current_code_version_id = None

    mock_db = MagicMock()
    mock_db.get.side_effect = lambda model, pk: (
        mock_project if model.__name__ == "VideoProject" else mock_narrative
    )
    mock_db.execute.return_value.scalar.return_value = None

    mock_engine = AsyncMock()
    mock_engine.validate_code = AsyncMock(return_value=(True, ""))

    with patch("app.workers.code_worker.get_ai_provider", return_value=mock_provider), \
         patch("app.workers.code_worker.get_sync_session", return_value=mock_db), \
         patch("app.workers.code_worker.get_render_engine", return_value=mock_engine):
        worker = CodeWorker(worker_id="test", temporal_client=AsyncMock())
        result = await worker._execute(task)

    assert "code_version_id" in result
    assert result["scene_count"] == 1
    mock_db.add.assert_called_once()
    assert mock_provider.generate_code.await_args.kwargs["aspect_ratio"] == "portrait"


def _scene(idx: int) -> dict:
    return {
        "scene_index": idx,
        "narration": f"旁白{idx}",
        "description": f"描述{idx}",
        "duration_seconds": 5.0,
        "beats": [
            {
                "beat_index": 0,
                "cue_text": f"旁白{idx}",
                "visual_action": "文字出现",
                "alignment_status": "interpolated",
                "speech_start_seconds": 0.0,
                "speech_end_seconds": 5.0,
                "animation_start_seconds": 0.0,
                "animation_end_seconds": 5.0,
            }
        ],
    }


@pytest.mark.asyncio
async def test_code_worker_repair_sends_full_scene_context():
    task = make_task()
    narrative_scenes = [_scene(0), _scene(1), _scene(2)]

    mock_provider = AsyncMock()
    mock_provider.model_name = "stub-model"
    mock_provider.generate_code = AsyncMock(
        return_value=CodeGenerationResult(codes=["# code 0", "# code 1", "# code 2"])
    )

    mock_narrative = MagicMock()
    mock_narrative.scenes = narrative_scenes
    mock_narrative.fact_checks = []

    mock_project = MagicMock()
    mock_project.id = task.project_id
    mock_project.current_narrative_version_id = uuid.uuid4()
    mock_project.render_engine = "manim"
    mock_project.aspect_ratio = "landscape"
    mock_project.current_code_version_id = None

    mock_db = MagicMock()
    mock_db.get.side_effect = lambda model, pk: (
        mock_project if model.__name__ == "VideoProject" else mock_narrative
    )
    mock_db.execute.return_value.scalar.return_value = None

    mock_engine = AsyncMock()
    mock_engine.validate_code = AsyncMock(
        side_effect=[(False, "scene 1: NameError: x is not defined"), (True, "")]
    )

    mock_repair_provider = AsyncMock()
    mock_repair_provider.repair_code = AsyncMock(
        return_value=CodeRepairResult(
            repairs=[{"scene_index": 1, "code": "# fixed code 1", "explanation": "fixed"}]
        )
    )

    def provider_factory(business):
        return mock_repair_provider if business == "code_repair" else mock_provider

    with patch("app.workers.code_worker.get_ai_provider", side_effect=provider_factory), \
         patch("app.workers.code_worker.get_sync_session", return_value=mock_db), \
         patch("app.workers.code_worker.get_render_engine", return_value=mock_engine):
        worker = CodeWorker(worker_id="test", temporal_client=AsyncMock())
        result = await worker._execute(task)

    assert result["scene_count"] == 3
    repair_kwargs = mock_repair_provider.repair_code.await_args.kwargs
    repaired_indices = {s["scene_index"] for s in repair_kwargs["scenes"]}
    assert repaired_indices == {0, 1, 2}  # full scene context, no scoping
    assert "context_truncated" not in repair_kwargs
