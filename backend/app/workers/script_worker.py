from app.workers.base import BaseWorker


class ScriptWorker(BaseWorker):
    supported_task_types = ["generate_script"]

    async def _execute(self, task) -> dict:
        raise NotImplementedError("Sprint 2: implement script generation")
