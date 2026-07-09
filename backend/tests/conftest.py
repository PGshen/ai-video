import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.deps import get_temporal_client
from app.db import get_async_session
from app.config import settings
from app.security import CurrentUser, create_access_token


@pytest.fixture
def mock_db():
    db = AsyncMock()
    # db.execute is AsyncMock; its return_value must be a plain MagicMock
    # so that result.scalars() (sync) works correctly.
    execute_result = MagicMock()
    execute_result.scalars.return_value.all.return_value = []
    execute_result.scalar_one.side_effect = (
        lambda: len(execute_result.scalars.return_value.all.return_value)
    )
    db.execute.return_value = execute_result
    db.get = AsyncMock(return_value=None)
    return db


@pytest.fixture
def mock_temporal():
    return AsyncMock()


@pytest.fixture
def client(mock_db, mock_temporal):
    async def override_db():
        yield mock_db

    def override_temporal():
        return mock_temporal

    app.dependency_overrides[get_async_session] = override_db
    app.dependency_overrides[get_temporal_client] = override_temporal
    with patch(
        "app.main.TemporalClient.connect",
        new=AsyncMock(return_value=mock_temporal),
    ):
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    token = create_access_token(
        CurrentUser(
            id="00000000-0000-0000-0000-000000000001",
            username="test-admin",
            display_name="Test Admin",
            role="admin",
            is_active=True,
        )
    )
    return {"Cookie": f"{settings.AUTH_COOKIE_NAME}={token}"}
