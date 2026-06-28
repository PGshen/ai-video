from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.models.script_version import ScriptVersion
from app.workflows.activities import update_project_status


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
