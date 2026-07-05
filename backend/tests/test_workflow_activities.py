from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.script_version import ScriptVersion
from app.workflows.activities import update_project_status
from app.workflows.activities import reset_stuck_stage


@pytest.mark.asyncio
async def test_script_review_status_event_keeps_exact_version_reference():
    project_id = uuid4()
    version_id = uuid4()
    project = SimpleNamespace(
        id=project_id,
        status="video_failed",
        current_narrative_version_id=None,
        current_script_version_id=version_id,
    )
    version = SimpleNamespace(id=version_id, version_number=4)
    db = MagicMock()
    db.get.side_effect = lambda model, object_id: (
        version if model is ScriptVersion else project
    )

    with patch("app.workflows.activities.get_sync_session", return_value=db):
        await update_project_status(
            str(project_id),
            "script_review",
            {"trigger": "video_failed", "error_message": "render exploded"},
        )

    event = db.add.call_args.args[0]
    assert project.status == "script_review"
    assert event.from_status == "video_failed"
    assert event.payload == {
        "trigger": "video_failed",
        "error_message": "render exploded",
        "content_type": "script",
        "content_version_id": str(version_id),
        "content_version_number": 4,
    }


@pytest.mark.asyncio
async def test_reset_stuck_stage_cancels_old_tasks_and_resubmits():
    project_id = uuid4()
    project = SimpleNamespace(id=project_id, status="code_generating")
    stuck_task = SimpleNamespace(id=uuid4(), status="processing")
    db = MagicMock()
    db.get.return_value = project
    db.execute.return_value.scalars.return_value.all.return_value = [stuck_task]

    with patch("app.workflows.activities.get_sync_session", return_value=db), \
         patch("app.workflows.activities.submit_code_task", new_callable=AsyncMock) as mock_submit:
        result = await reset_stuck_stage(str(project_id))

    assert stuck_task.status == "cancelled"
    mock_submit.assert_awaited_once_with(str(project_id))
    event = db.add.call_args.args[0]
    assert event.event_type == "stuck_reset"
    assert event.payload["stage"] == "generate_code"
    assert event.payload["cancelled_task_ids"] == [str(stuck_task.id)]
    assert result == {"stage": "generate_code", "cancelled_task_ids": [str(stuck_task.id)]}


@pytest.mark.asyncio
async def test_reset_stuck_stage_narrative_generating_resubmits_narrative_task():
    project_id = uuid4()
    project = SimpleNamespace(id=project_id, status="narrative_generating")
    stuck_task = SimpleNamespace(id=uuid4(), status="processing")
    db = MagicMock()
    db.get.return_value = project
    db.execute.return_value.scalars.return_value.all.return_value = [stuck_task]

    with patch("app.workflows.activities.get_sync_session", return_value=db), \
         patch("app.workflows.activities.submit_narrative_task", new_callable=AsyncMock) as mock_submit:
        result = await reset_stuck_stage(str(project_id))

    assert stuck_task.status == "cancelled"
    mock_submit.assert_awaited_once_with(str(project_id))
    event = db.add.call_args.args[0]
    assert event.event_type == "stuck_reset"
    assert event.payload["stage"] == "generate_narrative"
    assert event.payload["cancelled_task_ids"] == [str(stuck_task.id)]
    assert result == {"stage": "generate_narrative", "cancelled_task_ids": [str(stuck_task.id)]}


@pytest.mark.asyncio
async def test_reset_stuck_stage_video_generating_resubmits_video_task():
    project_id = uuid4()
    project = SimpleNamespace(id=project_id, status="video_generating")
    stuck_task = SimpleNamespace(id=uuid4(), status="processing")
    db = MagicMock()
    db.get.return_value = project
    db.execute.return_value.scalars.return_value.all.return_value = [stuck_task]

    with patch("app.workflows.activities.get_sync_session", return_value=db), \
         patch("app.workflows.activities.submit_video_generation_task", new_callable=AsyncMock) as mock_submit:
        result = await reset_stuck_stage(str(project_id))

    assert stuck_task.status == "cancelled"
    mock_submit.assert_awaited_once_with(str(project_id))
    event = db.add.call_args.args[0]
    assert event.event_type == "stuck_reset"
    assert event.payload["stage"] == "render_video"
    assert event.payload["cancelled_task_ids"] == [str(stuck_task.id)]
    assert result == {"stage": "render_video", "cancelled_task_ids": [str(stuck_task.id)]}


@pytest.mark.asyncio
async def test_reset_stuck_stage_rejects_non_resettable_status():
    project_id = uuid4()
    project = SimpleNamespace(id=project_id, status="script_review")
    db = MagicMock()
    db.get.return_value = project

    with patch("app.workflows.activities.get_sync_session", return_value=db):
        with pytest.raises(ValueError):
            await reset_stuck_stage(str(project_id))


@pytest.mark.asyncio
async def test_reset_stuck_stage_missing_project_raises_lookup_error():
    db = MagicMock()
    db.get.return_value = None

    with patch("app.workflows.activities.get_sync_session", return_value=db):
        with pytest.raises(LookupError):
            await reset_stuck_stage(str(uuid4()))
