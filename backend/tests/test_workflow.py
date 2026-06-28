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


def test_workflow_does_not_have_script_generated_signal():
    wf = VideoProductionWorkflow()
    assert not hasattr(wf, "script_generated")


@pytest.mark.asyncio
async def test_render_failure_is_recorded_before_returning_to_script_review():
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
            "script_review",
            payload={
                "trigger": "video_failed",
                "error_message": "Manim syntax error",
                "task_id": "task-7",
            },
        ),
        call("project-1", "video_generating"),
        call("project-1", "video_review"),
    ]
