import json
from unittest.mock import AsyncMock

import httpx
import pytest

from app.engines.ai.chat_provider import ChatAIProvider, normalize_exemplar_prompt
from app.engines.ai.anthropic import AnthropicClient
from app.engines.ai.gemini import GeminiClient
from app.engines.ai.openrouter import OpenRouterClient
from app.engines.ai.structured_output import (
    CODE_GENERATION_SCHEMA,
    EXEMPLAR_PROMPT_SCHEMA,
    NARRATIVE_SCHEMA,
    response_format_for,
)
from app.engines.ai.stub import StubChatClient


def stream_response(content: str) -> httpx.Response:
    body = "\n\n".join(
        [
            "data: "
            + json.dumps({"choices": [{"delta": {"content": content}}]}),
            "data: [DONE]",
        ]
    )
    return httpx.Response(200, content=body)


def test_response_format_uses_strict_json_schema_for_capable_clients():
    response_format = response_format_for(
        StubChatClient(),
        name="narrative",
        schema=NARRATIVE_SCHEMA,
    )

    assert response_format == {
        "type": "json_schema",
        "json_schema": {
            "name": "narrative",
            "strict": True,
            "schema": NARRATIVE_SCHEMA,
        },
    }


def test_anthropic_is_a_native_schema_capable_provider():
    client = AnthropicClient(api_key="test", model="claude-sonnet-4-6")

    assert response_format_for(
        client,
        name="result",
        schema={"type": "object"},
    )["type"] == "json_schema"


def test_response_format_falls_back_to_json_object_for_unsupported_clients():
    class JsonOnlyClient:
        supports_json_schema = False

    assert response_format_for(
        JsonOnlyClient(),  # type: ignore[arg-type]
        name="result",
        schema={"type": "object"},
    ) == {"type": "json_object"}


