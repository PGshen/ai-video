from typing import Optional
from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth import verify_api_key
from app.db import get_async_session
from app.models.topic import Topic
from app.schemas.topic import (
    TopicCreate, TopicUpdate, TopicResponse, TopicListResponse,
    BrainstormRequest, BrainstormResponse, ResearchMessageRequest,
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


DEFAULT_RESEARCH_SYSTEM_PROMPT = """\
你是一位知识视频选题研究助手。当前研究的选题是：

标题：{topic_title}
描述：{topic_description}

请围绕该选题提供背景资料，内容以 Markdown 格式输出，重点包括：核心概念、相关理论、反直觉角度、可视化潜力等。\
"""

DEFAULT_RESEARCH_QUESTION = "请介绍这个选题的背景知识和核心理论"


def get_ai_provider():
    """Returns the active AI provider. Replace with real implementation in Sprint 2."""

    class StubProvider:
        engine_name = "stub"
        model_name = "stub-model"

        async def generate_script(self, *args, **kwargs):
            from app.engines.ai.base import ScriptGenerationResult
            return ScriptGenerationResult(scenes=[], fact_checks=[])

        async def research_topic(
            self,
            topic_title: str,
            topic_description: str,
            conversation_history: list[dict],
            new_message: str,
            use_default_prompt: bool = False,
            system_prompt: str | None = None,
        ):
            import asyncio
            if use_default_prompt:
                chunks = [
                    f"## {topic_title} — 背景资料\n\n",
                    "**核心概念：** 这是一个由 AI Stub 生成的占位回复。\n\n",
                    "Sprint 2 接入真实 LLM 后将替换此内容。",
                ]
            else:
                chunks = [f"你问的是：{new_message}\n\n", "（Stub 回复，Sprint 2 替换）"]
            for chunk in chunks:
                await asyncio.sleep(0)
                yield chunk

    return StubProvider()


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
                yield f"data: {chunk}\n\n"

            now = datetime.now(timezone.utc).isoformat()
            new_history = list(history) + [
                {"role": "user", "content": user_message, "createdAt": now},
                {"role": "assistant", "content": "".join(full_response), "createdAt": now},
            ]
            topic.research_data = new_history
            await db.commit()
        except Exception as e:
            yield f"data: [ERROR] {e}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
