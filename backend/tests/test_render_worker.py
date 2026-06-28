import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

def make_project(script_version_id=None):
    p = MagicMock()
    p.id = uuid.uuid4()
    p.topic_id = uuid.uuid4()
    p.tts_voice = "male_calm"
    p.render_engine = "manim"
    p.current_script_version_id = script_version_id or uuid.uuid4()
    p.current_video_asset_id = None
    return p


def make_script_version(project_id, scenes=None):
    sv = MagicMock()
    sv.id = uuid.uuid4()
    sv.project_id = project_id
    sv.render_engine = "manim"
    sv.scenes = scenes or [
        {"scene_index": 0, "narration": "Hello world", "description": "intro", "code": "self.play(Write(Text('Hello')))"},
        {"scene_index": 1, "narration": "Goodbye", "description": "outro", "code": "self.play(FadeOut(Text('Hello')))"},
    ]
    return sv


def make_task(project_id):
    t = MagicMock()
    t.id = uuid.uuid4()
    t.project_id = project_id
    t.input_payload = {}
    return t


@pytest.mark.asyncio
async def test_render_worker_success():
    from app.workers.render_worker import RenderWorker
    from app.engines.tts.base import TTSResult
    from app.engines.render.manim import _RenderResultWithBytes

    project = make_project()
    sv = make_script_version(project.id)
    task = make_task(project.id)

    tts_result = TTSResult(
        success=True, output_path=None, duration_seconds=None,
        error_message=None, audio_bytes=b"fake-audio"
    )
    render_result = _RenderResultWithBytes(
        success=True, output_path="/tmp/out.mp4", duration_seconds=10.0,
        error_message=None, render_log="OK", video_bytes=b"fake-video"
    )

    asset_mock = MagicMock()
    project_mock = MagicMock()

    mock_db = MagicMock()
    mock_db.get.side_effect = [project, sv, asset_mock, project_mock]

    mock_tts = AsyncMock()
    mock_tts.synthesize = AsyncMock(return_value=tts_result)

    mock_render = AsyncMock()
    mock_render.render = AsyncMock(return_value=render_result)

    with patch("app.workers.render_worker.get_sync_session", return_value=mock_db), \
         patch("app.workers.render_worker.get_tts_engine", return_value=mock_tts), \
         patch("app.workers.render_worker.get_render_engine", return_value=mock_render), \
         patch("app.workers.render_worker.upload_bytes") as mock_upload, \
         patch("app.workers.render_worker.download_to_file"):

        temporal_client = AsyncMock()
        worker = RenderWorker(worker_id="test", temporal_client=temporal_client)
        result = await worker._execute(task)

    assert result["video_file_key"].startswith("video/")
    assert "asset_id" in result
    # upload called: N audio files + 1 video
    assert mock_upload.call_count == 3  # 2 scenes + 1 video


@pytest.mark.asyncio
async def test_render_worker_tts_failure_raises():
    from app.workers.render_worker import RenderWorker
    from app.engines.tts.base import TTSResult

    project = make_project()
    sv = make_script_version(project.id)
    task = make_task(project.id)

    tts_fail = TTSResult(
        success=False, output_path=None, duration_seconds=None,
        error_message="API error", audio_bytes=b""
    )

    mock_db = MagicMock()
    mock_db.get.side_effect = [project, sv]
    mock_tts = AsyncMock()
    mock_tts.synthesize = AsyncMock(return_value=tts_fail)

    with patch("app.workers.render_worker.get_sync_session", return_value=mock_db), \
         patch("app.workers.render_worker.get_tts_engine", return_value=mock_tts), \
         patch("app.workers.render_worker.upload_bytes"):

        temporal_client = AsyncMock()
        worker = RenderWorker(worker_id="test", temporal_client=temporal_client)
        with pytest.raises(RuntimeError, match="TTS failed"):
            await worker._execute(task)
