import pytest
from unittest.mock import AsyncMock, call, patch
from app.workflows.video_production import VideoProductionWorkflow


def test_workflow_has_narrative_generated_signal():
    wf = VideoProductionWorkflow()
    assert hasattr(wf, "narrative_generated")


def test_workflow_has_narrative_review_signal():
    wf = VideoProductionWorkflow()
    assert hasattr(wf, "narrative_review")


def test_workflow_has_code_generated_signal():
    wf = VideoProductionWorkflow()
    assert hasattr(wf, "code_generated")


@pytest.mark.asyncio
async def test_render_failure_is_recorded_before_returning_to_code_review():
    wf = VideoProductionWorkflow()
    wf._update_status = AsyncMock()
    wf._wait_signal = AsyncMock(side_effect=[
        {"success": False, "error": "Manim syntax error", "task_id": "task-7"},
        {"verdict": "approved"},
        {"success": True},
        {"verdict": "approved"},
    ])

    with patch(
        "app.workflows.video_production.workflow.execute_activity",
        new=AsyncMock(),
    ):
        result = await wf._generate_and_review_video("project-1")

    assert result == "approved"
    assert wf._update_status.call_args_list == [
        call("project-1", "video_generating"),
        call(
            "project-1",
            "video_failed",
            payload={"error_message": "Manim syntax error", "task_id": "task-7"},
        ),
        call(
            "project-1",
            "code_review",
            payload={
                "trigger": "video_failed",
                "error_message": "Manim syntax error",
                "task_id": "task-7",
            },
        ),
        call("project-1", "video_generating"),
        call("project-1", "video_review"),
    ]


@pytest.mark.asyncio
async def test_video_rejection_can_return_to_code_review():
    wf = VideoProductionWorkflow()
    wf._update_status = AsyncMock()
    wf._wait_signal = AsyncMock(side_effect=[
        {"success": True},
        {
            "verdict": "rejected",
            "target_stage": "code",
            "rejection_detail": "画面节奏需要调整",
        },
        {"verdict": "approved"},
    ])

    with patch(
        "app.workflows.video_production.workflow.execute_activity",
        new=AsyncMock(),
    ):
        result = await wf._generate_and_review_video("project-1")

    assert result == "retry_video"
    assert wf._update_status.call_args_list == [
        call("project-1", "video_generating"),
        call("project-1", "video_review"),
        call(
            "project-1",
            "code_review",
            payload={
                "trigger": "video_review_rejected",
                "target_stage": "code",
                "rejection_detail": "画面节奏需要调整",
            },
        ),
    ]


@pytest.mark.asyncio
async def test_video_rejection_can_return_to_narrative_review():
    wf = VideoProductionWorkflow()
    wf._update_status = AsyncMock()
    wf._wait_signal = AsyncMock(side_effect=[
        {"success": True},
        {
            "verdict": "rejected",
            "target_stage": "narrative",
            "rejection_detail": "叙事结构需要调整",
        },
        {"verdict": "approved"},
    ])

    with patch(
        "app.workflows.video_production.workflow.execute_activity",
        new=AsyncMock(),
    ):
        result = await wf._generate_and_review_video("project-1")

    assert result == "back_to_code"
    assert wf._update_status.call_args_list[-1] == call(
        "project-1",
        "narrative_review",
        payload={
            "trigger": "video_review_rejected",
            "target_stage": "narrative",
            "rejection_detail": "叙事结构需要调整",
        },
    )
