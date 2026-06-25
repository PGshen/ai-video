from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth import verify_api_key
from app.db import get_async_session
from app.models.topic import Topic
from app.schemas.topic import (
    TopicCreate, TopicUpdate, TopicResponse, TopicListResponse,
    BrainstormRequest, BrainstormResponse,
)

router = APIRouter(prefix="/api/topics", tags=["topics"])


@router.get("", response_model=TopicListResponse)
async def list_topics(
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_api_key),
):
    stmt = select(Topic)
    if status:
        stmt = stmt.where(Topic.status == status)
    stmt = stmt.order_by(Topic.created_at.desc())
    result = await db.execute(stmt)
    items = result.scalars().all()
    return TopicListResponse(items=items, total=len(items))


@router.post("", response_model=TopicResponse, status_code=201)
async def create_topic(
    body: TopicCreate,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_api_key),
):
    topic = Topic(
        title=body.title,
        description=body.description,
        source=body.source,
        tags=body.tags,
        score_counterintuitive=body.scores.counterintuitive,
        score_defensibility=body.scores.defensibility,
        score_visual=body.scores.visual,
        score_freshness=body.scores.freshness,
    )
    db.add(topic)
    await db.commit()
    await db.refresh(topic)
    return topic


@router.post("/brainstorm", response_model=BrainstormResponse)
async def brainstorm_topics(
    body: BrainstormRequest,
    _=Depends(verify_api_key),
):
    # Sprint 2: replace with real Claude API call
    candidates = [
        {
            "title": "为什么飞机翅膀向上弯曲而不是向下",
            "description": "解释机翼弯曲方向与升力的反直觉关系",
            "tags": ["航空", "物理", "工程"],
        },
        {
            "title": "大脑中的记忆并不是「存储」的",
            "description": "记忆是每次回忆时重新构建的，而非调取固定文件",
            "tags": ["神经科学", "认知", "心理学"],
        },
        {
            "title": "为什么节食反而让你更容易变胖",
            "description": "身体代谢适应机制：极低热量摄入如何触发「饥荒模式」",
            "tags": ["健康", "营养", "进化生物学"],
        },
    ]
    return BrainstormResponse(candidates=candidates[: body.count])


@router.patch("/{topic_id}", response_model=TopicResponse)
async def update_topic(
    topic_id: UUID,
    body: TopicUpdate,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_api_key),
):
    topic = await db.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    update_data = body.model_dump(exclude_none=True)
    if "scores" in update_data:
        scores = update_data.pop("scores")
        if scores.get("counterintuitive") is not None:
            topic.score_counterintuitive = scores["counterintuitive"]
        if scores.get("defensibility") is not None:
            topic.score_defensibility = scores["defensibility"]
        if scores.get("visual") is not None:
            topic.score_visual = scores["visual"]
        if scores.get("freshness") is not None:
            topic.score_freshness = scores["freshness"]

    for field, value in update_data.items():
        setattr(topic, field, value)

    await db.commit()
    await db.refresh(topic)
    return topic
