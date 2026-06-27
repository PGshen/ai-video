import pytest
from unittest.mock import AsyncMock, MagicMock
from app.workflows.video_production import VideoProductionWorkflow


def test_workflow_has_narrative_generated_signal():
    wf = VideoProductionWorkflow()
    assert hasattr(wf, "narrative_generated")


def test_workflow_has_narrative_review_signal():
    wf = VideoProductionWorkflow()
    assert hasattr(wf, "narrative_review")


def test_workflow_has_code_generated_signal():
    wf = VideoProductionWorkflow()
    assert hasattr(wf, "code_generated")


def test_workflow_does_not_have_script_generated_signal():
    wf = VideoProductionWorkflow()
    assert not hasattr(wf, "script_generated")
