import json
from typing import Optional
from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth import verify_api_key
from app.db import get_async_session
from app.engines.ai.factory import get_ai_provider
from app.models.project import VideoProject
from app.models.topic import Topic
from app.schemas.topic import (
    TopicCreate, TopicUpdate, TopicResponse, TopicListResponse,
    BrainstormRequest, BrainstormResponse, ResearchMessageRequest,
)

router = APIRouter(prefix="/api/topics", tags=["topics"])


@router.get("", response_model=TopicListResponse)
async def list_topics(
    status: Optional[str] = None,
    title: Optional[str] = None,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_api_key),
):
    stmt = select(Topic)
    if status:
        stmt = stmt.where(Topic.status == status)
    if title and title.strip():
        stmt = stmt.where(Topic.title.ilike(f"%{title.strip()}%"))
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
    provider = get_ai_provider()
    try:
        result = await provider.brainstorm_topics(body.topic_direction, body.count)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="AI service temporarily unavailable") from exc
    return BrainstormResponse(candidates=result.candidates[: body.count])


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


@router.delete("/{topic_id}", status_code=204)
async def delete_topic(
    topic_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_api_key),
):
    topic = await db.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    project_result = await db.execute(
        select(VideoProject.id).where(VideoProject.topic_id == topic_id).limit(1)
    )
    if project_result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409,
            detail="该选题已关联视频项目，请先删除相关项目",
        )

    await db.delete(topic)
    await db.commit()


DEFAULT_RESEARCH_SYSTEM_PROMPT = """\
你是一位知识视频选题研究助手。当前研究的选题是：

标题：{topic_title}
描述：{topic_description}

请围绕该选题提供背景资料，内容以 Markdown 格式输出，重点包括：核心概念、相关理论、反直觉角度、可视化潜力等。\
"""

DEFAULT_RESEARCH_QUESTION = "请介绍这个选题的背景知识和核心理论"


@router.post("/{topic_id}/research")
async def research_topic(
    topic_id: UUID,
    body: ResearchMessageRequest,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_api_key),
):
    topic = await db.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    if not body.use_default_prompt and not body.message.strip():
        raise HTTPException(status_code=422, detail="message is required when use_default_prompt is false")

    history: list[dict] = topic.research_data or []
    conversation_history = [{"role": m["role"], "content": m["content"]} for m in history]

    if body.use_default_prompt:
        system_prompt = DEFAULT_RESEARCH_SYSTEM_PROMPT.format(
            topic_title=topic.title,
            topic_description=topic.description or "",
        )
        user_message = DEFAULT_RESEARCH_QUESTION
    else:
        system_prompt = None
        user_message = body.message

    provider = get_ai_provider()

    async def event_stream():
        full_response = []
        try:
            async for chunk in provider.research_topic(
                topic_title=topic.title,
                topic_description=topic.description or "",
                conversation_history=conversation_history,
                new_message=user_message,
                use_default_prompt=body.use_default_prompt,
                system_prompt=system_prompt,
            ):
                full_response.append(chunk)
                yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
        except Exception:
            yield "data: [ERROR] 服务暂时不可用，请稍后重试\n\n"
            yield "data: [DONE]\n\n"
            return

        try:
            now = datetime.now(timezone.utc).isoformat()
            new_history = list(history) + [
                {"role": "user", "content": user_message, "createdAt": now},
                {"role": "assistant", "content": "".join(full_response), "createdAt": now},
            ]
            topic.research_data = new_history
            await db.commit()
        except Exception:
            yield "data: [ERROR] 对话内容保存失败\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
