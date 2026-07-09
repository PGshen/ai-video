from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from app.config import settings
from app.security import CurrentUser, create_access_token
from app.workflows.activities import StageNotResettableError


def make_project(temporal_workflow_id="wf-1", code_version_id=None):
    p = MagicMock()
    p.id = uuid4()
    p.status = "code_review"
    p.temporal_workflow_id = temporal_workflow_id
    p.current_code_version_id = code_version_id or uuid4()
    return p


def make_code_version():
    code_version = MagicMock()
    code_version.id = uuid4()
    code_version.version_number = 3
    code_version.fact_checks = [
        {"claim_text": "论断0", "scene_index": 0, "source_url": None,
         "source_description": "来源", "confidence": "medium", "is_hypothesis": False,
         "assumptions": None, "controversy": None,
         "reviewer_verdict": None, "reviewer_note": None},
        {"claim_text": "论断1", "scene_index": 0, "source_url": None,
         "source_description": "来源", "confidence": "low", "is_hypothesis": False,
         "assumptions": None, "controversy": None,
         "reviewer_verdict": None, "reviewer_note": None},
    ]
    return code_version


def _auth():
    token = create_access_token(
        CurrentUser(
            id="00000000-0000-0000-0000-000000000001",
            username="test-admin",
            display_name="Test Admin",
            role="admin",
            is_active=True,
        )
    )
    return {"Cookie": f"{settings.AUTH_COOKIE_NAME}={token}"}


def test_review_with_verdicts_creates_new_version(client, mock_db, mock_temporal):
    project = make_project()
    code_version = make_code_version()

    def db_get(model, pk):
        if str(pk) == str(project.id):
            return project
        return code_version

    mock_db.get = AsyncMock(side_effect=db_get)
    mock_handle = AsyncMock()
    mock_temporal.get_workflow_handle = MagicMock(return_value=mock_handle)

    response = client.post(
        f"/api/projects/{project.id}/review",
        headers=_auth(),
        json={
            "gate": "code",
            "verdict": "approved",
            "factCheckVerdicts": [
                {"index": 0, "verdict": "approved", "note": ""},
                {"index": 1, "verdict": "rejected", "note": "来源不可靠"},
            ],
        },
    )
    assert response.status_code == 200

    # Original record should NOT be mutated; a new CodeVersion is passed to db.add
    assert mock_db.add.called
    new_sv_calls = [
        call.args[0]
        for call in mock_db.add.call_args_list
        if hasattr(call.args[0], "version_number")
    ]
    assert new_sv_calls, "expected a new CodeVersion to be added"
    new_code_version = new_sv_calls[0]
    assert new_code_version.version_number == code_version.version_number + 1
    assert new_code_version.fact_checks[0]["reviewer_verdict"] == "approved"
    assert new_code_version.fact_checks[1]["reviewer_verdict"] == "rejected"
    assert new_code_version.fact_checks[1]["reviewer_note"] == "来源不可靠"

    mock_handle.signal.assert_called_once()
    event_calls = [
        call.args[0]
        for call in mock_db.add.call_args_list
        if hasattr(call.args[0], "event_type")
    ]
    assert event_calls
    event = event_calls[0]
    assert event.event_type == "review_verdict"
    assert event.from_status == "code_review"
    assert event.payload["verdict"] == "approved"
    assert event.payload["content_version_number"] == code_version.version_number + 1


def test_review_without_verdicts_still_sends_signal(client, mock_db, mock_temporal):
    project = make_project()
    mock_db.get = AsyncMock(return_value=project)
    mock_handle = AsyncMock()
    mock_temporal.get_workflow_handle = MagicMock(return_value=mock_handle)

    response = client.post(
        f"/api/projects/{project.id}/review",
        headers=_auth(),
        json={"gate": "code", "verdict": "approved"},
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
        json={"gate": "code", "verdict": "abandoned"},
    )
    assert response.status_code == 200
    call_args = mock_handle.signal.call_args[0]
    assert call_args[1]["verdict"] == "abandoned"


def test_reset_project_returns_stage_and_cancelled_count(client):
    project_id = uuid4()

    async def fake_reset(pid):
        assert pid == str(project_id)
        return {"stage": "generate_code", "cancelled_task_ids": ["t1", "t2"]}

    with patch("app.api.reviews.reset_stuck_stage", new=fake_reset):
        response = client.post(
            f"/api/projects/{project_id}/reset",
            headers=_auth(),
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "reset"
    assert body["projectId"] == str(project_id)
    assert body["stage"] == "generate_code"
    assert body["cancelledTaskCount"] == 2


def test_reset_project_not_found_returns_404(client):
    project_id = uuid4()

    async def fake_reset(pid):
        raise LookupError(f"Project {pid} not found")

    with patch("app.api.reviews.reset_stuck_stage", new=fake_reset):
        response = client.post(
            f"/api/projects/{project_id}/reset",
            headers=_auth(),
        )

    assert response.status_code == 404


def test_reset_project_non_resettable_status_returns_400(client):
    project_id = uuid4()

    async def fake_reset(pid):
        raise StageNotResettableError("Project status 'code_review' is not a resettable stage")

    with patch("app.api.reviews.reset_stuck_stage", new=fake_reset):
        response = client.post(
            f"/api/projects/{project_id}/reset",
            headers=_auth(),
        )

    assert response.status_code == 400


def test_reset_project_runs_off_event_loop_and_returns_200(client):
    """reset_stuck_stage is dispatched via run_in_threadpool(asyncio.run, ...);
    verify the coroutine still executes correctly and results/exceptions
    propagate back through to the route's response."""
    project_id = uuid4()

    async def fake_reset(pid):
        assert pid == str(project_id)
        return {"stage": "render_video", "cancelled_task_ids": ["t1"]}

    with patch("app.api.reviews.reset_stuck_stage", new=fake_reset):
        response = client.post(
            f"/api/projects/{project_id}/reset",
            headers=_auth(),
        )

    assert response.status_code == 200
    body = response.json()
    assert body["stage"] == "render_video"
    assert body["cancelledTaskCount"] == 1
