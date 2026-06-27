from app.models.narrative_version import NarrativeVersion
from app.models.project import VideoProject


def test_narrative_version_model_has_expected_columns():
    cols = {c.key for c in NarrativeVersion.__table__.columns}
    assert "id" in cols
    assert "project_id" in cols
    assert "version_number" in cols
    assert "scenes" in cols
    assert "fact_checks" in cols
    assert "rejection_context" in cols


def test_video_project_has_narrative_version_id_column():
    cols = {c.key for c in VideoProject.__table__.columns}
    assert "current_narrative_version_id" in cols
