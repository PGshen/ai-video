import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock
from app.main import app
from app.db import get_async_session
from app.config import settings


@pytest.fixture
def client():
    async def mock_session():
        yield MagicMock()

    app.dependency_overrides[get_async_session] = mock_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    return {"X-API-Key": settings.API_KEY}
