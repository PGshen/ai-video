import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def make_project(code_version_id=None, aspect_ratio="landscape"):
    p = MagicMock()
    p.id = uuid.uuid4()
    p.topic_id = uuid.uuid4()
    p.tts_voice = "male_calm"
    p.render_engine = "manim"
    p.aspect_ratio = aspect_ratio
    p.current_code_version_id = code_version_id or uuid.uuid4()
    p.current_video_asset_id = None
    return p


def make_code_version(project_id, scenes=None):
    code_version = MagicMock()
    code_version.id = uuid.uuid4()
    code_version.project_id = project_id
    code_version.render_engine = "manim"
    code_version.scenes = scenes or [
        {
            "scene_index": 0,
            "narration": "Hello world",
            "description": "intro",
            "code": "self.play(Write(Text('Hello')))",
            "audio_key": "audio/proj/code_version/scene_0.mp3",
            "duration_seconds": 3.5,
            "tts_status": "ready",
        },
        {
            "scene_index": 1,
            "narration": "Goodbye",
            "description": "outro",
            "code": "self.play(FadeOut(Text('Hello')))",
            "audio_key": "audio/proj/code_version/scene_1.mp3",
            "duration_seconds": 2.0,
            "tts_status": "ready",
        },
    ]
    return code_version


def make_task(project_id, code_version_id=None):
    t = MagicMock()
    t.id = uuid.uuid4()
    t.project_id = project_id
    t.code_version_id = code_version_id or uuid.uuid4()
    t.input_payload = {}
    return t


@pytest.mark.asyncio
async def test_render_worker_success():
    from app.workers.render_worker import RenderWorker
    from app.engines.render.base import RenderResultWithBytes as _RenderResultWithBytes

    project = make_project()
    code_version = make_code_version(project.id)
    task = make_task(project.id, code_version.id)

    render_result = _RenderResultWithBytes(
        success=True, output_path="/tmp/out.mp4", duration_seconds=10.0,
        error_message=None, render_log="OK", video_bytes=b"fake-video"
    )

    asset_mock = MagicMock()
    project_mock = MagicMock()

    mock_db = MagicMock()
    mock_db.get.side_effect = [project, code_version, asset_mock, project_mock]

    mock_render = AsyncMock()
    mock_render.render = AsyncMock(return_value=render_result)

    with patch("app.workers.render_worker.get_sync_session", return_value=mock_db), \
         patch("app.workers.render_worker.get_render_engine", return_value=mock_render), \
         patch("app.workers.render_worker.upload_bytes") as mock_upload, \
         patch("app.workers.render_worker.download_to_file") as mock_download:

        temporal_client = AsyncMock()
        worker = RenderWorker(worker_id="test", temporal_client=temporal_client)
        result = await worker._execute(task)

    assert result["video_file_key"].startswith("video/")
    assert "asset_id" in result
    assert result["code_version_id"] == str(code_version.id)
    # download called once per scene that has audio_key (2 scenes)
    assert mock_download.call_count == 2
    # upload called once for video only
    assert mock_upload.call_count == 1


@pytest.mark.asyncio
async def test_render_worker_uses_task_code_version_not_current_project_version():
    from app.workers.render_worker import RenderWorker
    from app.engines.render.base import RenderResultWithBytes
    from app.models.code_version import CodeVersion

    frozen_code_version_id = uuid.uuid4()
    project = make_project(code_version_id=uuid.uuid4())
    frozen_code_version = make_code_version(project.id)
    frozen_code_version.id = frozen_code_version_id
    frozen_code_version.version_number = 7
    task = make_task(project.id, frozen_code_version_id)
    db = MagicMock()
    db.get.side_effect = [project, frozen_code_version, MagicMock(), MagicMock()]
    render = AsyncMock()
    render.render = AsyncMock(return_value=RenderResultWithBytes(
        success=True, output_path="/tmp/out.mp4", duration_seconds=1.0,
        error_message=None, render_log="OK", video_bytes=b"fake-video",
    ))

    with patch("app.workers.render_worker.get_sync_session", return_value=db), \
         patch("app.workers.render_worker.get_render_engine", return_value=render), \
         patch("app.workers.render_worker.upload_bytes"), \
         patch("app.workers.render_worker.download_to_file"):
        result = await RenderWorker(worker_id="test", temporal_client=AsyncMock())._execute(task)

    assert db.get.call_args_list[1].args == (CodeVersion, frozen_code_version_id)
    assert result["code_version_id"] == str(frozen_code_version_id)


