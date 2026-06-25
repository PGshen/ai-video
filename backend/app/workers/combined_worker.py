"""
开发环境用合并 Worker。
单进程同时运行 Temporal Worker（Workflow + Activity）和 BaseWorker（任务轮询）。
"""
import asyncio
import logging
from temporalio.client import Client
from temporalio.worker import Worker as TemporalWorker
from app.workers.base import BaseWorker
from app.workflows.video_production import VideoProductionWorkflow
from app.workflows.activities import (
    update_project_status,
    submit_script_generation_task,
    submit_video_generation_task,
    check_and_increment_retry,
)
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TaskWorker(BaseWorker):
    """轮询 worker_tasks 表，Sprint 2/3 实现具体任务处理"""
    supported_task_types = ["generate_script", "render_video"]

    async def _execute(self, task) -> dict:
        raise NotImplementedError(f"Task type {task.task_type} not yet implemented")


async def main():
    logger.info("Connecting to Temporal at %s", settings.TEMPORAL_ADDRESS)
    client = await Client.connect(settings.TEMPORAL_ADDRESS)

    temporal_worker = TemporalWorker(
        client,
        task_queue=settings.TEMPORAL_TASK_QUEUE,
        workflows=[VideoProductionWorkflow],
        activities=[
            update_project_status,
            submit_script_generation_task,
            submit_video_generation_task,
            check_and_increment_retry,
        ],
    )

    task_worker = TaskWorker(
        worker_id="combined-worker-01",
        temporal_client=client,
        poll_interval=2.0,
    )

    logger.info("Workers started.")
    await asyncio.gather(
        temporal_worker.run(),
        task_worker.run(),
    )


if __name__ == "__main__":
    asyncio.run(main())
