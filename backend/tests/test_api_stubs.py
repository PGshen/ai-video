import pytest

STUB_ENDPOINTS = [
    ("GET", "/api/worker-tasks"),
]

PROJECT_ID = "00000000-0000-0000-0000-000000000001"


@pytest.mark.parametrize("method,path", STUB_ENDPOINTS)
def test_stub_endpoint_returns_todo(client, auth_headers, method, path):
    kwargs = {"headers": auth_headers}
    if method != "GET":
        kwargs["json"] = {}
    response = getattr(client, method.lower())(path, **kwargs)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "TODO"


def test_protected_endpoints_require_api_key(client):
    response = client.get("/api/topics")
    assert response.status_code == 401
