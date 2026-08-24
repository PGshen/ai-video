import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.models.narrative_version import NarrativeVersion


def make_project(topic_id=None, render_engine="manim", temporal_workflow_id="wf-1"):
    p = MagicMock()
    p.id = uuid4()
    p.topic_id = topic_id or uuid4()
    p.render_engine = render_engine
    p.temporal_workflow_id = temporal_workflow_id
    return p


def make_topic(title="选题标题", description="选题描述"):
    t = MagicMock()
    t.title = title
    t.description = description
    return t


@pytest.mark.asyncio
async def test_submit_narrative_task_writes_execution_mode_into_payload():
    from app.workflows import activities

    project_id = uuid4()
    project = SimpleNamespace(
        id=project_id,
        topic_id=uuid4(),
        render_engine="manim",
        aspect_ratio="16:9",
        current_narrative_version_id=None,
        narrative_context=[],
    )
    topic = make_topic()

    from app.models.project import VideoProject
    from app.models.topic import Topic

    db = MagicMock()

    def fake_get(model, object_id):
        if model is VideoProject:
            return project
        if model is Topic:
            return topic
        return None

    db.get.side_effect = fake_get
    db.execute.return_value.scalars.return_value.first.return_value = None

    with patch("app.workflows.activities.get_sync_session", return_value=db), \
         patch.object(
             activities,
             "build_prompt_snapshot",
             return_value=({"narrative_style": "x"}, {"base_prompt_version": "v1"}),
         ), \
         patch.object(
             activities, "resolve_execution_mode", return_value="agent"
         ) as mock_resolve:
        await activities.submit_narrative_task(str(project_id))

    task = db.add.call_args.args[0]
    assert task.input_payload["execution_mode"] == "agent"
    mock_resolve.assert_called_once_with(db, project, "narrative_generation")


@pytest.mark.asyncio
async def test_submit_code_task_writes_execution_mode_into_payload():
    from app.workflows import activities
    from app.models.project import VideoProject

    project_id = uuid4()
    narrative_version_id = uuid4()
    project = SimpleNamespace(
        id=project_id,
        render_engine="manim",
        aspect_ratio="16:9",
        current_narrative_version_id=narrative_version_id,
        current_code_version_id=None,
    )
    narrative = SimpleNamespace(
        id=narrative_version_id,
        prompt_snapshot={"base_prompt_version": "v1"},
    )

    db = MagicMock()

    def fake_get(model, object_id):
        if model is VideoProject:
            return project
        if model is NarrativeVersion:
            return narrative
        return None

    db.get.side_effect = fake_get
    db.execute.return_value.scalars.return_value.first.return_value = None

    with patch("app.workflows.activities.get_sync_session", return_value=db), \
         patch.object(
             activities,
             "style_components_from_snapshot",
             return_value={"narrative_style": "x"},
         ), \
         patch.object(
             activities, "resolve_execution_mode", return_value="agent"
         ) as mock_resolve:
        await activities.submit_code_task(str(project_id))

    task = db.add.call_args.args[0]
    assert task.input_payload["execution_mode"] == "agent"
    mock_resolve.assert_called_once_with(db, project, "code_generation")
