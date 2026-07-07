import logging
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth import verify_api_key
from app.db import get_async_session
from app.engines.ai.factory import get_ai_provider
from app.models.prompt_component import PromptComponent
from app.models.style_template import StyleTemplate
from app.schemas.prompt_component import (
    PromptComponentCreate, PromptComponentUpdate,
    PromptComponentResponse, PromptComponentListResponse,
    StyleAssistantRequest, StyleAssistantResponse,
)

router = APIRouter(prefix="/api/prompt-components", tags=["prompt-components"])
logger = logging.getLogger(__name__)


def _to_response(pc: PromptComponent) -> PromptComponentResponse:
    return PromptComponentResponse(
        id=pc.id,
        category=pc.category,
        name=pc.name,
        description=pc.description,
        prompt_text=pc.prompt_text,
        is_builtin=pc.is_builtin,
        created_by=pc.created_by,
        created_at=pc.created_at,
        updated_at=pc.updated_at,
    )


@router.get("", response_model=PromptComponentListResponse)
async def list_prompt_components(
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_api_key),
):
    stmt = select(PromptComponent).order_by(PromptComponent.is_builtin.desc(), PromptComponent.name)
    if category:
        stmt = stmt.where(PromptComponent.category == category)
    result = await db.execute(stmt)
    items = result.scalars().all()
    return PromptComponentListResponse(items=[_to_response(pc) for pc in items], total=len(items))


@router.post("", response_model=PromptComponentResponse, status_code=201)
async def create_prompt_component(
    body: PromptComponentCreate,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_api_key),
):
    pc = PromptComponent(
        id=uuid.uuid4(),
        category=body.category,
        name=body.name,
        description=body.description,
        prompt_text=body.prompt_text,
        is_builtin=False,
    )
    db.add(pc)
    await db.commit()
    await db.refresh(pc)
    return _to_response(pc)


@router.post("/assist", response_model=StyleAssistantResponse)
async def assist_prompt_component(
    body: StyleAssistantRequest,
    _=Depends(verify_api_key),
):
    provider = get_ai_provider("style_assistant")
    try:
        result = await provider.assist_style_prompt(
            category=body.category,
            name=body.name,
            description=body.description,
            prompt_text=body.prompt_text,
            conversation_history=[
                message.model_dump() for message in body.conversation_history
            ],
            new_message=body.message.strip(),
        )
    except Exception as exc:
        logger.exception("Style prompt assistant failed")
        raise HTTPException(
            status_code=503,
            detail="AI style assistant temporarily unavailable",
        ) from exc
    return StyleAssistantResponse(
        reply=result.reply,
        name=result.name,
        description=result.description,
        prompt_text=result.prompt_text,
    )


@router.put("/{component_id}", response_model=PromptComponentResponse)
async def update_prompt_component(
    component_id: uuid.UUID,
    body: PromptComponentUpdate,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_api_key),
):
    pc = await db.get(PromptComponent, component_id)
    if pc is None:
        raise HTTPException(status_code=404, detail="Component not found")
    if pc.is_builtin:
        raise HTTPException(status_code=403, detail="Cannot modify built-in components")
    if body.category is not None:
        pc.category = body.category
    if body.name is not None:
        pc.name = body.name
    if body.description is not None:
        pc.description = body.description
    if body.prompt_text is not None:
        pc.prompt_text = body.prompt_text
    await db.commit()
    await db.refresh(pc)
    return _to_response(pc)


@router.delete("/{component_id}", status_code=204)
async def delete_prompt_component(
    component_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_api_key),
):
    pc = await db.get(PromptComponent, component_id)
    if pc is None:
        raise HTTPException(status_code=404, detail="Component not found")
    if pc.is_builtin:
        raise HTTPException(status_code=403, detail="Cannot delete built-in components")
    result = await db.execute(select(StyleTemplate))
    for template in result.scalars().all():
        cleaned_config = {
            category: saved_id
            for category, saved_id in (template.style_config or {}).items()
            if str(saved_id) != str(component_id)
        }
        if cleaned_config != (template.style_config or {}):
            template.style_config = cleaned_config
            flag_modified(template, "style_config")
    await db.delete(pc)
    await db.commit()


@router.post("/{component_id}/duplicate", response_model=PromptComponentResponse, status_code=201)
async def duplicate_prompt_component(
    component_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_api_key),
):
    pc = await db.get(PromptComponent, component_id)
    if pc is None:
        raise HTTPException(status_code=404, detail="Component not found")
    new_pc = PromptComponent(
        id=uuid.uuid4(),
        category=pc.category,
        name=f"{pc.name}（副本）",
        description=pc.description,
        prompt_text=pc.prompt_text,
        is_builtin=False,
    )
    db.add(new_pc)
    await db.commit()
    await db.refresh(new_pc)
    return _to_response(new_pc)
