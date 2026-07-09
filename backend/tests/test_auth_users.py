from unittest.mock import MagicMock
from uuid import uuid4

from app.models.user import User
from app.security import hash_password


def make_user(role="admin", is_active=True):
    return User(
        id=uuid4(),
        username="admin",
        password_hash=hash_password("secret123"),
        display_name="Admin",
        role=role,
        is_active=is_active,
    )


def test_login_sets_http_only_cookie(client, mock_db):
    user = make_user()
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    mock_db.execute.return_value = result

    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "secret123"},
    )

    assert response.status_code == 200
    assert response.json()["user"]["username"] == "admin"
    cookie = response.headers["set-cookie"]
    assert "ai_video_session=" in cookie
    assert "HttpOnly" in cookie


def test_login_rejects_disabled_user(client, mock_db):
    user = make_user(is_active=False)
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    mock_db.execute.return_value = result

    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "secret123"},
    )

    assert response.status_code == 403


def test_create_user_requires_admin(client, mock_db):
    response = client.post(
        "/api/users",
        json={"username": "editor", "password": "secret123", "role": "user"},
    )

    assert response.status_code == 401


def test_admin_can_create_user(client, auth_headers, mock_db):
    select_result = MagicMock()
    select_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = select_result

    response = client.post(
        "/api/users",
        headers=auth_headers,
        json={"username": "editor", "password": "secret123", "role": "user"},
    )

    assert response.status_code == 201
    created = mock_db.add.call_args.args[0]
    assert created.username == "editor"
    assert created.password_hash != "secret123"
