from app.workers.base import BaseWorker


class RenderWorker(BaseWorker):
    supported_task_types = ["render_video"]

    async def _execute(self, task) -> dict:
        raise NotImplementedError("Sprint 3: implement TTS + render pipeline")
