import asyncio
from datetime import datetime, timezone
import logging
from typing import Any
from fastapi import logger
from temporalio.client import Client
from sqlalchemy import text
from app.db import get_sync_session

logger = logging.getLogger(__name__)

class BaseWorker:
    supported_task_types: list[str] = []

    def __init__(
        self,
        worker_id: str,
        temporal_client: Client,
        poll_interval: float = 2.0,
    ):
        self.worker_id = worker_id
        self.temporal_client = temporal_client
        self.poll_interval = poll_interval

    async def run(self):
        while True:
            task = self._claim_next_task()
            if task:
                await self._process_task(task)
            else:
                await asyncio.sleep(self.poll_interval)

    def _claim_next_task(self) -> Any | None:
        db = get_sync_session()
        try:
            if not self.supported_task_types:
                return None

            type_placeholders = ", ".join(
                f":type_{i}" for i in range(len(self.supported_task_types))
            )
            params = {"worker_id": self.worker_id}
            for i, t in enumerate(self.supported_task_types):
                params[f"type_{i}"] = t

            result = db.execute(
                text(f"""
                    UPDATE worker_tasks
                    SET status = 'processing',
                        worker_id = :worker_id,
                        started_at = NOW()
                    WHERE id = (
                        SELECT id FROM worker_tasks
                        WHERE status = 'pending'
                          AND task_type IN ({type_placeholders})
                        ORDER BY created_at
                        FOR UPDATE SKIP LOCKED
                        LIMIT 1
                    )
                    RETURNING *
                """),
                params,
            ).fetchone()
            db.commit()
            return result
        finally:
            db.close()

    async def _process_task(self, task: Any):
        db = get_sync_session()
        try:
            from app.models.worker_task import WorkerTask
            # Load the actual ORM instance from DB (task may be an immutable Row)
            task_id = task.id
            orm_task = db.get(WorkerTask, task_id)
            if orm_task is None:
                return  # task disappeared, skip

            output = await self._execute(orm_task)
            orm_task.status = "completed"
            orm_task.output_payload = output
            orm_task.completed_at = datetime.now(timezone.utc)
            db.commit()

            await self._send_signal(orm_task, {
                "task_id": str(orm_task.id),
                "success": True,
                **output,
            })

        except Exception as e:
            logger.exception("[BaseWorker] task=%s error: %s", task.id, e)
            db.rollback()
            from app.models.worker_task import WorkerTask
            task_id = task.id
            try:
                orm_task = db.get(WorkerTask, task_id)
            except Exception:
                orm_task = None

            if orm_task is None:
                return

            if orm_task.retry_count < orm_task.max_retries:
                orm_task.status = "pending"
                orm_task.retry_count += 1
                orm_task.worker_id = None
                orm_task.started_at = None
                orm_task.completed_at = None
                db.commit()
                return

            orm_task.status = "failed"
            orm_task.output_payload = {"error_message": str(e)}
            orm_task.completed_at = datetime.now(timezone.utc)
            db.commit()

            await self._send_signal(orm_task, {
                "task_id": str(orm_task.id),
                "success": False,
                "error": str(e),
            })
        finally:
            db.close()

    async def _send_signal(self, task: Any, payload: dict):
        handle = self.temporal_client.get_workflow_handle(task.temporal_workflow_id)
        await handle.signal(task.signal_name, payload)

    async def _execute(self, task: Any) -> dict:
        raise NotImplementedError
