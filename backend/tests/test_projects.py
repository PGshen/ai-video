import pytest
from types import SimpleNamespace
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
    p.tts_voice = kwargs.get("tts_voice", "zizi")
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


def test_list_projects_filters_by_topic(client, auth_headers, mock_db):
    topic_id = uuid4()
    mock_db.execute.return_value.scalars.return_value.all.return_value = []

    response = client.get(
        f"/api/projects?topic_id={topic_id}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    statement = mock_db.execute.await_args.args[0]
    assert "video_projects.topic_id" in str(statement)
    assert topic_id in statement.compile().params.values()


def test_list_projects_combines_title_engine_and_aspect_ratio_filters(
    client, auth_headers, mock_db,
):
    mock_db.execute.return_value.scalars.return_value.all.return_value = []

    response = client.get(
        "/api/projects?topic_title=%E9%87%8F%E5%AD%90"
        "&render_engine=manim&aspect_ratio=portrait",
        headers=auth_headers,
    )

    assert response.status_code == 200
    statement = mock_db.execute.await_args.args[0]
    statement_sql = str(statement)
    params = statement.compile().params.values()
    assert "lower(topics.title) LIKE lower" in statement_sql
    assert "video_projects.render_engine" in statement_sql
    assert "video_projects.aspect_ratio" in statement_sql
    assert "manim" in params
    assert "portrait" in params


def test_list_projects_applies_pagination(client, auth_headers, mock_db):
    mock_db.execute.return_value.scalars.return_value.all.return_value = []

    response = client.get(
        "/api/projects?page=2&page_size=25",
        headers=auth_headers,
    )

    assert response.status_code == 200
    statement = mock_db.execute.await_args.args[0]
    params = statement.compile().params
    assert list(params.values()).count(25) == 2


def test_create_project_starts_workflow(client, auth_headers, mock_db, mock_temporal):
    topic = make_topic(title="My Topic")
    topic.status = "stocked"
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
            tts_voice="zizi",
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
                "tts_voice": "zizi",
                "aspect_ratio": "landscape",
            },
        )
    assert response.status_code == 201
    assert topic.status == "stocked"
    mock_temporal.start_workflow.assert_called_once()


def test_create_project_stores_narrative_context(client, auth_headers, mock_db, mock_temporal):
    topic = make_topic(title="测试")
    mock_db.get.return_value = topic
    mock_temporal.start_workflow = AsyncMock()

    captured_projects = []

    original_add = mock_db.add
    def capture_add(obj):
        captured_projects.append(obj)
        return original_add(obj)
    mock_db.add = capture_add

    with patch("app.api.projects._project_to_response") as mock_resp:
        now = datetime.now(timezone.utc)
        mock_resp.return_value = ProjectResponse(
            id=uuid4(),
            topic_id=topic.id,
            topic_title=topic.title,
            status="draft",
            render_engine="manim",
            tts_voice="zizi",
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
                "tts_voice": "zizi",
                "aspect_ratio": "landscape",
                "narrative_context": [{"text": "关键参考片段一"}, {"text": "片段二"}],
            },
        )
    assert response.status_code == 201
    assert len(captured_projects) == 1
    assert captured_projects[0].narrative_context == [{"text": "关键参考片段一"}, {"text": "片段二"}]


def test_create_project_missing_fields(client, auth_headers):
    response = client.post("/api/projects", headers=auth_headers, json={})
    assert response.status_code == 422


def test_get_project_not_found(client, auth_headers, mock_db):
    mock_db.get.return_value = None
    response = client.get(f"/api/projects/{uuid4()}", headers=auth_headers)
    assert response.status_code == 404


