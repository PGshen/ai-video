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


def test_submit_script_generation_task_populates_input_payload():
    """Activity 应从 topics 表读取 title/description 写入 input_payload"""
    project = make_project()
    topic = make_topic(title="生命中点", description="关于时间感知的选题")

    added_task = None

    def fake_add(obj):
        nonlocal added_task
        added_task = obj

    mock_db = MagicMock()
    mock_db.get.side_effect = lambda model, pk: (
        project if model.__name__ == "VideoProject" else topic
    )
    mock_db.add.side_effect = fake_add

    # 没有历史 rejection event
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = None
    mock_db.execute.return_value = mock_result

    with patch("app.workflows.activities.get_sync_session", return_value=mock_db):
        import asyncio
        from app.workflows.activities import submit_script_generation_task
        asyncio.run(submit_script_generation_task(str(project.id)))

    assert added_task is not None
    payload = added_task.input_payload
    assert payload["topic_title"] == "生命中点"
    assert payload["topic_description"] == "关于时间感知的选题"
    assert payload["render_engine"] == "manim"
    assert payload["rejection_context"] is None


def test_submit_script_generation_task_includes_rejection_context():
    """有历史驳回事件时，rejection_context 应被填入"""
    project = make_project()
    topic = make_topic()

    rejected_event = MagicMock()
    rejected_event.payload = {
        "rejection_type": "fact_error",
        "rejection_detail": "第2条事实有误",
    }

    added_task = None

    def fake_add(obj):
        nonlocal added_task
        added_task = obj

    mock_db = MagicMock()
    mock_db.get.side_effect = lambda model, pk: (
        project if model.__name__ == "VideoProject" else topic
    )
    mock_db.add.side_effect = fake_add
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = rejected_event
    mock_db.execute.return_value = mock_result

    with patch("app.workflows.activities.get_sync_session", return_value=mock_db):
        import asyncio
        from app.workflows.activities import submit_script_generation_task
        asyncio.run(submit_script_generation_task(str(project.id)))

    assert added_task.input_payload["rejection_context"] == rejected_event.payload
