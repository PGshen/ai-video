# backend/tests/test_health.py
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_no_auth_required():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_protected_endpoint_without_key_returns_401(client):
    response = client.get("/api/topics")
    assert response.status_code == 401


def test_protected_endpoint_with_invalid_cookie_returns_401(client):
    response = client.get("/api/topics", headers={"Cookie": "ai_video_session=bad-token"})
    assert response.status_code == 401
