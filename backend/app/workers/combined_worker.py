"""
开发环境用合并 Worker。
单进程同时运行 Temporal Worker（Workflow + Activity）和 BaseWorker（任务轮询）。
"""
import asyncio
import logging
from temporalio.client import Client
from temporalio.worker import Worker as TemporalWorker
from app.workers.script_worker import ScriptWorker
from app.workers.render_worker import RenderWorker
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

    script_worker = ScriptWorker(
        worker_id="script-worker-01",
        temporal_client=client,
        poll_interval=2.0,
    )

    render_worker = RenderWorker(
        worker_id="render-worker-01",
        temporal_client=client,
        poll_interval=2.0,
    )

    logger.info("Workers started.")
    await asyncio.gather(
        temporal_worker.run(),
        script_worker.run(),
        render_worker.run(),
    )


if __name__ == "__main__":
    asyncio.run(main())
