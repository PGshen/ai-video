import json

import httpx
import pytest

from app.engines.ai.chat_provider import ChatAIProvider
from app.engines.ai.deepseek import DeepSeekClient


def make_client(handler) -> DeepSeekClient:
    return DeepSeekClient(
        api_key="test-key",
        model="deepseek-v4-flash",
        transport=httpx.MockTransport(handler),
    )


@pytest.mark.asyncio
async def test_deepseek_client_uses_official_chat_completion_shape_and_auth_header():
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.url.path == "/chat/completions"
        assert request.headers["authorization"] == "Bearer test-key"
        assert payload["model"] == "deepseek-v4-flash"
        assert payload["response_format"] == {"type": "json_object"}
        assert payload["max_tokens"] == 123
        assert payload["stream"] is False
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"ok": true}'}}]})

    content = await make_client(handler).create_chat_completion(
        messages=[{"role": "user", "content": "hello"}],
        response_format={"type": "json_object"},
        max_tokens=123,
    )

    assert content == '{"ok": true}'


@pytest.mark.asyncio
async def test_chat_ai_provider_brainstorm_uses_json_mode_and_parses_candidates():
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["response_format"] == {"type": "json_object"}
        assert "选题策划助手" in payload["messages"][0]["content"]
        assert "候选选题" in payload["messages"][1]["content"]
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "candidates": [
                                        {
                                            "title": "为什么冰会浮在水上",
                                            "description": "密度反常的可视化解释",
                                            "tags": ["物理", "化学"],
                                        }
                                    ]
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            },
        )

    result = await ChatAIProvider(make_client(handler)).brainstorm_topics("科学", 1)

    assert result.candidates[0]["title"] == "为什么冰会浮在水上"


@pytest.mark.asyncio
async def test_chat_ai_provider_generate_script_parses_json_object():
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert "知识视频脚本生成器" in payload["messages"][0]["content"]
        script_payload = {
            "scenes": [
                {
                    "scene_index": 0,
                    "narration": "旁白",
                    "description": "画面",
                    "code": "self.add_sound('{{AUDIO_SCENE_0}}')",
                    "estimated_duration_seconds": 3,
                }
            ],
            "fact_checks": [
                {
                    "claim_text": "事实",
                    "scene_index": 0,
                    "source_url": None,
                    "source_description": "来源",
                    "confidence": "high",
                    "is_hypothesis": False,
                    "assumptions": None,
                    "controversy": None,
                    "reviewer_verdict": None,
                    "reviewer_note": None,
                }
            ],
        }
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(script_payload, ensure_ascii=False)}}]},
        )

    result = await ChatAIProvider(make_client(handler)).generate_script(
        topic_title="测试",
        topic_description="描述",
        render_engine="manim",
    )

    assert len(result.scenes) == 1
    assert len(result.fact_checks) == 1


@pytest.mark.asyncio
async def test_deepseek_client_stream_yields_delta_content():
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["stream"] is True
        body = "\n\n".join(
            [
                'data: {"choices":[{"delta":{"content":"第一段"},"index":0}]}',
                'data: {"choices":[{"delta":{"content":"第二段"},"index":0}]}',
                "data: [DONE]",
            ]
        )
        return httpx.Response(200, content=body)

    chunks = []
    async for chunk in make_client(handler).stream_chat_completion(
        messages=[{"role": "user", "content": "介绍背景"}],
    ):
        chunks.append(chunk)

    assert chunks == ["第一段", "第二段"]
