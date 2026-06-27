import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4
from datetime import datetime, timezone


def make_asset(project_id, status="ready", video_file_key="video/proj/sv/asset.mp4"):
    a = MagicMock()
    a.id = uuid4()
    a.project_id = project_id
    a.status = status
    a.video_file_key = video_file_key
    return a


def make_project(pid=None):
    p = MagicMock()
    p.id = pid or uuid4()
    p.topic_id = uuid4()
    p.status = "video_review"
    p.render_engine = "manim"
    p.tts_voice = "male_calm"
    p.aspect_ratio = "landscape"
    p.retry_count = 0
    p.created_at = datetime.now(timezone.utc)
    p.updated_at = datetime.now(timezone.utc)
    return p


def test_video_url_returns_presigned_url(client, auth_headers, mock_db):
    project = make_project()
    asset = make_asset(project.id)

    mock_db.get.side_effect = [project, asset]

    with patch("app.api.projects.get_presigned_url", return_value="http://minio/signed") as mock_url:
        response = client.get(
            f"/api/projects/{project.id}/video-url",
            params={"asset_id": str(asset.id)},
            headers=auth_headers,
        )

    assert response.status_code == 200
    data = response.json()
    assert data["url"] == "http://minio/signed"
    assert data["expires_in"] == 3600
    mock_url.assert_called_once_with(asset.video_file_key, expires_seconds=3600)


def test_video_url_asset_not_found(client, auth_headers, mock_db):
    project = make_project()
    mock_db.get.side_effect = [project, None]

    response = client.get(
        f"/api/projects/{project.id}/video-url",
        params={"asset_id": str(uuid4())},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_video_url_asset_wrong_project(client, auth_headers, mock_db):
    project = make_project()
    other_project_id = uuid4()
    asset = make_asset(other_project_id)  # belongs to different project

    mock_db.get.side_effect = [project, asset]

    response = client.get(
        f"/api/projects/{project.id}/video-url",
        params={"asset_id": str(asset.id)},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_video_url_no_file_key(client, auth_headers, mock_db):
    project = make_project()
    asset = make_asset(project.id, video_file_key=None)
    mock_db.get.side_effect = [project, asset]

    response = client.get(
        f"/api/projects/{project.id}/video-url",
        params={"asset_id": str(asset.id)},
        headers=auth_headers,
    )
    assert response.status_code == 404
