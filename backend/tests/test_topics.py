import pytest
from unittest.mock import MagicMock, AsyncMock
from uuid import uuid4
from datetime import datetime, timezone


def make_topic(**kwargs):
    t = MagicMock()
    t.id = kwargs.get("id", uuid4())
    t.title = kwargs.get("title", "Test Topic")
    t.description = kwargs.get("description", None)
    t.source = kwargs.get("source", "manual")
    t.status = kwargs.get("status", "pending")
    t.score_counterintuitive = kwargs.get("score_counterintuitive", None)
    t.score_defensibility = kwargs.get("score_defensibility", None)
    t.score_visual = kwargs.get("score_visual", None)
    t.score_freshness = kwargs.get("score_freshness", None)
    t.composite_score = kwargs.get("composite_score", None)
    t.performance_score = kwargs.get("performance_score", None)
    t.tags = kwargs.get("tags", [])
    t.needs_recheck = kwargs.get("needs_recheck", False)
    t.research_data = kwargs.get("research_data", [])
    t.researchData = t.research_data  # prevent MagicMock auto-attr from shadowing alias
    t.created_at = kwargs.get("created_at", datetime.now(timezone.utc))
    t.updated_at = kwargs.get("updated_at", datetime.now(timezone.utc))
    return t


def test_list_topics_empty(client, auth_headers, mock_db):
    mock_db.execute.return_value.scalars.return_value.all.return_value = []
    response = client.get("/api/topics", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


def test_list_topics_returns_items(client, auth_headers, mock_db):
    topics = [make_topic(title="T1"), make_topic(title="T2")]
    mock_db.execute.return_value.scalars.return_value.all.return_value = topics
    response = client.get("/api/topics", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert data["items"][0]["title"] == "T1"


def test_create_topic(client, auth_headers, mock_db):
    created = make_topic(title="New Topic", source="manual")
    mock_db.refresh = AsyncMock(return_value=None)
    # After refresh, the mock_db.add was called and refresh populates the object
    # We simulate refresh by making the topic returned from get == created
    response = client.post(
        "/api/topics",
        headers=auth_headers,
        json={"title": "New Topic", "source": "manual", "tags": []},
    )
    assert response.status_code == 201


def test_create_topic_missing_title_returns_422(client, auth_headers):
    response = client.post(
        "/api/topics",
        headers=auth_headers,
        json={"source": "manual"},
    )
    assert response.status_code == 422


def test_update_topic_scores(client, auth_headers, mock_db):
    topic = make_topic()
    mock_db.get.return_value = topic
    response = client.patch(
        f"/api/topics/{topic.id}",
        headers=auth_headers,
        json={"scores": {"counterintuitive": 4, "defensibility": 3, "visual": 5, "freshness": 2}},
    )
    assert response.status_code == 200
    assert topic.score_counterintuitive == 4
    assert topic.score_defensibility == 3


def test_update_topic_not_found(client, auth_headers, mock_db):
    mock_db.get.return_value = None
    response = client.patch(
        f"/api/topics/{uuid4()}",
        headers=auth_headers,
        json={"status": "stocked"},
    )
    assert response.status_code == 404


def test_brainstorm_returns_candidates(client, auth_headers):
    response = client.post(
        "/api/topics/brainstorm",
        headers=auth_headers,
        json={"topic_direction": "science", "count": 3},
    )
    assert response.status_code == 200
    data = response.json()
    assert "candidates" in data
    assert len(data["candidates"]) == 3


def test_topics_require_api_key(client):
    response = client.get("/api/topics")
    assert response.status_code == 401


def test_topic_response_includes_research_data(client, auth_headers, mock_db):
    topic = make_topic(research_data=[{"role": "user", "content": "hi", "createdAt": "2026-01-01T00:00:00Z"}])
    mock_db.execute.return_value.scalars.return_value.all.return_value = [topic]
    response = client.get("/api/topics", headers=auth_headers)
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert "researchData" in item
    assert item["researchData"][0]["role"] == "user"
