import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4
from datetime import datetime, timezone
from app.schemas.project import ProjectResponse


def make_project(**kwargs):
    p = MagicMock()
    p.id = kwargs.get("id", uuid4())
    p.topic_id = kwargs.get("topic_id", uuid4())
    p.status = kwargs.get("status", "draft")
    p.render_engine = kwargs.get("render_engine", "manim")
    p.tts_voice = kwargs.get("tts_voice", "alloy")
    p.aspect_ratio = kwargs.get("aspect_ratio", "landscape")
    p.temporal_workflow_id = kwargs.get("temporal_workflow_id", None)
    p.retry_count = 0
    p.created_at = datetime.now(timezone.utc)
    p.updated_at = datetime.now(timezone.utc)
    return p


def make_topic(**kwargs):
    t = MagicMock()
    t.id = kwargs.get("id", uuid4())
    t.title = kwargs.get("title", "Test Topic")
    return t


def test_list_projects_empty(client, auth_headers, mock_db):
    mock_db.execute.return_value.scalars.return_value.all.return_value = []
    response = client.get("/api/projects", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


def test_create_project_starts_workflow(client, auth_headers, mock_db, mock_temporal):
    topic = make_topic(title="My Topic")
    mock_db.get.return_value = topic  # only called once now: for the topic
    mock_temporal.start_workflow = AsyncMock()

    with patch("app.api.projects._project_to_response") as mock_resp:
        now = datetime.now(timezone.utc)
        mock_resp.return_value = ProjectResponse(
            id=uuid4(),
            topic_id=topic.id,
            topic_title=topic.title,
            status="draft",
            render_engine="manim",
            tts_voice="alloy",
            aspect_ratio="landscape",
            retry_count=0,
            created_at=now,
            updated_at=now,
        )
        response = client.post(
            "/api/projects",
            headers=auth_headers,
            json={
                "topic_id": str(topic.id),
                "render_engine": "manim",
                "tts_voice": "alloy",
                "aspect_ratio": "landscape",
            },
        )
    assert response.status_code == 201
    mock_temporal.start_workflow.assert_called_once()


def test_create_project_missing_fields(client, auth_headers):
    response = client.post("/api/projects", headers=auth_headers, json={})
    assert response.status_code == 422


def test_get_project_not_found(client, auth_headers, mock_db):
    mock_db.get.return_value = None
    response = client.get(f"/api/projects/{uuid4()}", headers=auth_headers)
    assert response.status_code == 404


def test_submit_script_review_sends_signal(client, auth_headers, mock_db, mock_temporal):
    project = make_project(temporal_workflow_id="video-production-abc")
    mock_db.get.return_value = project
    mock_handle = AsyncMock()
    mock_temporal.get_workflow_handle = MagicMock(return_value=mock_handle)

    response = client.post(
        f"/api/projects/{project.id}/review",
        headers=auth_headers,
        json={"gate": "script", "verdict": "approved"},
    )
    assert response.status_code == 200
    mock_temporal.get_workflow_handle.assert_called_once_with(project.temporal_workflow_id)
    mock_handle.signal.assert_called_once()
    call_args = mock_handle.signal.call_args
    assert call_args[0][0] == "script_review"


def test_submit_video_review_sends_signal(client, auth_headers, mock_db, mock_temporal):
    project = make_project(temporal_workflow_id="video-production-abc")
    mock_db.get.return_value = project
    mock_handle = AsyncMock()
    mock_temporal.get_workflow_handle = MagicMock(return_value=mock_handle)

    response = client.post(
        f"/api/projects/{project.id}/review",
        headers=auth_headers,
        json={"gate": "video", "verdict": "rejected", "rejectionType": "sync_issue"},
    )
    assert response.status_code == 200
    call_args = mock_handle.signal.call_args
    assert call_args[0][0] == "video_review"


def test_list_project_events(client, auth_headers, mock_db):
    mock_db.execute.return_value.scalars.return_value.all.return_value = []
    response = client.get(f"/api/projects/{uuid4()}/events", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_projects_require_api_key(client):
    response = client.get("/api/projects")
    assert response.status_code == 401
