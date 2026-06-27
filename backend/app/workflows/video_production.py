from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from app.workflows.activities import (
        update_project_status,
        submit_narrative_task,
        submit_video_generation_task,
        check_and_increment_retry,
    )

_ACTIVITY_OPTS = dict(
    start_to_close_timeout=timedelta(seconds=30),
    retry_policy=RetryPolicy(maximum_attempts=3),
)
_STATUS_OPTS = dict(
    start_to_close_timeout=timedelta(seconds=10),
    retry_policy=RetryPolicy(maximum_attempts=3),
)


@workflow.defn
class VideoProductionWorkflow:

    def __init__(self):
        self._signals: dict[str, list] = {}

    @workflow.signal
    async def script_generated(self, payload: dict) -> None:
        self._signals.setdefault("script_generated", []).append(payload)

    @workflow.signal
    async def script_review(self, payload: dict) -> None:
        self._signals.setdefault("script_review", []).append(payload)

    @workflow.signal
    async def render_completed(self, payload: dict) -> None:
        self._signals.setdefault("render_completed", []).append(payload)

    @workflow.signal
    async def video_review(self, payload: dict) -> None:
        self._signals.setdefault("video_review", []).append(payload)

    @workflow.signal
    async def cancel(self, payload: dict) -> None:
        self._signals.setdefault("cancel", []).append(payload)

    @workflow.run
    async def run(self, project_id: str) -> None:
        # Phase 1: script generation loop
        while True:
            result = await self._generate_and_review_script(project_id)
            if result == "approved":
                break
            elif result == "abandoned":
                await self._update_status(project_id, "abandoned")
                return

        # Phase 2: video generation loop
        while True:
            result = await self._generate_and_review_video(project_id)
            if result == "approved":
                break
            elif result == "abandoned":
                await self._update_status(project_id, "abandoned")
                return
            elif result == "back_to_script":
                while True:
                    r = await self._generate_and_review_script(project_id)
                    if r == "approved":
                        break
                    elif r == "abandoned":
                        await self._update_status(project_id, "abandoned")
                        return

        # Phase 3: publish
        await self._update_status(project_id, "published")

    async def _generate_and_review_script(self, project_id: str) -> str:
        await self._update_status(project_id, "script_generating")
        await workflow.execute_activity(
            submit_narrative_task, args=[project_id], **_ACTIVITY_OPTS
        )

        while True:
            result = await self._wait_signal("script_generated")
            if result["success"]:
                break
            can_retry = await workflow.execute_activity(
                check_and_increment_retry,
                args=[project_id, "script_generating", result.get("error", "")],
                **_STATUS_OPTS,
            )
            if not can_retry:
                await self._update_status(project_id, "script_failed")
                return "abandoned"
            await workflow.execute_activity(
                submit_narrative_task, args=[project_id], **_ACTIVITY_OPTS
            )

        await self._update_status(project_id, "script_review")
        review = await self._wait_signal("script_review")
        return review["verdict"]

    async def _generate_and_review_video(self, project_id: str) -> str:
        await self._update_status(project_id, "video_generating")
        await workflow.execute_activity(
            submit_video_generation_task, args=[project_id], **_ACTIVITY_OPTS
        )

        while True:
            result = await self._wait_signal("render_completed")
            if result["success"]:
                break
            can_retry = await workflow.execute_activity(
                check_and_increment_retry,
                args=[project_id, "video_generating", result.get("error", "")],
                **_STATUS_OPTS,
            )
            if not can_retry:
                await self._update_status(project_id, "video_failed")
                return "abandoned"
            await workflow.execute_activity(
                submit_video_generation_task, args=[project_id], **_ACTIVITY_OPTS
            )

        await self._update_status(project_id, "video_review")
        review = await self._wait_signal("video_review")
        verdict = review["verdict"]
        if verdict == "approved":
            return "approved"
        elif verdict == "abandoned":
            return "abandoned"
        return "back_to_script"

    async def _update_status(self, project_id: str, status: str) -> None:
        await workflow.execute_activity(
            update_project_status, args=[project_id, status], **_STATUS_OPTS
        )

    async def _wait_signal(self, name: str) -> dict:
        await workflow.wait_condition(
            lambda: bool(self._signals.get(name))
        )
        return self._signals[name].pop(0)
