import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.deps import get_temporal_client
from app.db import get_async_session
from app.config import settings


@pytest.fixture
def mock_db():
    db = AsyncMock()
    # db.execute is AsyncMock; its return_value must be a plain MagicMock
    # so that result.scalars() (sync) works correctly.
    execute_result = MagicMock()
    execute_result.scalars.return_value.all.return_value = []
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
    return {"X-API-Key": settings.API_KEY}
