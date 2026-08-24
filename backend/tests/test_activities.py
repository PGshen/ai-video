import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4


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
async def test_submit_code_task_writes_execution_mode_into_payload():
    from app.workflows import activities

    captured = {}

    def fake_resolve(db, project, business):
        captured["business"] = business
        return "agent"

    with patch.object(activities, "resolve_execution_mode", fake_resolve):
        mode = activities.resolve_execution_mode(MagicMock(), MagicMock(), "code_generation")

    assert mode == "agent"
    assert captured["business"] == "code_generation"
