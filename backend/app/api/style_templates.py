import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_active_user
from app.db import get_async_session
from app.engines.ai.factory import get_ai_provider
from app.models.prompt_component import PromptComponent
from app.models.style_template import StyleTemplate
from app.schemas.style_template import (
    StyleLibraryAssistantRequest,
    StyleLibraryAssistantResponse,
    StyleLibraryComponentDraft,
    StyleLibraryComponentInput,
    StyleLibraryUpsert,
    StyleTemplateCreate,
    StyleTemplateListResponse,
    StyleTemplateResponse,
    StyleTemplateUpdate,
)

router = APIRouter(prefix="/api/style-templates", tags=["style-templates"])
logger = logging.getLogger(__name__)

from app.services.prompt_bundle import STYLE_CATEGORIES as _STYLE_CATEGORIES

STYLE_CATEGORIES = set(_STYLE_CATEGORIES)


def _to_response(template: StyleTemplate) -> StyleTemplateResponse:
    return StyleTemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        style_config=template.style_config or {},
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


async def _validate_style_config(
    db: AsyncSession, style_config: dict[str, str]
) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for category, raw_id in style_config.items():
        if category not in STYLE_CATEGORIES:
            raise HTTPException(
                status_code=422, detail=f"style_config[{category}]: unknown category"
            )
        try:
            component_id = uuid.UUID(str(raw_id))
        except ValueError as exc:
            raise HTTPException(
                status_code=422, detail=f"style_config[{category}]: invalid UUID"
            ) from exc
        component = await db.get(PromptComponent, component_id)
        if component is None:
            raise HTTPException(
                status_code=422, detail=f"style_config[{category}]: component not found"
            )
        if component.category != category:
            raise HTTPException(
                status_code=422,
                detail=f"style_config[{category}]: component category mismatch",
            )
        normalized[category] = str(component_id)
    return normalized


def _new_component(
    category: str, data: StyleLibraryComponentInput
) -> PromptComponent:
    return PromptComponent(
        id=uuid.uuid4(),
        category=category,
        name=data.name.strip(),
        description=data.description.strip() if data.description else None,
        prompt_text=data.prompt_text.strip(),
        is_builtin=False,
    )


def _update_component(
    component: PromptComponent, data: StyleLibraryComponentInput
) -> None:
    component.name = data.name.strip()
    component.description = data.description.strip() if data.description else None
    component.prompt_text = data.prompt_text.strip()


@router.get("", response_model=StyleTemplateListResponse)
async def list_style_templates(
    db: AsyncSession = Depends(get_async_session),
    _=Depends(require_active_user),
):
    result = await db.execute(
        select(StyleTemplate).order_by(StyleTemplate.updated_at.desc())
    )
    items = result.scalars().all()
    return StyleTemplateListResponse(
        items=[_to_response(item) for item in items], total=len(items)
    )


@router.post("", response_model=StyleTemplateResponse, status_code=201)
async def create_style_template(
    body: StyleTemplateCreate,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(require_active_user),
):
    style_config = await _validate_style_config(db, body.style_config)
    template = StyleTemplate(
        id=uuid.uuid4(),
        name=body.name.strip(),
        description=body.description.strip() if body.description else None,
        style_config=style_config,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return _to_response(template)


@router.post("/library", response_model=StyleTemplateResponse, status_code=201)
async def create_style_library(
    body: StyleLibraryUpsert,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(require_active_user),
):
    style_config: dict[str, str] = {}
    for category, component_data in body.components.items():
        component = _new_component(category, component_data)
        db.add(component)
        style_config[category] = str(component.id)

    template = StyleTemplate(
        id=uuid.uuid4(),
        name=body.name.strip(),
        description=body.description.strip() if body.description else None,
        style_config=style_config,
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return _to_response(template)


@router.post("/assist", response_model=StyleLibraryAssistantResponse)
async def assist_style_library(
    body: StyleLibraryAssistantRequest,
    _=Depends(require_active_user),
):
    provider = get_ai_provider("style_assistant")
    try:
        result = await provider.assist_style_library(
            name=body.name,
            description=body.description,
            components={
                category: component.model_dump()
                for category, component in body.components.items()
            },
            conversation_history=[
                message.model_dump() for message in body.conversation_history
            ],
            new_message=body.message.strip(),
        )
        return StyleLibraryAssistantResponse(
            reply=result.reply,
            name=result.name,
            description=result.description,
            components={
                category: StyleLibraryComponentDraft(**component)
                for category, component in result.components.items()
            },
        )
    except Exception as exc:
        logger.exception("Style library assistant failed")
        raise HTTPException(
            status_code=503,
            detail="AI style library assistant temporarily unavailable",
        ) from exc


@router.put("/{template_id}", response_model=StyleTemplateResponse)
async def update_style_template(
    template_id: uuid.UUID,
    body: StyleTemplateUpdate,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(require_active_user),
):
    template = await db.get(StyleTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Style template not found")
    if body.name is not None:
        template.name = body.name.strip()
    if body.description is not None:
        template.description = body.description.strip() or None
    if body.style_config is not None:
        template.style_config = await _validate_style_config(db, body.style_config)
    await db.commit()
    await db.refresh(template)
    return _to_response(template)


@router.put("/{template_id}/library", response_model=StyleTemplateResponse)
async def update_style_library(
    template_id: uuid.UUID,
    body: StyleLibraryUpsert,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(require_active_user),
):
    template = await db.get(StyleTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Style template not found")

    result = await db.execute(select(StyleTemplate))
    shared_component_ids = {
        str(component_id)
        for other_template in result.scalars().all()
        if str(other_template.id) != str(template_id)
        for component_id in (other_template.style_config or {}).values()
    }

    next_style_config: dict[str, str] = {}
    current_style_config = template.style_config or {}
    for category, component_data in body.components.items():
        raw_component_id = current_style_config.get(category)
        component = None
        if raw_component_id:
            try:
                component = await db.get(
                    PromptComponent, uuid.UUID(str(raw_component_id))
                )
            except ValueError:
                component = None

        can_update_in_place = (
            component is not None
            and component.category == category
            and not component.is_builtin
            and str(component.id) not in shared_component_ids
        )
        if can_update_in_place:
            _update_component(component, component_data)
        else:
            component = _new_component(category, component_data)
            db.add(component)
        next_style_config[category] = str(component.id)

    template.name = body.name.strip()
    template.description = body.description.strip() if body.description else None
    template.style_config = next_style_config
    await db.commit()
    await db.refresh(template)
    return _to_response(template)


@router.delete("/{template_id}", status_code=204)
async def delete_style_template(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(require_active_user),
):
    template = await db.get(StyleTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Style template not found")
    await db.delete(template)
    await db.commit()
