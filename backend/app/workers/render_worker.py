import asyncio
import logging
import tempfile
import os
import uuid
from app.db import get_sync_session
from app.engines.tts.factory import get_tts_engine
from app.engines.tts.base import TTSRequest
from app.engines.render.factory import get_render_engine
from app.engines.render.base import RenderRequest, SceneInput, SceneAudio
from app.models.project import VideoProject
from app.models.script_version import ScriptVersion
from app.models.video_asset import VideoAsset
from app.storage import upload_bytes, download_to_file
from app.workers.base import BaseWorker

logger = logging.getLogger(__name__)


class RenderWorker(BaseWorker):
    supported_task_types = ["render_video"]

    async def _execute(self, task) -> dict:
        db = get_sync_session()
        try:
            project = db.get(VideoProject, task.project_id)
            if project is None:
                raise ValueError(f"Project {task.project_id} not found")

            sv = db.get(ScriptVersion, project.current_script_version_id)
            if sv is None:
                raise ValueError("No script version found for project")

            scenes_data = list(sv.scenes or [])
            project_id = str(project.id)
            script_version_id = str(sv.id)
            tts_voice = project.tts_voice
            render_engine_name = project.render_engine
        finally:
            db.close()

        # Step 1: 并发 TTS 合成
        logger.info("[RenderWorker] Starting TTS for %d scenes", len(scenes_data))
        tts_engine = get_tts_engine()
        tts_requests = [
            TTSRequest(text=s.get("narration", ""), voice=tts_voice)
            for s in scenes_data
        ]
        tts_results = await asyncio.gather(
            *[tts_engine.synthesize(req) for req in tts_requests],
            return_exceptions=True,
        )

        # 检查 TTS 结果
        for i, result in enumerate(tts_results):
            if isinstance(result, Exception):
                raise RuntimeError(f"TTS failed for scene {i}: {result}")
            if not result.success:
                raise RuntimeError(f"TTS failed for scene {i}: {result.error_message}")

        # Step 2: 上传音频到 MinIO
        audio_keys = []
        for i, tts_result in enumerate(tts_results):
            key = f"audio/{project_id}/{script_version_id}/scene_{i}.mp3"
            upload_bytes(key, tts_result.audio_bytes, "audio/mpeg")
            audio_keys.append(key)
            logger.info("[RenderWorker] Uploaded audio scene %d → %s", i, key)

        # Step 3: 创建 VideoAsset 记录
        asset_id = uuid.uuid4()
        asset_id_str = str(asset_id)
        asset = VideoAsset(
            id=asset_id,
            project_id=uuid.UUID(project_id),
            script_version_id=uuid.UUID(script_version_id),
            status="rendering",
        )
        db = get_sync_session()
        try:
            db.add(asset)
            db.commit()
        finally:
            db.close()

        # Step 4: 下载音频到临时目录并渲染
        logger.info("[RenderWorker] Starting Manim render for asset %s", asset_id_str)
        with tempfile.TemporaryDirectory() as tmpdir:
            # 下载各 scene 音频到临时目录
            for i, audio_key in enumerate(audio_keys):
                local_audio = os.path.join(tmpdir, f"scene_{i}_audio.mp3")
                download_to_file(audio_key, local_audio)

            scene_inputs = [
                SceneInput(
                    scene_index=i,
                    narration=s.get("narration", ""),
                    description=s.get("description", ""),
                    code=s.get("code", ""),
                    audio=SceneAudio(
                        scene_index=i,
                        audio_path=os.path.join(tmpdir, f"scene_{i}_audio.mp3"),
                        duration_seconds=0.0,
                    ),
                )
                for i, s in enumerate(scenes_data)
            ]

            render_engine = get_render_engine(render_engine_name)
            render_request = RenderRequest(
                scenes=scene_inputs,
                output_format="mp4",
                resolution=(1920, 1080),
                fps=30,
            )
            render_result = await render_engine.render(render_request)

            if not render_result.success:
                db = get_sync_session()
                try:
                    asset_orm = db.get(VideoAsset, asset_id)
                    if asset_orm:
                        asset_orm.status = "failed"
                        asset_orm.render_log = render_result.render_log
                    db.commit()
                finally:
                    db.close()
                raise RuntimeError(
                    f"Render failed: {render_result.error_message}"
                )

            # Step 5: 上传视频到 MinIO
            video_key = f"video/{project_id}/{script_version_id}/{asset_id_str}.mp4"
            upload_bytes(video_key, render_result.video_bytes, "video/mp4")
            logger.info("[RenderWorker] Uploaded video → %s", video_key)

        # Step 6: 更新 VideoAsset 和 Project
        db = get_sync_session()
        try:
            asset_orm = db.get(VideoAsset, asset_id)
            if asset_orm:
                asset_orm.status = "ready"
                asset_orm.video_file_key = video_key
                asset_orm.render_log = render_result.render_log
                asset_orm.duration_seconds = render_result.duration_seconds

            project_orm = db.get(VideoProject, task.project_id)
            if project_orm:
                project_orm.current_video_asset_id = asset_id

            db.commit()
        finally:
            db.close()

        logger.info("[RenderWorker] Done. asset_id=%s", asset_id_str)
        return {"asset_id": asset_id_str, "video_file_key": video_key}