@pytest.mark.asyncio
async def test_chat_provider_sends_operation_specific_schema():
    client = StubChatClient()
    client.create_chat_completion = AsyncMock(
        return_value=json.dumps({"codes": ["first", "second"]})
    )

    await ChatAIProvider(client).generate_code(
        scenes=[{"scene_index": 0}, {"scene_index": 1}],
        render_engine="manim",
    )

    response_format = client.create_chat_completion.await_args.kwargs["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True
    assert response_format["json_schema"]["schema"] == CODE_GENERATION_SCHEMA


@pytest.mark.asyncio
async def test_gemini_forwards_openai_compatible_json_schema():
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["stream"] is True
        assert payload["stream_options"] == {"include_usage": True}
        assert payload["response_format"]["type"] == "json_schema"
        assert payload["response_format"]["json_schema"]["strict"] is True
        return stream_response('{"codes":["ok"]}')

    client = GeminiClient(
        api_key="test-key",
        model="gemini-2.5-flash",
        transport=httpx.MockTransport(handler),
    )
    await client.create_chat_completion(
        messages=[{"role": "user", "content": "JSON"}],
        response_format=response_format_for(
            client,
            name="code_generation",
            schema=CODE_GENERATION_SCHEMA,
        ),
    )


@pytest.mark.asyncio
async def test_openrouter_requires_schema_capable_upstream_provider():
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["stream"] is True
        assert payload["stream_options"] == {"include_usage": True}
        assert payload["response_format"]["type"] == "json_schema"
        assert payload["provider"] == {"require_parameters": True}
        return stream_response('{"codes":["ok"]}')

    client = OpenRouterClient(
        api_key="test-key",
        model="openrouter/auto",
        transport=httpx.MockTransport(handler),
    )
    await client.create_chat_completion(
        messages=[{"role": "user", "content": "JSON"}],
        response_format=response_format_for(
            client,
            name="code_generation",
            schema=CODE_GENERATION_SCHEMA,
        ),
    )


@pytest.mark.asyncio
async def test_brainstorm_rejects_invalid_candidate_even_in_json_only_mode():
    class InvalidJsonOnlyClient:
        engine_name = "json-only"
        model_name = "json-only-model"
        supports_json_schema = False

        async def create_chat_completion(self, **kwargs):
            assert kwargs["response_format"] == {"type": "json_object"}
            return '{"candidates":[{"title":"缺少字段"}]}'

    with pytest.raises(ValueError, match="Invalid brainstorm candidate"):
        await ChatAIProvider(InvalidJsonOnlyClient()).brainstorm_topics("科学", 1)


@pytest.mark.asyncio
async def test_style_assistant_tolerates_optional_fields_missing_in_json_mode():
    class PartialJsonClient:
        engine_name = "deepseek"
        model_name = "json-only-model"
        supports_json_schema = False

        async def create_chat_completion(self, **kwargs):
            assert kwargs["response_format"] == {"type": "json_object"}
            return '{"name":"科技蓝","prompt_text":"只使用蓝色系和充足留白。"}'

    result = await ChatAIProvider(PartialJsonClient()).assist_style_prompt(
        category="color_scheme",
        name="",
        description="原说明",
        prompt_text="",
        conversation_history=[],
        new_message="简洁科技感",
    )

    assert result.name == "科技蓝"
    assert result.description == "原说明"
    assert result.prompt_text == "只使用蓝色系和充足留白。"
    assert "更新了左侧提示词" in result.reply


@pytest.mark.asyncio
async def test_style_library_assistant_parses_all_four_components():
    categories = (
        "narrative_style",
        "color_scheme",
        "animation_style",
        "exemplar",
    )

    class LibraryJsonClient:
        engine_name = "deepseek"
        model_name = "schema-model"
        supports_json_schema = True

        async def create_chat_completion(self, **kwargs):
            response_format = kwargs["response_format"]
            exemplar_schema = response_format["json_schema"]["schema"][
                "properties"
            ]["components"]["properties"]["exemplar"]["properties"]["prompt_text"]
            assert exemplar_schema == EXEMPLAR_PROMPT_SCHEMA
            assert exemplar_schema["properties"]["scenes"]["maxItems"] == 2
            system_prompt = kwargs["messages"][0]["content"]
            assert "金样本强制格式" in system_prompt
            assert "video_title" in system_prompt
            assert "责任几乎全部落在你身上" in system_prompt
            return json.dumps(
                {
                    "reply": "已生成四个组件。",
                    "name": "冷静科技",
                    "description": "适合严谨知识解释",
                    "components": {
                        category: {
                            "name": f"科技 · {category}",
                            "description": f"{category} rules",
                            "prompt_text": (
                                {
                                    "scenes": [
                                        {
                                            "scene_index": 0,
                                            "narration": "测试旁白。",
                                            "description": "测试画面。",
                                            "estimated_duration_seconds": 5,
                                            "beats": [
                                                {
                                                    "beat_index": 0,
                                                    "cue_text": "测试旁白。",
                                                    "visual_action": "绘制测试画面。",
                                                    "emphasis": None,
                                                    "transition": "reveal",
                                                    "fallback_weight": 1,
                                                }
                                            ],
                                        }
                                    ],
                                    "fact_checks": [],
                                }
                                if category == "exemplar"
                                else f"Prompt for {category}"
                            ),
                        }
                        for category in categories
                    },
                },
                ensure_ascii=False,
            )

    result = await ChatAIProvider(LibraryJsonClient()).assist_style_library(
        name="",
        description="",
        components={},
        conversation_history=[],
        new_message="生成冷静科技风格",
    )

    assert result.name == "冷静科技"
    assert set(result.components) == set(categories)
    exemplar = json.loads(result.components["exemplar"]["prompt_text"])
    assert set(exemplar) == {"scenes", "fact_checks"}
    assert exemplar["scenes"][0]["scene_index"] == 0


@pytest.mark.asyncio
async def test_single_exemplar_assistant_uses_canonical_narrative_schema():
    class ExemplarSchemaClient:
        engine_name = "deepseek"
        model_name = "schema-model"
        supports_json_schema = True

        async def create_chat_completion(self, **kwargs):
            response_format = kwargs["response_format"]
            assert (
                response_format["json_schema"]["schema"]["properties"]["prompt_text"]
                == EXEMPLAR_PROMPT_SCHEMA
            )
            system_prompt = kwargs["messages"][0]["content"]
            assert "顶层只能包含 scenes 和 fact_checks" in system_prompt
            assert "1-2 个代表镜头" in system_prompt
            assert "shots" in system_prompt
            assert "责任几乎全部落在你身上" in system_prompt
            return json.dumps(
                {
                    "reply": "已按标准 Schema 生成金样本。",
                    "name": "标准金样本",
                    "description": "标准镜头结构",
                    "prompt_text": {
                        "scenes": [
                            {
                                "scene_index": 0,
                                "narration": "测试旁白。",
                                "description": "测试画面。",
                                "estimated_duration_seconds": 5,
                                "beats": [
                                    {
                                        "beat_index": 0,
                                        "cue_text": "测试旁白。",
                                        "visual_action": "绘制测试画面。",
                                        "emphasis": None,
                                        "transition": "reveal",
                                        "fallback_weight": 1,
                                    }
                                ],
                            }
                        ],
                        "fact_checks": [],
                    },
                },
                ensure_ascii=False,
            )

    result = await ChatAIProvider(ExemplarSchemaClient()).assist_style_prompt(
        category="exemplar",
        name="",
        description="",
        prompt_text="",
        conversation_history=[],
        new_message="生成一个标准金样本",
    )

    exemplar = json.loads(result.prompt_text)
    assert set(exemplar) == {"scenes", "fact_checks"}
    assert set(exemplar["scenes"][0]) == {
        "scene_index",
        "narration",
        "description",
        "estimated_duration_seconds",
        "beats",
    }


@pytest.mark.asyncio
async def test_exemplar_assistant_rejects_invented_shots_schema():
    class InvalidExemplarClient:
        engine_name = "deepseek"
        model_name = "json-only-model"
        supports_json_schema = False

        async def create_chat_completion(self, **kwargs):
            return json.dumps(
                {
                    "reply": "生成完成。",
                    "name": "错误金样本",
                    "description": "错误结构",
                    "prompt_text": json.dumps(
                        {
                            "video_title": "模型自创标题",
                            "shots": [{"id": 1, "phase": "开场"}],
                        },
                        ensure_ascii=False,
                    ),
                },
                ensure_ascii=False,
            )

    with pytest.raises(ValueError, match="exemplar.*missing fields"):
        await ChatAIProvider(InvalidExemplarClient()).assist_style_prompt(
            category="exemplar",
            name="",
            description="",
            prompt_text="",
            conversation_history=[],
            new_message="生成金样本",
        )


def _minimal_exemplar_scene(scene_index: int) -> dict:
    return {
        "scene_index": scene_index,
        "narration": "测试旁白。",
        "description": "测试画面。",
        "estimated_duration_seconds": 5,
        "beats": [
            {
                "beat_index": 0,
                "cue_text": "测试旁白。",
                "visual_action": "绘制测试画面。",
                "emphasis": None,
                "transition": "reveal",
                "fallback_weight": 1,
            }
        ],
    }


def test_exemplar_assistant_rejects_full_video_instead_of_style_sample():
    with pytest.raises(ValueError, match="at most 2 items"):
        normalize_exemplar_prompt(
            {
                "scenes": [
                    _minimal_exemplar_scene(scene_index)
                    for scene_index in range(3)
                ],
                "fact_checks": [],
            }
        )


@pytest.mark.asyncio
async def test_style_assistant_rejects_prompt_over_component_limit():
    class OversizedPromptClient:
        engine_name = "deepseek"
        model_name = "json-only-model"
        supports_json_schema = False

        async def create_chat_completion(self, **kwargs):
            return json.dumps(
                {
                    "reply": "生成完成。",
                    "name": "超长视觉系统",
                    "description": "错误长度",
                    "prompt_text": "x" * 8001,
                }
            )

    with pytest.raises(ValueError, match="exceeds 8000"):
        await ChatAIProvider(OversizedPromptClient()).assist_style_prompt(
            category="color_scheme",
            name="",
            description="",
            prompt_text="",
            conversation_history=[],
            new_message="生成视觉系统",
        )
