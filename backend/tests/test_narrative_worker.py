import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from app.workers.narrative_worker import NarrativeWorker
from app.engines.ai.base import NarrativeResult
from app.engines.tts.base import TTSResult


def make_task(**kwargs):
    task = MagicMock()
    task.project_id = kwargs.get("project_id", uuid.uuid4())
    task.input_payload = kwargs.get("input_payload", {
        "topic_title": "测试选题",
        "topic_description": "测试描述",
        "render_engine": "manim",
        "rejection_context": None,
        "prompt_snapshot": {"base_prompt_version": "test"},
    })
    return task


@pytest.mark.asyncio
async def test_narrative_worker_supported_task_types():
    assert "generate_narrative" in NarrativeWorker.supported_task_types


@pytest.mark.asyncio
async def test_narrative_worker_execute_writes_narrative_version():
    task = make_task()
    project_id = task.project_id
    mock_provider = AsyncMock()
    mock_provider.model_name = "stub-model"
    mock_provider.generate_narrative = AsyncMock(
        return_value=NarrativeResult(
            scenes=[{
                "scene_index": 0,
                "narration": "旁白",
                "description": "描述",
                "beats": [{
                    "beat_index": 0,
                    "cue_text": "旁白",
                    "visual_action": "文字出现",
                    "fallback_weight": 1.0,
                }],
            }],
            fact_checks=[],
        )
    )

    mock_project = MagicMock()
    mock_project.id = project_id
    mock_project.tts_voice = "zh_female_1"
    mock_project.tts_engine = "doubao_2.0"
    mock_project.tts_speed = 1.1
    mock_project.current_narrative_version_id = None

    nv_id = uuid.uuid4()
    mock_nv = MagicMock()
    mock_nv.id = nv_id
    mock_nv.scenes = []

    # First DB session: create NarrativeVersion
    mock_db1 = MagicMock()
    mock_db1.get.return_value = mock_project
    mock_db1.execute.return_value.scalar.return_value = None

    def db1_flush():
        mock_nv.id = nv_id

    mock_db1.flush.side_effect = db1_flush

    # Capture the added NarrativeVersion to return its id
    added_nv = {}

    def db1_add(obj):
        if hasattr(obj, "version_number"):
            obj.id = nv_id
            added_nv["nv"] = obj

    mock_db1.add.side_effect = db1_add

    # Second DB session: update scenes + current_narrative_version_id
    mock_db2 = MagicMock()
    mock_db2.get.side_effect = lambda model, pk: mock_nv if "NarrativeVersion" in str(model) else mock_project

    mock_tts_engine = AsyncMock()
    mock_tts_result = TTSResult(
        success=True,
        output_path=None,
        error_message=None,
        audio_bytes=b"fake-mp3",
        duration_seconds=2.5,
    )
    mock_tts_engine.synthesize = AsyncMock(return_value=mock_tts_result)

    session_calls = []

    def get_session():
        if len(session_calls) == 0:
            session_calls.append(1)
            return mock_db1
        else:
            return mock_db2

    with patch("app.services.strategies.prompt_narrative.get_ai_provider", return_value=mock_provider), \
         patch("app.workers.narrative_worker.get_sync_session", side_effect=get_session), \
         patch("app.workers.narrative_worker.get_tts_engine", return_value=mock_tts_engine), \
         patch("app.workers.narrative_worker.upload_bytes"):
        worker = NarrativeWorker(worker_id="test", temporal_client=AsyncMock())
        result = await worker._execute(task)

    assert "narrative_version_id" in result
    assert result["scene_count"] == 1
    mock_db1.add.assert_called_once()
    mock_db1.commit.assert_called_once()
    mock_db2.commit.assert_called_once()
    synthesized_request = mock_tts_engine.synthesize.await_args.args[0]
    assert synthesized_request.speed == 1.1


@pytest.mark.asyncio
async def test_narrative_worker_passes_context_to_provider():
    task = make_task(input_payload={
        "topic_title": "T",
        "topic_description": "D",
        "render_engine": "manim",
        "rejection_context": None,
        "narrative_context": [{"text": "参考片段"}],
        "prompt_snapshot": {"base_prompt_version": "test"},
    })
    project_id = task.project_id
    captured_kwargs = {}

    async def fake_generate_narrative(**kwargs):
        captured_kwargs.update(kwargs)
        return NarrativeResult(
            scenes=[{
                "scene_index": 0,
                "narration": "旁白",
                "description": "描述",
                "beats": [{
                    "beat_index": 0,
                    "cue_text": "旁白",
                    "visual_action": "文字出现",
                }],
            }],
            fact_checks=[],
        )

    mock_provider = AsyncMock()
    mock_provider.model_name = "stub-model"
    mock_provider.generate_narrative = fake_generate_narrative

    mock_project = MagicMock()
    mock_project.id = project_id
    mock_project.tts_voice = "zizi"
    mock_project.tts_engine = "doubao_2.0"
    mock_project.tts_speed = 1.0
    mock_project.current_narrative_version_id = None

    nv_id = uuid.uuid4()
    mock_nv = MagicMock()
    mock_nv.id = nv_id
    mock_nv.scenes = []

    mock_db = MagicMock()
    mock_db.get.side_effect = lambda model, pid: mock_project if model.__name__ == "VideoProject" else mock_nv
    mock_db.execute.return_value.scalar.return_value = None

    with patch("app.services.strategies.prompt_narrative.get_ai_provider", return_value=mock_provider), \
         patch("app.workers.narrative_worker.get_sync_session", return_value=mock_db), \
         patch("app.workers.narrative_worker._synthesize_scenes_tts", new_callable=AsyncMock) as mock_tts, \
         patch("app.workers.narrative_worker.upload_bytes"):
        mock_tts.return_value = [{
            "scene_index": 0,
            "tts_status": "ready",
            "beats": [{"beat_index": 0, "cue_text": "旁白", "visual_action": "文字出现"}],
        }]
        worker = NarrativeWorker(worker_id="test", temporal_client=AsyncMock())
        await worker._execute(task)

    assert captured_kwargs.get("narrative_context") == [{"text": "参考片段"}]
    assert mock_tts.await_args.kwargs["tts_engine_name"] == "doubao_2.0"
    assert mock_tts.await_args.kwargs["tts_speed"] == 1.0
