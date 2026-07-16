"""
开发环境用合并 Worker。
单进程同时运行 Temporal Worker（Workflow + Activity）和 BaseWorker（任务轮询）。
"""
import asyncio
import logging

# 必须在其它模块 import 之前配置根 logger：manim（被 RenderWorker 间接 import）
# 会在根 logger 尚无 handler 时给它挂上 RichHandler，而 RichHandler 在 Temporal
# workflow sandbox 内触发 rich 的循环 import 并使 workflow activation 崩溃。
logging.basicConfig(level=logging.INFO)

from temporalio.client import Client
from temporalio.worker import Worker as TemporalWorker
from app.workers.narrative_worker import NarrativeWorker
from app.workers.code_worker import CodeWorker
from app.workers.render_worker import RenderWorker
from app.workflows.video_production import VideoProductionWorkflow
from app.workflows.activities import (
    update_project_status,
    submit_narrative_task,
    submit_code_task,
    submit_video_generation_task,
    check_and_increment_retry,
)
from app.config import settings

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
            submit_narrative_task,
            submit_code_task,
            submit_video_generation_task,
            check_and_increment_retry,
        ],
    )

    narrative_worker = NarrativeWorker(
        worker_id="narrative-worker-01",
        temporal_client=client,
        poll_interval=2.0,
    )

    code_worker = CodeWorker(
        worker_id="code-worker-01",
        temporal_client=client,
        poll_interval=2.0,
    )

    render_worker = RenderWorker(
        worker_id="render-worker-01",
        temporal_client=client,
        poll_interval=2.0,
    )

    logger.info("Workers started.")
    try:
        await asyncio.gather(
            temporal_worker.run(),
            narrative_worker.run(),
            code_worker.run(),
            render_worker.run(),
        )
    except asyncio.CancelledError:
        logger.info("Workers cancelled, shutting down.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user.")
