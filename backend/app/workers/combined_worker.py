"""
开发环境用合并 Worker。
单进程同时处理 generate_script 和 render_video 任务。
"""
import asyncio
import logging
from temporalio.client import Client
from app.workers.base import BaseWorker
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CombinedWorker(BaseWorker):
    """开发用：合并所有任务类型"""
    supported_task_types = ["generate_script", "render_video"]

    async def _execute(self, task) -> dict:
        raise NotImplementedError(f"Task type {task.task_type} not yet implemented")


async def main():
    logger.info("Connecting to Temporal at %s", settings.TEMPORAL_ADDRESS)
    client = await Client.connect(settings.TEMPORAL_ADDRESS)

    worker = CombinedWorker(
        worker_id="combined-worker-01",
        temporal_client=client,
        poll_interval=2.0,
    )
    logger.info("CombinedWorker started. Polling for tasks...")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
