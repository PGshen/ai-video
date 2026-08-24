from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

from app.engines.ai import factory
from app.models.ai_model_config import (
    AIBusinessModelConfig,
    AIModelProvider,
    AIProviderModel,
)


def _provider(**kwargs):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=kwargs.get("id", uuid4()),
        name=kwargs.get("name", "DeepSeek"),
        provider_type=kwargs.get("provider_type", "deepseek"),
        base_url=kwargs.get("base_url", "https://api.deepseek.com"),
        api_key=kwargs.get("api_key", "sk-test"),
        timeout_seconds=kwargs.get("timeout_seconds", 600.0),
        site_url=kwargs.get("site_url", None),
        site_name=kwargs.get("site_name", None),
        is_active=kwargs.get("is_active", True),
        created_at=kwargs.get("created_at", now),
        updated_at=kwargs.get("updated_at", now),
    )


def _model(provider_id, **kwargs):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=kwargs.get("id", uuid4()),
        provider_id=provider_id,
        name=kwargs.get("name", "DeepSeek Flash"),
        model=kwargs.get("model", "deepseek-test"),
        content_max_tokens=kwargs.get("content_max_tokens", 100000),
        json_max_tokens=kwargs.get("json_max_tokens", 100000),
        input_cost_per_million=kwargs.get("input_cost_per_million", Decimal("1")),
        cached_input_cost_per_million=kwargs.get(
            "cached_input_cost_per_million", Decimal("0.1")
        ),
        output_cost_per_million=kwargs.get("output_cost_per_million", Decimal("2")),
        is_active=kwargs.get("is_active", True),
        created_at=kwargs.get("created_at", now),
        updated_at=kwargs.get("updated_at", now),
    )


def _config(model_id, business="topic_brainstorm"):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id=uuid4(),
        business=business,
        model_id=model_id,
        created_at=now,
        updated_at=now,
    )


def test_get_model_settings_returns_two_level_settings(client, auth_headers, mock_db):
    provider = _provider()
    model = _model(provider.id)
    config = _config(model.id)
    provider_result = MagicMock()
    provider_result.scalars.return_value.all.return_value = [provider]
    model_result = MagicMock()
    model_result.scalars.return_value.all.return_value = [model]
    config_result = MagicMock()
    config_result.scalars.return_value.all.return_value = [config]
    mock_db.execute.side_effect = [provider_result, model_result, config_result]

    response = client.get("/api/ai-model-settings", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["providers"][0]["name"] == "DeepSeek"
    assert data["providers"][0]["apiKeySet"] is True
    assert "apiKey" not in data["providers"][0]
    assert data["models"][0]["model"] == "deepseek-test"
    assert data["models"][0]["providerId"] == str(provider.id)
    assert data["businessConfigs"][0]["modelId"] == str(model.id)
    assert any(option["key"] == "code_generation" for option in data["businessOptions"])


def test_create_model_provider_masks_api_key(client, auth_headers, mock_db):
    now = datetime.now(timezone.utc)

    async def refresh_with_timestamps(provider):
        provider.created_at = now
        provider.updated_at = now

    mock_db.refresh.side_effect = refresh_with_timestamps

    response = client.post(
        "/api/ai-model-settings/providers",
        headers=auth_headers,
        json={
            "name": "Doubao",
            "providerType": "doubao",
            "baseUrl": "https://ark.cn-beijing.volcengine.com/api/v3",
            "apiKey": "sk-test",
            "timeoutSeconds": 600,
            "isActive": True,
        },
    )

    assert response.status_code == 201
    created = mock_db.add.call_args.args[0]
    assert isinstance(created, AIModelProvider)
    assert created.api_key == "sk-test"
    assert response.json()["apiKeySet"] is True
    assert "apiKey" not in response.json()


def test_create_provider_model(client, auth_headers, mock_db):
    provider = _provider()
    mock_db.get.return_value = provider
    now = datetime.now(timezone.utc)

    async def refresh_with_timestamps(model):
        model.created_at = now
        model.updated_at = now

    mock_db.refresh.side_effect = refresh_with_timestamps

    response = client.post(
        "/api/ai-model-settings/models",
        headers=auth_headers,
        json={
            "providerId": str(provider.id),
            "name": "Flash",
            "model": "deepseek-test",
            "contentMaxTokens": 100000,
            "jsonMaxTokens": 100000,
            "inputCostPerMillion": "0",
            "cachedInputCostPerMillion": "0",
            "outputCostPerMillion": "0",
            "isActive": True,
        },
    )

    assert response.status_code == 201
    created = mock_db.add.call_args.args[0]
    assert isinstance(created, AIProviderModel)
    assert created.provider_id == provider.id
    assert created.model == "deepseek-test"


def test_set_business_model_config(client, auth_headers, mock_db):
    provider = _provider()
    model = _model(provider.id)

    async def get_model(model_cls, pk):
        if model_cls.__name__ == "AIProviderModel":
            return model
        return provider

    mock_db.get.side_effect = get_model
    lookup_result = MagicMock()
    lookup_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = lookup_result
    now = datetime.now(timezone.utc)

    async def refresh_with_timestamps(config):
        config.created_at = now
        config.updated_at = now

    mock_db.refresh.side_effect = refresh_with_timestamps

    response = client.put(
        "/api/ai-model-settings/business-configs/code_generation",
        headers=auth_headers,
        json={"modelId": str(model.id)},
    )

    assert response.status_code == 200
    created = mock_db.add.call_args.args[0]
    assert isinstance(created, AIBusinessModelConfig)
    assert created.business == "code_generation"
    assert created.model_id == model.id


def test_get_ai_provider_uses_business_specific_db_model(monkeypatch):
    provider = _provider()
    model = _model(provider.id, model="deepseek-business")
    config = _config(model.id, business="topic_brainstorm")

    class Result:
        def scalar_one_or_none(self):
            return config

    class Session:
        def execute(self, _statement):
            return Result()

        def get(self, model_cls, pk):
            if model_cls is AIProviderModel and pk == model.id:
                return model
            if model_cls is AIModelProvider and pk == provider.id:
                return provider
            return None

        def close(self):
            pass

    monkeypatch.setattr(factory, "get_sync_session", lambda: Session())

    ai_provider = factory.get_ai_provider("topic_brainstorm")

    assert ai_provider.engine_name == "deepseek"
    assert ai_provider.model_name == "deepseek-business"


from app.schemas.ai_model_config import AIModelProviderCreate


def test_anthropic_provider_accepts_empty_base_url():
    provider = AIModelProviderCreate(
        name="Anthropic 官方",
        provider_type="anthropic",
        base_url="",
        api_key="sk-test",
    )
    assert provider.provider_type == "anthropic"
    assert provider.base_url == ""


def test_anthropic_provider_accepts_gateway_base_url():
    provider = AIModelProviderCreate(
        name="中转",
        provider_type="anthropic",
        base_url="https://gateway.example.com",
        api_key="sk-test",
    )
    assert provider.base_url == "https://gateway.example.com"
