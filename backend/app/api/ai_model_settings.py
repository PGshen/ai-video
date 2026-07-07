import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import verify_api_key
from app.db import get_async_session
from app.engines.ai.factory import BUSINESS_OPTIONS
from app.models.ai_model_config import (
    AIBusinessModelConfig,
    AIModelProvider,
    AIProviderModel,
)
from app.schemas.ai_model_config import (
    AIBusinessModelConfigResponse,
    AIBusinessModelConfigUpdate,
    AIBusinessOption,
    AIModelProviderCreate,
    AIModelProviderResponse,
    AIModelProviderUpdate,
    AIModelSettingsResponse,
    AIProviderModelCreate,
    AIProviderModelResponse,
    AIProviderModelUpdate,
)

router = APIRouter(prefix="/api/ai-model-settings", tags=["ai-model-settings"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _provider_response(provider: AIModelProvider) -> AIModelProviderResponse:
    return AIModelProviderResponse(
        id=provider.id,
        name=provider.name,
        provider_type=provider.provider_type,
        base_url=provider.base_url,
        timeout_seconds=provider.timeout_seconds,
        site_url=provider.site_url,
        site_name=provider.site_name,
        is_active=provider.is_active,
        api_key_set=bool(provider.api_key),
        created_at=provider.created_at,
        updated_at=provider.updated_at,
    )


def _model_response(model: AIProviderModel) -> AIProviderModelResponse:
    return AIProviderModelResponse(
        id=model.id,
        provider_id=model.provider_id,
        name=model.name,
        model=model.model,
        content_max_tokens=model.content_max_tokens,
        json_max_tokens=model.json_max_tokens,
        input_cost_per_million=model.input_cost_per_million,
        cached_input_cost_per_million=model.cached_input_cost_per_million,
        output_cost_per_million=model.output_cost_per_million,
        is_active=model.is_active,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _business_response(config: AIBusinessModelConfig) -> AIBusinessModelConfigResponse:
    return AIBusinessModelConfigResponse(
        id=config.id,
        business=config.business,
        model_id=config.model_id,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


@router.get("", response_model=AIModelSettingsResponse)
async def get_model_settings(
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_api_key),
):
    providers = (
        await db.execute(select(AIModelProvider).order_by(AIModelProvider.created_at.desc()))
    ).scalars().all()
    models = (
        await db.execute(select(AIProviderModel).order_by(AIProviderModel.created_at.desc()))
    ).scalars().all()
    configs = (
        await db.execute(
            select(AIBusinessModelConfig).order_by(AIBusinessModelConfig.business.asc())
        )
    ).scalars().all()
    return AIModelSettingsResponse(
        providers=[_provider_response(provider) for provider in providers],
        models=[_model_response(model) for model in models],
        business_configs=[_business_response(config) for config in configs],
        business_options=[
            AIBusinessOption(key=key, label=label) for key, label in BUSINESS_OPTIONS
        ],
    )


@router.post("/providers", response_model=AIModelProviderResponse, status_code=201)
async def create_provider(
    body: AIModelProviderCreate,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_api_key),
):
    provider = AIModelProvider(
        id=uuid.uuid4(),
        **body.model_dump(),
    )
    db.add(provider)
    await db.commit()
    await db.refresh(provider)
    return _provider_response(provider)


@router.put("/providers/{provider_id}", response_model=AIModelProviderResponse)
async def update_provider(
    provider_id: uuid.UUID,
    body: AIModelProviderUpdate,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_api_key),
):
    provider = await db.get(AIModelProvider, provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="AI model provider not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "api_key" and not value:
            continue
        setattr(provider, field, value)
    provider.updated_at = _now()
    await db.commit()
    await db.refresh(provider)
    return _provider_response(provider)


@router.delete("/providers/{provider_id}", status_code=204)
async def delete_provider(
    provider_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_api_key),
):
    provider = await db.get(AIModelProvider, provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="AI model provider not found")

    model_in_use = (
        await db.execute(
            select(AIProviderModel.id)
            .where(AIProviderModel.provider_id == provider_id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if model_in_use is not None:
        raise HTTPException(status_code=409, detail="该供应商下仍有模型配置")

    await db.delete(provider)
    await db.commit()


@router.post("/models", response_model=AIProviderModelResponse, status_code=201)
async def create_model(
    body: AIProviderModelCreate,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_api_key),
):
    provider = await db.get(AIModelProvider, body.provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="AI model provider not found")

    model = AIProviderModel(id=uuid.uuid4(), **body.model_dump())
    db.add(model)
    await db.commit()
    await db.refresh(model)
    return _model_response(model)


@router.put("/models/{model_id}", response_model=AIProviderModelResponse)
async def update_model(
    model_id: uuid.UUID,
    body: AIProviderModelUpdate,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_api_key),
):
    model = await db.get(AIProviderModel, model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="AI provider model not found")

    update_data = body.model_dump(exclude_unset=True)
    if "provider_id" in update_data:
        provider = await db.get(AIModelProvider, update_data["provider_id"])
        if provider is None:
            raise HTTPException(status_code=404, detail="AI model provider not found")

    for field, value in update_data.items():
        setattr(model, field, value)
    model.updated_at = _now()
    await db.commit()
    await db.refresh(model)
    return _model_response(model)


@router.delete("/models/{model_id}", status_code=204)
async def delete_model(
    model_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_api_key),
):
    model = await db.get(AIProviderModel, model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="AI provider model not found")

    in_use = (
        await db.execute(
            select(AIBusinessModelConfig.id)
            .where(AIBusinessModelConfig.model_id == model_id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if in_use is not None:
        raise HTTPException(status_code=409, detail="该模型仍被业务配置引用")

    await db.delete(model)
    await db.commit()


@router.put("/business-configs/{business}", response_model=AIBusinessModelConfigResponse)
async def set_business_config(
    business: str,
    body: AIBusinessModelConfigUpdate,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_api_key),
):
    allowed = {key for key, _ in BUSINESS_OPTIONS}
    if business not in allowed:
        raise HTTPException(status_code=404, detail="Unknown AI business")
    if body.model_id is None:
        raise HTTPException(status_code=422, detail="modelId is required")

    model = await db.get(AIProviderModel, body.model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="AI provider model not found")
    if not model.is_active:
        raise HTTPException(status_code=409, detail="Cannot assign an inactive model")

    provider = await db.get(AIModelProvider, model.provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="AI model provider not found")
    if not provider.is_active:
        raise HTTPException(status_code=409, detail="Cannot assign an inactive provider")

    result = await db.execute(
        select(AIBusinessModelConfig).where(AIBusinessModelConfig.business == business)
    )
    config = result.scalar_one_or_none()
    if config is None:
        config = AIBusinessModelConfig(
            id=uuid.uuid4(),
            business=business,
            model_id=body.model_id,
        )
        db.add(config)
    else:
        config.model_id = body.model_id
        config.updated_at = _now()
    await db.commit()
    await db.refresh(config)
    return _business_response(config)


@router.delete("/business-configs/{business}", status_code=204)
async def delete_business_config(
    business: str,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_api_key),
):
    result = await db.execute(
        select(AIBusinessModelConfig).where(AIBusinessModelConfig.business == business)
    )
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(status_code=404, detail="AI business config not found")
    await db.delete(config)
    await db.commit()
