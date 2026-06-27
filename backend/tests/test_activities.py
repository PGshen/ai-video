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


