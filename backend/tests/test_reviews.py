from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from app.config import settings


def make_project(temporal_workflow_id="wf-1", script_version_id=None):
    p = MagicMock()
    p.id = uuid4()
    p.status = "script_review"
    p.temporal_workflow_id = temporal_workflow_id
    p.current_script_version_id = script_version_id or uuid4()
    return p


def make_script_version():
    sv = MagicMock()
    sv.id = uuid4()
    sv.version_number = 3
    sv.fact_checks = [
        {"claim_text": "论断0", "scene_index": 0, "source_url": None,
         "source_description": "来源", "confidence": "medium", "is_hypothesis": False,
         "assumptions": None, "controversy": None,
         "reviewer_verdict": None, "reviewer_note": None},
        {"claim_text": "论断1", "scene_index": 0, "source_url": None,
         "source_description": "来源", "confidence": "low", "is_hypothesis": False,
         "assumptions": None, "controversy": None,
         "reviewer_verdict": None, "reviewer_note": None},
    ]
    return sv


def _auth():
    return {"X-API-Key": settings.API_KEY}


def test_review_with_verdicts_updates_fact_checks(client, mock_db, mock_temporal):
    project = make_project()
    sv = make_script_version()

    def db_get(model, pk):
        if str(pk) == str(project.id):
            return project
        return sv

    mock_db.get = AsyncMock(side_effect=db_get)
    mock_handle = AsyncMock()
    mock_temporal.get_workflow_handle = MagicMock(return_value=mock_handle)

    response = client.post(
        f"/api/projects/{project.id}/review",
        headers=_auth(),
        json={
            "gate": "script",
            "verdict": "approved",
            "factCheckVerdicts": [
                {"index": 0, "verdict": "approved", "note": ""},
                {"index": 1, "verdict": "rejected", "note": "来源不可靠"},
            ],
        },
    )
    assert response.status_code == 200

    updated = sv.fact_checks
    assert updated[0]["reviewer_verdict"] == "approved"
    assert updated[1]["reviewer_verdict"] == "rejected"
    assert updated[1]["reviewer_note"] == "来源不可靠"

    mock_handle.signal.assert_called_once()
    event = mock_db.add.call_args.args[0]
    assert event.event_type == "review_verdict"
    assert event.from_status == "script_review"
    assert event.payload["verdict"] == "approved"
    assert event.payload["content_version_id"] == str(sv.id)
    assert event.payload["content_version_number"] == 3


def test_review_without_verdicts_still_sends_signal(client, mock_db, mock_temporal):
    project = make_project()
    mock_db.get = AsyncMock(return_value=project)
    mock_handle = AsyncMock()
    mock_temporal.get_workflow_handle = MagicMock(return_value=mock_handle)

    response = client.post(
        f"/api/projects/{project.id}/review",
        headers=_auth(),
        json={"gate": "script", "verdict": "approved"},
    )
    assert response.status_code == 200
    mock_handle.signal.assert_called_once()


def test_review_abandoned_sends_correct_signal(client, mock_db, mock_temporal):
    project = make_project()
    mock_db.get = AsyncMock(return_value=project)
    mock_handle = AsyncMock()
    mock_temporal.get_workflow_handle = MagicMock(return_value=mock_handle)

    response = client.post(
        f"/api/projects/{project.id}/review",
        headers=_auth(),
        json={"gate": "script", "verdict": "abandoned"},
    )
    assert response.status_code == 200
    call_args = mock_handle.signal.call_args[0]
    assert call_args[1]["verdict"] == "abandoned"
