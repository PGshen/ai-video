import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4
from datetime import datetime, timezone
from app.schemas.project import ProjectResponse
from app.engines.ai.base import CodeRepairResult
from temporalio.client import WorkflowExecutionStatus


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
    assert topic.status == "in_production"
    mock_temporal.start_workflow.assert_called_once()


def test_create_project_missing_fields(client, auth_headers):
    response = client.post("/api/projects", headers=auth_headers, json={})
    assert response.status_code == 422


def test_get_project_not_found(client, auth_headers, mock_db):
    mock_db.get.return_value = None
    response = client.get(f"/api/projects/{uuid4()}", headers=auth_headers)
    assert response.status_code == 404


def test_delete_project_cleans_related_data_and_restores_topic(
    client, auth_headers, mock_db, mock_temporal,
):
    project = make_project(
        status="script_review",
        temporal_workflow_id="video-production-delete",
    )
    topic = make_topic(id=project.topic_id)
    topic.status = "in_production"
    mock_db.get = AsyncMock(
        side_effect=lambda model, pk: project if pk == project.id else topic
    )
    mock_db.execute.return_value.scalar_one_or_none.return_value = None
    handle = AsyncMock()
    handle.describe.return_value.status = WorkflowExecutionStatus.RUNNING
    mock_temporal.get_workflow_handle = MagicMock(return_value=handle)

    response = client.delete(f"/api/projects/{project.id}", headers=auth_headers)

    assert response.status_code == 204
    handle.terminate.assert_awaited_once_with(reason="Project deleted by user")
    assert mock_db.execute.await_count == 7
    mock_db.delete.assert_awaited_once_with(project)
    assert topic.status == "stocked"
    mock_db.commit.assert_awaited_once()


def test_delete_completed_project_does_not_terminate_workflow(
    client, auth_headers, mock_db, mock_temporal,
):
    project = make_project(
        status="published",
        temporal_workflow_id="video-production-complete",
    )
    topic = make_topic(id=project.topic_id)
    topic.status = "used"
    mock_db.get = AsyncMock(
        side_effect=lambda model, pk: project if pk == project.id else topic
    )
    mock_db.execute.return_value.scalar_one_or_none.return_value = None
    handle = AsyncMock()
    handle.describe.return_value.status = WorkflowExecutionStatus.COMPLETED
    mock_temporal.get_workflow_handle = MagicMock(return_value=handle)

    response = client.delete(f"/api/projects/{project.id}", headers=auth_headers)

    assert response.status_code == 204
    handle.terminate.assert_not_awaited()
    assert topic.status == "used"


def test_delete_project_not_found(client, auth_headers, mock_db):
    mock_db.get.return_value = None

    response = client.delete(f"/api/projects/{uuid4()}", headers=auth_headers)

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


def test_get_script_returns_script_version(client, auth_headers, mock_db):
    from datetime import datetime, timezone
    from types import SimpleNamespace

    project_id = uuid4()
    script_id = uuid4()

    project = MagicMock()
    project.id = project_id
    project.current_script_version_id = script_id

    # Use SimpleNamespace so missing camelCase attrs raise AttributeError,
    # allowing Pydantic v2 alias_generator fallback to snake_case field names.
    sv = SimpleNamespace(
        id=script_id,
        project_id=project_id,
        version_number=1,
        scenes=[{"scene_index": 0, "narration": "旁白", "description": "画面", "code": "", "estimated_duration_seconds": 5.0}],
        fact_checks=[{
            "claim_text": "事实陈述",
            "scene_index": 0,
            "source_url": None,
            "source_description": "测试来源",
            "confidence": "high",
            "is_hypothesis": False,
            "assumptions": None,
            "controversy": None,
            "reviewer_verdict": None,
            "reviewer_note": None,
        }],
        render_engine="manim",
        ai_model="test-model",
        rejection_context=None,
        created_at=datetime.now(timezone.utc),
    )

    mock_db.get = AsyncMock(side_effect=lambda model, pk: project if pk == project_id else sv)

    response = client.get(f"/api/projects/{project_id}/script", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["versionNumber"] == 1
    assert len(data["scenes"]) == 1
    assert data["scenes"][0]["sceneIndex"] == 0
    assert data["scenes"][0]["estimatedDurationSeconds"] == 5.0
    assert data["factChecks"][0]["claimText"] == "事实陈述"
    assert data["factChecks"][0]["sceneIndex"] == 0


def test_get_script_returns_404_if_no_script(client, auth_headers, mock_db):
    project = MagicMock()
    project.current_script_version_id = None
    mock_db.get = AsyncMock(return_value=project)

    response = client.get(f"/api/projects/{uuid4()}/script", headers=auth_headers)
    assert response.status_code == 404


def test_get_script_returns_404_if_project_missing(client, auth_headers, mock_db):
    mock_db.get = AsyncMock(return_value=None)
    response = client.get(f"/api/projects/{uuid4()}/script", headers=auth_headers)
    assert response.status_code == 404


def test_repair_script_code_sends_all_scenes_and_error_to_ai(
    client, auth_headers, mock_db,
):
    project = make_project(status="script_review", render_engine="manim")
    mock_db.get = AsyncMock(return_value=project)
    provider = MagicMock()
    provider.repair_code = AsyncMock(return_value=CodeRepairResult(repairs=[{
        "scene_index": 1,
        "code": "label = Text('18岁')",
        "explanation": "移除不支持的 label 参数",
    }]))
    scenes = [
        {
            "sceneIndex": 0,
            "narration": "第一幕",
            "description": "标题",
            "code": "title = Text('标题')",
            "estimatedDurationSeconds": 5,
        },
        {
            "sceneIndex": 1,
            "narration": "第二幕",
            "description": "数轴",
            "code": "NumberLine(label_direction=DOWN)",
            "estimatedDurationSeconds": 6,
        },
    ]

    with patch("app.api.projects.get_ai_provider", return_value=provider):
        response = client.post(
            f"/api/projects/{project.id}/script/repair",
            headers=auth_headers,
            json={
                "errorMessage": "unexpected keyword argument 'label'",
                "scenes": scenes,
            },
        )

    assert response.status_code == 200
    assert response.json()["repairs"][0]["sceneIndex"] == 1
    call = provider.repair_code.await_args.kwargs
    assert call["error_message"] == "unexpected keyword argument 'label'"
    assert call["render_engine"] == "manim"
    assert [scene["scene_index"] for scene in call["scenes"]] == [0, 1]
    assert call["scenes"][1]["code"] == "NumberLine(label_direction=DOWN)"


def test_repair_script_code_only_allowed_during_script_review(
    client, auth_headers, mock_db,
):
    project = make_project(status="video_generating")
    mock_db.get = AsyncMock(return_value=project)

    response = client.post(
        f"/api/projects/{project.id}/script/repair",
        headers=auth_headers,
        json={
            "errorMessage": "render failed",
            "scenes": [{
                "sceneIndex": 0,
                "narration": "旁白",
                "description": "画面",
                "code": "broken()",
                "estimatedDurationSeconds": 5,
            }],
        },
    )

    assert response.status_code == 409