def test_delete_project_cleans_related_data_without_changing_topic(
    client, auth_headers, mock_db, mock_temporal,
):
    project = make_project(
        status="script_review",
        temporal_workflow_id="video-production-delete",
    )
    mock_db.get = AsyncMock(return_value=project)
    handle = AsyncMock()
    handle.describe.return_value.status = WorkflowExecutionStatus.RUNNING
    mock_temporal.get_workflow_handle = MagicMock(return_value=handle)

    response = client.delete(f"/api/projects/{project.id}", headers=auth_headers)

    assert response.status_code == 204
    handle.terminate.assert_awaited_once_with(reason="Project deleted by user")
    assert mock_db.execute.await_count == 6
    mock_db.delete.assert_awaited_once_with(project)
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
        json={
            "gate": "video",
            "verdict": "rejected",
            "rejectionType": "sync_issue",
            "rejectionDetail": "口播与画面不同步",
            "targetStage": "script",
        },
    )
    assert response.status_code == 200
    call_args = mock_handle.signal.call_args
    assert call_args[0][0] == "video_review"
    assert call_args[0][1]["target_stage"] == "script"


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
        scenes=[{
            "scene_index": 0,
            "narration": "旁白",
            "description": "画面",
            "code": "pass",
            "beats": [{
                "beat_index": 0,
                "cue_text": "旁白",
                "visual_action": "文字出现",
                "alignment_status": "interpolated",
                "speech_start_seconds": 0.0,
                "speech_end_seconds": 5.0,
                "animation_start_seconds": 0.0,
                "animation_end_seconds": 5.0,
            }],
            "estimated_duration_seconds": 5.0,
            "duration_seconds": 5.0,
        }],
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
        prompt_snapshot={"base_prompt_version": "test"},
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


def test_get_script_serializes_nested_beats_as_camel_case(
    client, auth_headers, mock_db,
):
    project = make_project()
    project.current_script_version_id = uuid4()
    script_version = SimpleNamespace(
        id=project.current_script_version_id,
        project_id=project.id,
        version_number=1,
        scenes=[{
            "scene_index": 0,
            "narration": "第一幕",
            "description": "标题",
            "code": "title = Text('标题')",
            "beats": [{
                "beat_index": 0,
                "cue_text": "第一幕",
                "visual_action": "标题出现",
                "alignment_status": "aligned",
            }],
            "estimated_duration_seconds": 5,
            "duration_seconds": 5,
        }],
        fact_checks=[],
        render_engine="manim",
        ai_model="test-model",
        prompt_snapshot=None,
        created_at=datetime.now(timezone.utc),
    )
    mock_db.get = AsyncMock(
        side_effect=lambda model, pk: (
            project if model.__name__ == "VideoProject" else script_version
        )
    )

    response = client.get(
        f"/api/projects/{project.id}/script",
        headers=auth_headers,
    )

    assert response.status_code == 200
    beat = response.json()["scenes"][0]["beats"][0]
    assert beat["beatIndex"] == 0
    assert beat["cueText"] == "第一幕"
    assert beat["visualAction"] == "标题出现"
    assert beat["alignmentStatus"] == "aligned"
    assert "beat_index" not in beat


def test_repair_script_code_sends_all_scenes_and_error_to_ai(
    client, auth_headers, mock_db,
):
    project = make_project(status="script_review", render_engine="manim")
    project.current_script_version_id = uuid4()
    script_version = MagicMock()
    script_version.prompt_snapshot = {"components": {}}
    mock_db.get = AsyncMock(
        side_effect=lambda model, pk: (
            project if model.__name__ == "VideoProject" else script_version
        )
    )
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
            "beats": [{
                "beatIndex": 0,
                "cueText": "第一幕",
                "visualAction": "标题出现",
            }],
            "estimatedDurationSeconds": 5,
            "durationSeconds": 5,
        },
        {
            "sceneIndex": 1,
            "narration": "第二幕",
            "description": "数轴",
            "code": "NumberLine(label_direction=DOWN)",
            "beats": [{
                "beatIndex": 0,
                "cueText": "第二幕",
                "visualAction": "数轴出现",
            }],
            "estimatedDurationSeconds": 6,
            "durationSeconds": 6,
        },
    ]

    with patch("app.api.projects.get_ai_provider", return_value=provider), \
         patch("app.api.projects.style_components_from_snapshot", return_value={}):
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
                "beats": [{
                    "beatIndex": 0,
                    "cueText": "旁白",
                    "visualAction": "画面出现",
                }],
                "estimatedDurationSeconds": 5,
                "durationSeconds": 5,
            }],
        },
    )

    assert response.status_code == 409
