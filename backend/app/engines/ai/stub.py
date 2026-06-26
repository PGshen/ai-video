import asyncio
import json

from app.engines.ai.base import BrainstormResult, ScriptGenerationResult, ChatClient


class StubProvider:
    engine_name = "stub"
    model_name = "stub-model"

    async def generate_script(self, *args, **kwargs) -> ScriptGenerationResult:
        return ScriptGenerationResult(scenes=[], fact_checks=[])

    async def brainstorm_topics(self, topic_direction: str, count: int) -> BrainstormResult:
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
        await asyncio.sleep(0)
        return BrainstormResult(candidates=candidates[:count])

    async def research_topic(
        self,
        topic_title: str,
        topic_description: str,
        conversation_history: list[dict],
        new_message: str,
        use_default_prompt: bool = False,
        system_prompt: str | None = None,
    ):
        if use_default_prompt:
            chunks = [
                f"## {topic_title} - 背景资料\n\n",
                "**核心概念：** 这是一个由 AI Stub 生成的占位回复。\n\n",
                "Sprint 2 接入真实 LLM 后将替换此内容。",
            ]
        else:
            chunks = [f"你问的是：{new_message}\n\n", "（Stub 回复，Sprint 2 替换）"]
        for chunk in chunks:
            await asyncio.sleep(0)
            yield chunk


class StubChatClient:
    """Stub implementation of ChatClient protocol for testing."""

    @property
    def engine_name(self) -> str:
        return "stub"

    @property
    def model_name(self) -> str:
        return "stub-model"

    async def create_chat_completion(
        self,
        messages: list[dict],
        response_format: dict | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Return a stub JSON response with empty scenes and fact_checks."""
        await asyncio.sleep(0)
        response = {
            "scenes": [],
            "fact_checks": [],
        }
        return json.dumps(response, ensure_ascii=False)

    async def stream_chat_completion(
        self,
        messages: list[dict],
    ):
        """Stub streaming - yields empty chunks."""
        await asyncio.sleep(0)
        yield ""
