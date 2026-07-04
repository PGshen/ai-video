import asyncio
import json

from app.engines.ai.base import (
    BrainstormResult, CodeGenerationResult, CodeRepairResult,
    NarrativeResult,
)


class StubProvider:
    engine_name = "stub"
    model_name = "stub-model"
    
    async def generate_narrative(
        self,
        topic_title: str,
        topic_description: str,
        render_engine: str,
        rejection_context: dict | None = None,
        narrative_context: list[dict] | None = None,
        style_components: dict[str, str] | None = None,
        aspect_ratio: str = "landscape",
    ) -> NarrativeResult:
        await asyncio.sleep(0)
        return NarrativeResult(scenes=[], fact_checks=[])

    async def generate_code(
        self,
        scenes: list[dict],
        render_engine: str,
        style_components: dict[str, str] | None = None,
        aspect_ratio: str = "landscape",
    ) -> CodeGenerationResult:
        await asyncio.sleep(0)
        return CodeGenerationResult(codes=["" for _ in scenes])

    async def repair_code(
        self,
        scenes: list[dict],
        render_engine: str,
        error_message: str,
        style_components: dict[str, str] | None = None,
        aspect_ratio: str = "landscape",
    ) -> CodeRepairResult:
        await asyncio.sleep(0)
        return CodeRepairResult(repairs=[])

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

    supports_json_schema = True

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
        """Return a schema-valid stub response for provider tests."""
        await asyncio.sleep(0)
        narrative_response = {
            "scenes": [
                {
                    "scene_index": 0,
                    "narration": "测试旁白。",
                    "description": "显示测试标题。",
                    "estimated_duration_seconds": 3.0,
                    "beats": [
                        {
                            "beat_index": 0,
                            "cue_text": "测试旁白。",
                            "visual_action": "测试标题出现。",
                            "transition": "reveal",
                            "fallback_weight": 1.0,
                        }
                    ],
                }
            ],
            "fact_checks": [],
        }
        user_content = messages[-1].get("content", "") if messages else ""
        if "生成渲染代码 JSON" in user_content:
            try:
                request_payload = json.loads(user_content.split("\n", 1)[1])
                scene_count = len(request_payload.get("scenes") or [])
            except (json.JSONDecodeError, IndexError, AttributeError):
                scene_count = 0
            return json.dumps(
                {"codes": ["# stub generated code" for _ in range(scene_count)]},
                ensure_ascii=False,
            )
        return json.dumps(narrative_response, ensure_ascii=False)

    async def stream_chat_completion(
        self,
        messages: list[dict],
    ):
        """Stub streaming - yields empty chunks."""
        await asyncio.sleep(0)
        yield ""
