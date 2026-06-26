import json
import re
from collections.abc import AsyncIterator

from app.engines.ai.base import BrainstormResult, ChatClient, ScriptGenerationResult


class ChatAIProvider:
    def __init__(
        self,
        client: ChatClient,
        script_max_tokens: int = 8192,
        json_max_tokens: int = 4096,
    ):
        self.client = client
        self.script_max_tokens = script_max_tokens
        self.json_max_tokens = json_max_tokens

    @property
    def engine_name(self) -> str:
        return self.client.engine_name

    @property
    def model_name(self) -> str:
        return self.client.model_name

    async def generate_script(
        self,
        topic_title: str,
        topic_description: str,
        render_engine: str,
        rejection_context: dict | None = None,
    ) -> ScriptGenerationResult:
        system_prompt = """\
你是知识视频脚本生成器。请严格输出 JSON object，不要输出 Markdown。

JSON 格式示例：
{
  "scenes": [
    {
      "scene_index": 0,
      "narration": "旁白文稿",
      "description": "画面描述",
      "code": "渲染代码，必要时使用 {{AUDIO_SCENE_0}} 音频占位符",
      "estimated_duration_seconds": 12.5
    }
  ],
  "fact_checks": [
    {
      "claim_text": "需要核查的具体论断",
      "scene_index": 0,
      "source_url": null,
      "source_description": "建议核查来源或说明",
      "confidence": "medium",
      "is_hypothesis": false,
      "assumptions": null,
      "controversy": null,
      "reviewer_verdict": null,
      "reviewer_note": null
    }
  ]
}

要求：
- scenes 是镜头数组，scene_index 从 0 连续递增。
- 每个镜头包含 narration、description、code、estimated_duration_seconds。
- code 应匹配指定渲染引擎，并预留 {{AUDIO_SCENE_N}} 音频占位符。
- fact_checks 覆盖脚本中的关键事实论断和可能争议点。
- 只能输出合法 JSON object。\
"""
        user_payload = {
            "topic_title": topic_title,
            "topic_description": topic_description,
            "render_engine": render_engine,
            "rejection_context": rejection_context,
        }
        content = await self.client.create_chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": "请为以下选题生成知识视频脚本 JSON：\n"
                    + json.dumps(user_payload, ensure_ascii=False),
                },
            ],
            response_format={"type": "json_object"},
            max_tokens=self.script_max_tokens,
        )
        payload = parse_json_object(content)
        scenes = payload.get("scenes")
        fact_checks = payload.get("fact_checks")
        if not isinstance(scenes, list) or not isinstance(fact_checks, list):
            raise ValueError("Script response must contain scenes and fact_checks arrays")
        return ScriptGenerationResult(scenes=scenes, fact_checks=fact_checks)

    async def brainstorm_topics(self, topic_direction: str, count: int) -> BrainstormResult:
        system_prompt = """\
你是知识视频选题策划助手。请严格输出 JSON object，不要输出 Markdown。

JSON 格式示例：
{
  "candidates": [
    {
      "title": "一个反直觉、可论证、适合动画化的选题标题",
      "description": "一句话说明选题切入角度和知识价值",
      "tags": ["物理", "认知"]
    }
  ]
}

要求：
- candidates 数量必须匹配用户要求。
- title 适合自媒体知识视频标题，避免空泛。
- description 说明反直觉点、可论证点或可视化潜力。
- tags 使用 2 到 5 个中文短标签。
- 只能输出合法 JSON object。\
"""
        user_prompt = f"请围绕「{topic_direction}」生成 {count} 个候选选题 JSON。"
        content = await self.client.create_chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            max_tokens=self.json_max_tokens,
        )
        payload = parse_json_object(content)
        candidates = payload.get("candidates")
        if not isinstance(candidates, list):
            raise ValueError("Brainstorm response must contain candidates array")
        return BrainstormResult(candidates=candidates[:count])

    async def research_topic(
        self,
        topic_title: str,
        topic_description: str,
        conversation_history: list[dict],
        new_message: str,
        use_default_prompt: bool = False,
        system_prompt: str | None = None,
    ) -> AsyncIterator[str]:
        if system_prompt is None:
            system_prompt = (
                "你是一位知识视频选题研究助手。请基于事实、理论背景和可视化潜力回答，"
                "输出 Markdown。"
            )

        messages = [{"role": "system", "content": system_prompt}]
        for item in conversation_history:
            role = item.get("role")
            content = item.get("content")
            if role in {"user", "assistant"} and isinstance(content, str):
                messages.append({"role": role, "content": content})
        messages.append(
            {
                "role": "user",
                "content": (
                    f"当前选题：{topic_title}\n"
                    f"选题描述：{topic_description or '无'}\n\n"
                    f"问题：{new_message}"
                ),
            }
        )

        async for chunk in self.client.stream_chat_completion(messages):
            yield chunk


def parse_json_object(content: str) -> dict:
    text = content.strip()
    fence_match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("AI response is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("AI JSON response must be an object")
    return payload
