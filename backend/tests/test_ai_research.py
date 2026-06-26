import pytest
from unittest.mock import AsyncMock, MagicMock


class StubAIProvider:
    engine_name = "stub"
    model_name = "stub-model"

    async def generate_script(self, *args, **kwargs):
        pass

    async def research_topic(
        self,
        topic_title,
        topic_description,
        conversation_history,
        new_message,
        use_default_prompt=False,
    ):
        chunks = ["## 核心理论\n\n", "这是一个测试回复。"]
        for chunk in chunks:
            yield chunk


@pytest.mark.asyncio
async def test_stub_research_topic_yields_chunks():
    provider = StubAIProvider()
    chunks = []
    async for chunk in provider.research_topic(
        topic_title="测试选题",
        topic_description="描述",
        conversation_history=[],
        new_message="介绍核心理论",
    ):
        chunks.append(chunk)
    assert len(chunks) == 2
    assert "核心理论" in chunks[0]


@pytest.mark.asyncio
async def test_stub_research_topic_default_prompt():
    provider = StubAIProvider()
    chunks = []
    async for chunk in provider.research_topic(
        topic_title="测试选题",
        topic_description="描述",
        conversation_history=[],
        new_message="",
        use_default_prompt=True,
    ):
        chunks.append(chunk)
    assert len(chunks) > 0