@pytest.mark.asyncio
async def test_render_worker_uses_portrait_resolution():
    from app.workers.render_worker import RenderWorker
    from app.engines.render.base import RenderResultWithBytes

    project = make_project(aspect_ratio="portrait")
    code_version = make_code_version(project.id)
    task = make_task(project.id, code_version.id)
    mock_db = MagicMock()
    mock_db.get.side_effect = [project, code_version, MagicMock(), MagicMock()]
    captured_resolution = None

    async def capture_render(request, work_dir):
        nonlocal captured_resolution
        captured_resolution = request.resolution
        return RenderResultWithBytes(
            success=True,
            output_path="/tmp/out.mp4",
            duration_seconds=10.0,
            error_message=None,
            render_log="OK",
            video_bytes=b"fake-video",
        )

    mock_render = AsyncMock()
    mock_render.render = AsyncMock(side_effect=capture_render)

    with patch("app.workers.render_worker.get_sync_session", return_value=mock_db), \
         patch("app.workers.render_worker.get_render_engine", return_value=mock_render), \
         patch("app.workers.render_worker.upload_bytes"), \
         patch("app.workers.render_worker.download_to_file"):
        await RenderWorker(worker_id="test", temporal_client=AsyncMock())._execute(task)

    assert captured_resolution == (1080, 1920)


@pytest.mark.asyncio
async def test_render_worker_scene_without_audio_key():
    """Scene with no audio_key (tts_status=skipped) should produce audio=None in SceneInput."""
    from app.workers.render_worker import RenderWorker
    from app.engines.render.base import RenderResultWithBytes as _RenderResultWithBytes
    from app.engines.render.base import SceneInput

    project = make_project()
    code_version = make_code_version(project.id, scenes=[
        {
            "scene_index": 0,
            "narration": "Hello",
            "description": "intro",
            "code": "pass",
            # no audio_key — tts was skipped
            "duration_seconds": 0.0,
            "tts_status": "skipped",
        },
    ])
    task = make_task(project.id, code_version.id)

    render_result = _RenderResultWithBytes(
        success=True, output_path="/tmp/out.mp4", duration_seconds=5.0,
        error_message=None, render_log="OK", video_bytes=b"fake-video"
    )

    asset_mock = MagicMock()
    project_mock = MagicMock()
    mock_db = MagicMock()
    mock_db.get.side_effect = [project, code_version, asset_mock, project_mock]

    captured_inputs = []

    async def capture_render(request, work_dir):
        captured_inputs.extend(request.scenes)
        return render_result

    mock_render = AsyncMock()
    mock_render.render = AsyncMock(side_effect=capture_render)

    with patch("app.workers.render_worker.get_sync_session", return_value=mock_db), \
         patch("app.workers.render_worker.get_render_engine", return_value=mock_render), \
         patch("app.workers.render_worker.upload_bytes"), \
         patch("app.workers.render_worker.download_to_file") as mock_download:

        temporal_client = AsyncMock()
        worker = RenderWorker(worker_id="test", temporal_client=temporal_client)
        result = await worker._execute(task)

    # No audio downloaded for skipped scene
    assert mock_download.call_count == 0
    # SceneInput.audio should be None
    assert len(captured_inputs) == 1
    assert captured_inputs[0].audio is None
