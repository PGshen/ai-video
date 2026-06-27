import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4
from datetime import datetime, timezone
from app.schemas.narrative import NarrativeVersionSchema


def make_project(**kwargs):
    p = MagicMock()
    p.id = kwargs.get("id", uuid4())
    p.topic_id = uuid4()
    p.status = "narrative_review"
    p.current_narrative_version_id = kwargs.get("narrative_version_id", uuid4())
    p.temporal_workflow_id = f"video-production-{p.id}"
    return p


def make_narrative_version(project_id, **kwargs):
    from types import SimpleNamespace
    return SimpleNamespace(
        id=kwargs.get("id", uuid4()),
        project_id=project_id,
        version_number=1,
        scenes=[
            {"scene_index": 0, "narration": "旁白", "description": "描述", "estimated_duration_seconds": 5.0}
        ],
        fact_checks=[],
        ai_model="deepseek",
        created_at=datetime.now(timezone.utc),
    )


def test_get_narrative_not_found_project(client, auth_headers, mock_db):
    mock_db.get.return_value = None
    response = client.get(f"/api/projects/{uuid4()}/narrative", headers=auth_headers)
    assert response.status_code == 404


def test_get_narrative_no_narrative_yet(client, auth_headers, mock_db):
    project = make_project()
    project.current_narrative_version_id = None
    mock_db.get.return_value = project
    response = client.get(f"/api/projects/{project.id}/narrative", headers=auth_headers)
    assert response.status_code == 404


def test_get_narrative_returns_version(client, auth_headers, mock_db):
    project = make_project()
    nv = make_narrative_version(project.id)
    mock_db.get.side_effect = lambda model, pk: (
        project if "VideoProject" in str(model) else nv
    )
    response = client.get(f"/api/projects/{project.id}/narrative", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["versionNumber"] == 1


def test_review_narrative_approved_sends_signal(client, auth_headers, mock_db, mock_temporal):
    project = make_project()
    nv = make_narrative_version(project.id)
    mock_db.get.side_effect = lambda model, pk: (
        project if "VideoProject" in str(model) else nv
    )
    mock_db.commit = AsyncMock()
    mock_handle = AsyncMock()
    mock_temporal.get_workflow_handle = MagicMock(return_value=mock_handle)

    with patch("app.api.reviews.flag_modified"):
        response = client.post(
            f"/api/projects/{project.id}/review",
            headers=auth_headers,
            json={
                "gate": "narrative",
                "verdict": "approved",
                "editedScenes": [
                    {"sceneIndex": 0, "narration": "修改旁白", "description": "修改描述"}
                ],
            },
        )
    assert response.status_code == 200
    mock_handle.signal.assert_awaited_once()
