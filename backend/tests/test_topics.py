import json
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


def test_list_topics_filters_by_title(client, auth_headers, mock_db):
    mock_db.execute.return_value.scalars.return_value.all.return_value = []

    response = client.get(
        "/api/topics?title=%E9%87%8F%E5%AD%90",
        headers=auth_headers,
    )

    assert response.status_code == 200
    statement = mock_db.execute.await_args.args[0]
    assert "lower(topics.title) LIKE lower" in str(statement)


def test_list_topics_applies_pagination(client, auth_headers, mock_db):
    mock_db.execute.return_value.scalars.return_value.all.return_value = []

    response = client.get(
        "/api/topics?page=3&page_size=20",
        headers=auth_headers,
    )

    assert response.status_code == 200
    statement = mock_db.execute.await_args.args[0]
    params = statement.compile().params
    assert 40 in params.values()
    assert 20 in params.values()


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


def test_delete_topic(client, auth_headers, mock_db):
    topic = make_topic()
    mock_db.get.return_value = topic
    mock_db.execute.return_value.scalar_one_or_none.return_value = None

    response = client.delete(f"/api/topics/{topic.id}", headers=auth_headers)

    assert response.status_code == 204
    mock_db.delete.assert_awaited_once_with(topic)
    mock_db.commit.assert_awaited_once()


def test_delete_topic_rejects_topic_with_project(client, auth_headers, mock_db):
    topic = make_topic()
    mock_db.get.return_value = topic
    mock_db.execute.return_value.scalar_one_or_none.return_value = uuid4()

    response = client.delete(f"/api/topics/{topic.id}", headers=auth_headers)

    assert response.status_code == 409
    mock_db.delete.assert_not_awaited()


def test_delete_topic_not_found(client, auth_headers, mock_db):
    mock_db.get.return_value = None

    response = client.delete(f"/api/topics/{uuid4()}", headers=auth_headers)

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


def test_research_topic_streams_response(client, auth_headers, mock_db):
    from unittest.mock import patch

    topic = make_topic(
        title="量子纠缠",
        description="粒子间的神秘关联",
        research_data=[],
    )
    mock_db.get = AsyncMock(return_value=topic)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    async def fake_research(*args, **kwargs):
        for chunk in ["## 核心理论\n", "量子纠缠是..."]:
            yield chunk

    with patch(
        "app.api.topics.get_ai_provider",
        return_value=type("P", (), {"research_topic": lambda self, **kw: fake_research(**kw)})(),
    ):
        response = client.post(
            f"/api/topics/{topic.id}/research",
            headers=auth_headers,
            json={"message": "介绍核心理论", "use_default_prompt": False},
        )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    body = response.text
    assert "data: " in body
    assert "[DONE]" in body
    data_lines = [
        line.removeprefix("data: ")
        for line in body.splitlines()
        if line.startswith("data: {")
    ]
    assert json.loads(data_lines[0])["content"] == "## 核心理论\n"


def test_research_topic_404_when_not_found(client, auth_headers, mock_db):
    mock_db.get = AsyncMock(return_value=None)
    response = client.post(
        f"/api/topics/00000000-0000-0000-0000-000000000000/research",
        headers=auth_headers,
        json={"message": "test"},
    )
    assert response.status_code == 404


def test_research_topic_default_prompt(client, auth_headers, mock_db):
    from unittest.mock import patch

    topic = make_topic(title="黑洞", description="时空曲率极大处", research_data=[])
    mock_db.get = AsyncMock(return_value=topic)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    received_kwargs = {}

    async def fake_research(**kwargs):
        received_kwargs.update(kwargs)
        yield "测试内容"

    with patch(
        "app.api.topics.get_ai_provider",
        return_value=type("P", (), {"research_topic": lambda self, **kw: fake_research(**kw)})(),
    ):
        client.post(
            f"/api/topics/{topic.id}/research",
            headers=auth_headers,
            json={"use_default_prompt": True},
        )
    assert received_kwargs.get("use_default_prompt") is True
