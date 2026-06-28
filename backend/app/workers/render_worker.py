import logging
import os
import tempfile
import uuid
from app.db import get_sync_session
from app.engines.render.factory import get_render_engine
from app.engines.render.base import RenderRequest, SceneInput, SceneAudio
from app.models.project import VideoProject
from app.models.project_event import ProjectEvent
from app.models.script_version import ScriptVersion
from app.models.video_asset import VideoAsset
from app.storage import download_to_file, upload_bytes
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
            render_engine_name = project.render_engine
        finally:
            db.close()

        logger.info(
            "[RenderWorker] task=%s project=%s scenes=%d engine=%s",
            task.id,
            task.project_id,
            len(scenes_data),
            render_engine_name,
        )

        # Step 1: 创建 VideoAsset 记录
        asset_id = uuid.uuid4()
        asset_id_str = str(asset_id)
        db = get_sync_session()
        try:
            asset = VideoAsset(
                id=asset_id,
                project_id=uuid.UUID(project_id),
                script_version_id=uuid.UUID(script_version_id),
                status="rendering",
            )
            db.add(asset)
            db.commit()
        finally:
            db.close()

        # Step 2: 下载音频并渲染
        logger.info("[RenderWorker] Starting Manim render for asset %s", asset_id_str)
        with tempfile.TemporaryDirectory() as tmpdir:
            scene_inputs = []
            for i, s in enumerate(scenes_data):
                audio_key = s.get("audio_key")
                duration = s.get("duration_seconds") or 0.0
                audio_path = None
                if audio_key:
                    audio_path = os.path.join(tmpdir, f"scene_{i}_audio.mp3")
                    download_to_file(audio_key, audio_path)
                    logger.info("[RenderWorker] Downloaded audio scene %d ← %s", i, audio_key)

                scene_inputs.append(
                    SceneInput(
                        scene_index=i,
                        narration=s.get("narration", ""),
                        description=s.get("description", ""),
                        code=s.get("code", ""),
                        audio=SceneAudio(
                            scene_index=i,
                            audio_path=audio_path or "",
                            duration_seconds=duration,
                        ) if audio_path else None,
                    )
                )

            render_engine = get_render_engine(render_engine_name)
            render_request = RenderRequest(
                scenes=scene_inputs,
                output_format="mp4",
                resolution=(1920, 1080),
                fps=30,
            )
            render_result = await render_engine.render(render_request, work_dir=tmpdir)

            if not render_result.success:
                logger.error(
                    "[RenderWorker] Render failed asset=%s: %s",
                    asset_id_str,
                    render_result.error_message,
                )
                db = get_sync_session()
                try:
                    asset_orm = db.get(VideoAsset, asset_id)
                    if asset_orm:
                        asset_orm.status = "failed"
                        asset_orm.render_log = render_result.render_log
                        asset_orm.error_message = render_result.error_message
                    project_orm = db.get(VideoProject, task.project_id)
                    if project_orm:
                        project_orm.current_video_asset_id = asset_id
                        db.add(ProjectEvent(
                            project_id=uuid.UUID(project_id),
                            event_type="render_failed",
                            from_status="video_generating",
                            to_status=None,
                            actor="system",
                            payload={"error_message": (render_result.error_message or "")[:800]},
                        ))
                    db.commit()
                finally:
                    db.close()
                raise RuntimeError(f"Render failed: {render_result.error_message}")

            # Step 3: 上传视频
            video_key = f"video/{project_id}/{script_version_id}/{asset_id_str}.mp4"
            upload_bytes(video_key, render_result.video_bytes, "video/mp4")
            logger.info("[RenderWorker] Uploaded video → %s", video_key)

        # Step 4: 更新 VideoAsset 和 Project
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
