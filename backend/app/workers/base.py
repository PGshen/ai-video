import asyncio
from datetime import datetime, timezone
from typing import Any
from temporalio.client import Client
from sqlalchemy import text
from app.db import get_sync_session


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
            output = await self._execute(task)
            task.status = "completed"
            task.output_payload = output
            task.completed_at = datetime.now(timezone.utc)
            db.merge(task)
            db.commit()

            await self._send_signal(task, {
                "task_id": str(task.id),
                "success": True,
                **output,
            })

        except Exception as e:
            if task.retry_count < task.max_retries:
                task.status = "pending"
                task.retry_count += 1
                task.worker_id = None
                task.started_at = None
                task.completed_at = None
                db.merge(task)
                db.commit()
                return

            task.status = "failed"
            task.output_payload = {"error_message": str(e)}
            task.completed_at = datetime.now(timezone.utc)
            db.merge(task)
            db.commit()

            await self._send_signal(task, {
                "task_id": str(task.id),
                "success": False,
                "error": str(e),
            })
        finally:
            db.close()

    async def _send_signal(self, task: Any, payload: dict):
        handle = await self.temporal_client.get_workflow_handle(task.temporal_workflow_id)
        await handle.signal(task.signal_name, payload)

    async def _execute(self, task: Any) -> dict:
        raise NotImplementedError
