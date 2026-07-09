import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_active_user
from app.db import get_async_session
from app.models.prompt_component import PromptComponent
from app.models.style_template import StyleTemplate
from app.schemas.style_template import (
    StyleTemplateCreate,
    StyleTemplateListResponse,
    StyleTemplateResponse,
    StyleTemplateUpdate,
)

router = APIRouter(prefix="/api/style-templates", tags=["style-templates"])

STYLE_CATEGORIES = {
    "narrative_style",
    "pacing",
    "scene_structure",
    "color_scheme",
    "animation_style",
}


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
