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
    async def code_review(self, payload: dict) -> None:
        self._signals.setdefault("code_review", []).append(payload)

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

        # Phase 1 outer loop: narrative + code + code review
        while True:
            if need_narrative:
                narrative_result = await self._generate_and_review_narrative(project_id)
                if narrative_result == "abandoned":
                    await self._update_status(project_id, "abandoned")
                    return
                if narrative_result != "approved":
                    need_narrative = True
                    continue

            code_result = await self._generate_and_review_code(project_id)
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
            elif result == "retry_video":
                continue
            elif result == "abandoned":
                await self._update_status(project_id, "abandoned")
                return
            elif result in ("back_to_code", "back_to_narrative"):
                # back_to_narrative 重新生成叙事和代码；back_to_code 只重新生成代码。
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
                    code_result = await self._generate_and_review_code(project_id)
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
                await self._update_status(
                    project_id, "narrative_failed",
                    payload={"error_message": result.get("error", "")},
                )
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

    async def _generate_and_review_code(self, project_id: str) -> str:
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
                await self._update_status(
                    project_id, "code_failed",
                    payload={"error_message": result.get("error", "")},
                )
                # Keep the workflow alive at code_failed. An operator can
                # manually retry from the UI, which requeues generate_code and
                # sends the next code_generated signal back here.
                continue
            await workflow.execute_activity(
                submit_code_task, args=[project_id], **_ACTIVITY_OPTS
            )

        await self._update_status(project_id, "code_review")
        review = await self._wait_signal("code_review")
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

            # 渲染失败：直接退回代码审核，不重试
            render_error = result.get("error", "")
            failure_payload = {
                "error_message": render_error,
                **({"task_id": result["task_id"]} if result.get("task_id") else {}),
            }
            # 项目最终会停在 code_review，但时间线需要保留独立的失败状态。
            await self._update_status(
                project_id, "video_failed", payload=failure_payload,
            )
            await self._update_status(
                project_id, "code_review",
                payload={"trigger": "video_failed", **failure_payload},
            )
            review = await self._wait_signal("code_review")
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

        target = review.get("target_stage", "code")
        rejection_payload = {
            "trigger": "video_review_rejected",
            "target_stage": target,
            **({"rejection_type": review["rejection_type"]}
               if review.get("rejection_type") else {}),
            **({"rejection_detail": review["rejection_detail"]}
               if review.get("rejection_detail") else {}),
            **({"scene_annotations": review["scene_annotations"]}
               if review.get("scene_annotations") else {}),
        }

        if target == "narrative":
            # Re-open the existing narrative instead of regenerating it before
            # the reviewer has had a chance to make or request changes.
            await self._update_status(
                project_id, "narrative_review", payload=rejection_payload,
            )
            narrative_review = await self._wait_signal("narrative_review")
            narrative_verdict = narrative_review.get("verdict")
            if narrative_verdict == "abandoned":
                return "abandoned"
            if narrative_verdict == "approved":
                return "back_to_code"
            return "back_to_narrative"

        await self._update_status(
            project_id, "code_review", payload=rejection_payload,
        )
        code_review = await self._wait_signal("code_review")
        code_verdict = code_review.get("verdict")
        if code_verdict == "abandoned":
            return "abandoned"
        if code_verdict == "approved":
            return "retry_video"
        if code_review.get("target_stage", "narrative") == "code":
            return "back_to_code"
        return "back_to_narrative"

    async def _update_status(self, project_id: str, status: str, payload: dict | None = None) -> None:
        await workflow.execute_activity(
            update_project_status, args=[project_id, status, payload], **_STATUS_OPTS
        )

    async def _wait_signal(self, name: str) -> dict:
        await workflow.wait_condition(
            lambda: bool(self._signals.get(name))
        )
        return self._signals[name].pop(0)
