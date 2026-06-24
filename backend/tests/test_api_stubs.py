# backend/tests/test_api_stubs.py
import pytest


STUB_ENDPOINTS = [
    ("GET", "/api/topics"),
    ("POST", "/api/topics"),
    ("POST", "/api/topics/brainstorm"),
    ("GET", "/api/projects"),
    ("POST", "/api/projects"),
    ("GET", "/api/worker-tasks"),
]

PROJECT_ID = "00000000-0000-0000-0000-000000000001"

PROJECT_STUB_ENDPOINTS = [
    ("GET", f"/api/projects/{PROJECT_ID}"),
    ("POST", f"/api/projects/{PROJECT_ID}/review"),
    ("GET", f"/api/projects/{PROJECT_ID}/script-versions"),
    ("GET", f"/api/projects/{PROJECT_ID}/events"),
    ("POST", f"/api/projects/{PROJECT_ID}/performance"),
    ("GET", f"/api/projects/{PROJECT_ID}/preview-url"),
]


@pytest.mark.parametrize("method,path", STUB_ENDPOINTS)
def test_stub_endpoint_returns_todo(client, auth_headers, method, path):
    kwargs = {"headers": auth_headers}
    if method != "GET":
        kwargs["json"] = {}
    response = getattr(client, method.lower())(path, **kwargs)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "TODO"


@pytest.mark.parametrize("method,path", PROJECT_STUB_ENDPOINTS)
def test_project_stub_endpoint_returns_todo(client, auth_headers, method, path):
    kwargs = {"headers": auth_headers}
    if method != "GET":
        kwargs["json"] = {}
    response = getattr(client, method.lower())(path, **kwargs)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "TODO"


def test_topic_patch_stub(client, auth_headers):
    response = client.patch(
        f"/api/topics/{PROJECT_ID}", headers=auth_headers, json={}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "TODO"


def test_protected_endpoints_require_api_key(client):
    response = client.get("/api/topics")
    assert response.status_code == 401
