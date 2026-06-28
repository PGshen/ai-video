from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from app.workflows.activities import (
        update_project_status,
        submit_narrative_task,
        submit_code_task,
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
    async def narrative_generated(self, payload: dict) -> None:
        self._signals.setdefault("narrative_generated", []).append(payload)

    @workflow.signal
    async def narrative_review(self, payload: dict) -> None:
        self._signals.setdefault("narrative_review", []).append(payload)

    @workflow.signal
    async def code_generated(self, payload: dict) -> None:
        self._signals.setdefault("code_generated", []).append(payload)

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
        need_narrative = True

        # Phase 1 outer loop: narrative + code + script review
        while True:
            if need_narrative:
                narrative_result = await self._generate_and_review_narrative(project_id)
                if narrative_result == "abandoned":
                    await self._update_status(project_id, "abandoned")
                    return
                if narrative_result != "approved":
                    need_narrative = True
                    continue

            code_result = await self._generate_code_and_review_script(project_id)
            if code_result == "approved":
                break
            elif code_result == "back_to_narrative":
                need_narrative = True
                continue
            elif code_result == "back_to_code":
                need_narrative = False
                continue
            elif code_result == "abandoned":
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
            elif result in ("back_to_script", "back_to_code", "back_to_narrative"):
                # 退回脚本阶段：back_to_script/back_to_narrative 重新生成叙事+代码，
                # back_to_code 只重新生成代码
                need_narrative = result != "back_to_code"
                while True:
                    if need_narrative:
                        narrative_result = await self._generate_and_review_narrative(project_id)
                        if narrative_result == "abandoned":
                            await self._update_status(project_id, "abandoned")
                            return
                        if narrative_result != "approved":
                            need_narrative = True
                            continue
                    code_result = await self._generate_code_and_review_script(project_id)
                    if code_result == "approved":
                        break
                    elif code_result == "back_to_narrative":
                        need_narrative = True
                        continue
                    elif code_result == "back_to_code":
                        need_narrative = False
                        continue
                    elif code_result == "abandoned":
                        await self._update_status(project_id, "abandoned")
                        return

        await self._update_status(project_id, "published")

    async def _generate_and_review_narrative(self, project_id: str) -> str:
        await self._update_status(project_id, "narrative_generating")
        await workflow.execute_activity(
            submit_narrative_task, args=[project_id], **_ACTIVITY_OPTS
        )

        while True:
            result = await self._wait_signal("narrative_generated")
            if result["success"]:
                break
            can_retry = await workflow.execute_activity(
                check_and_increment_retry,
                args=[project_id, "narrative_generating", result.get("error", "")],
                **_STATUS_OPTS,
            )
            if not can_retry:
                await self._update_status(project_id, "narrative_failed")
                return "abandoned"
            await workflow.execute_activity(
                submit_narrative_task, args=[project_id], **_ACTIVITY_OPTS
            )

        await self._update_status(project_id, "narrative_review")
        review = await self._wait_signal("narrative_review")
        verdict = review.get("verdict")
        if verdict == "approved":
            return "approved"
        elif verdict == "abandoned":
            return "abandoned"
        # rejected → retry narrative
        return "rejected_retry"

    async def _generate_code_and_review_script(self, project_id: str) -> str:
        await self._update_status(project_id, "code_generating")
        await workflow.execute_activity(
            submit_code_task, args=[project_id], **_ACTIVITY_OPTS
        )

        while True:
            result = await self._wait_signal("code_generated")
            if result["success"]:
                break
            can_retry = await workflow.execute_activity(
                check_and_increment_retry,
                args=[project_id, "code_generating", result.get("error", "")],
                **_STATUS_OPTS,
            )
            if not can_retry:
                await self._update_status(project_id, "code_failed")
                return "abandoned"
            await workflow.execute_activity(
                submit_code_task, args=[project_id], **_ACTIVITY_OPTS
            )

        await self._update_status(project_id, "script_review")
        review = await self._wait_signal("script_review")
        verdict = review.get("verdict")
        if verdict == "approved":
            return "approved"
        elif verdict == "abandoned":
            return "abandoned"
        # rejected: check target_stage
        target = review.get("target_stage", "narrative")
        if target == "code":
            return "back_to_code"
        return "back_to_narrative"

    async def _generate_and_review_video(self, project_id: str) -> str:
        await self._update_status(project_id, "video_generating")
        await workflow.execute_activity(
            submit_video_generation_task, args=[project_id], **_ACTIVITY_OPTS
        )

        while True:
            result = await self._wait_signal("render_completed")
            if result["success"]:
                break

            # 渲染失败：直接退回脚本审核，不重试
            await self._update_status(project_id, "script_review")
            review = await self._wait_signal("script_review")
            verdict = review.get("verdict")
            if verdict == "abandoned":
                return "abandoned"
            elif verdict == "rejected":
                target = review.get("target_stage", "narrative")
                if target == "code":
                    return "back_to_code"
                return "back_to_narrative"
            # approved：用户（可能已编辑代码）重新提交视频生成
            await self._update_status(project_id, "video_generating")
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
