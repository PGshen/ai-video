import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.strategies.agent_codegen import AgentCancelledError, AgentCodegenStrategy

SCENES = [{"scene_index": 0, "narration": "旁白", "description": "描述", "beats": []}]


class FakeResultMessage:
    """替身，形状对齐 SDK 的 ResultMessage。"""

    def __init__(self, subtype="success", result="done", total_cost_usd=0.5):
        self.subtype = subtype
        self.result = result
        self.total_cost_usd = total_cost_usd


def make_agent_query(*, per_call_messages, on_call=None):
    """返回一个假的 agent_query；每次调用吐出 per_call_messages 里的下一批消息。"""
    calls = {"n": 0}

    async def fake_query(*, prompt, options):
        index = calls["n"]
        calls["n"] += 1
        if on_call:
            on_call(index, options)
        for message in per_call_messages[index]:
            yield message

    fake_query.calls = calls
    return fake_query


@pytest.mark.asyncio
async def test_agent_claiming_success_but_failing_validation_triggers_resume():
    """Agent 说自己成功了，但平台回读校验不过 —— 必须 resume 续跑一次。"""
    agent_query = make_agent_query(
        per_call_messages=[[FakeResultMessage()], [FakeResultMessage()]]
    )
    strategy = AgentCodegenStrategy(agent_query=agent_query)

    validate_results = [(False, "scene 0: NameError"), (True, "")]

    async def fake_validate(workdir, scenes, render_engine):
        return validate_results.pop(0)

    with patch(
        "app.services.strategies.agent_codegen.validate_workdir", fake_validate
    ), patch(
        "app.services.strategies.agent_codegen.read_scene_codes",
        return_value=["# code"],
    ), patch(
        "app.services.strategies.agent_codegen.build_validate_server",
        return_value=(MagicMock(), "mcp__codegen__validate"),
    ), patch(
        "app.services.strategies.agent_codegen.is_task_cancelled", return_value=False
    ), patch(
        "app.services.strategies.agent_codegen.record_agent_call", AsyncMock()
    ), patch(
        "app.services.strategies.agent_codegen._agent_env", return_value={}
    ):
        outcome = await strategy.run(
            scenes=SCENES,
            render_engine="manim",
            style_components={},
            aspect_ratio="landscape",
            rejection_context=None,
            previous_code_scenes=None,
            task_id="t1",
        )

    assert agent_query.calls["n"] == 2, "平台校验失败后必须 resume 续跑"
    assert outcome.scenes[0]["code"] == "# code"
    assert outcome.trace["resumed"] is True


@pytest.mark.asyncio
async def test_resume_is_attempted_at_most_once():
    """resume 后仍不过 —— 抛错，且不再续跑第三次。"""
    agent_query = make_agent_query(
        per_call_messages=[[FakeResultMessage()], [FakeResultMessage()]]
    )
    strategy = AgentCodegenStrategy(agent_query=agent_query)

    async def always_fail(workdir, scenes, render_engine):
        return False, "scene 0: SyntaxError"

    with patch(
        "app.services.strategies.agent_codegen.validate_workdir", always_fail
    ), patch(
        "app.services.strategies.agent_codegen.build_validate_server",
        return_value=(MagicMock(), "mcp__codegen__validate"),
    ), patch(
        "app.services.strategies.agent_codegen.is_task_cancelled", return_value=False
    ), patch(
        "app.services.strategies.agent_codegen.record_agent_call", AsyncMock()
    ), patch(
        "app.services.strategies.agent_codegen._agent_env", return_value={}
    ):
        with pytest.raises(ValueError, match="SyntaxError"):
            await strategy.run(
                scenes=SCENES,
                render_engine="manim",
                style_components={},
                aspect_ratio="landscape",
                rejection_context=None,
                previous_code_scenes=None,
                task_id="t1",
            )

    assert agent_query.calls["n"] == 2, "最多只能续跑一次"


@pytest.mark.asyncio
async def test_non_success_result_subtype_is_a_failure():
    agent_query = make_agent_query(
        per_call_messages=[
            [FakeResultMessage(subtype="error_max_turns")],
            [FakeResultMessage(subtype="error_max_turns")],
        ]
    )
    strategy = AgentCodegenStrategy(agent_query=agent_query)

    async def always_fail(workdir, scenes, render_engine):
        return False, "未完成"

    with patch(
        "app.services.strategies.agent_codegen.validate_workdir", always_fail
    ), patch(
        "app.services.strategies.agent_codegen.build_validate_server",
        return_value=(MagicMock(), "mcp__codegen__validate"),
    ), patch(
        "app.services.strategies.agent_codegen.is_task_cancelled", return_value=False
    ), patch(
        "app.services.strategies.agent_codegen.record_agent_call", AsyncMock()
    ), patch(
        "app.services.strategies.agent_codegen._agent_env", return_value={}
    ):
        with pytest.raises(ValueError):
            await strategy.run(
                scenes=SCENES,
                render_engine="manim",
                style_components={},
                aspect_ratio="landscape",
                rejection_context=None,
                previous_code_scenes=None,
                task_id="t1",
            )


@pytest.mark.asyncio
async def test_cancellation_mid_stream_aborts_and_cleans_up():
    captured_workdir = {}

    async def fake_query(*, prompt, options):
        captured_workdir["path"] = str(options.cwd)
        yield FakeResultMessage()

    strategy = AgentCodegenStrategy(agent_query=fake_query)

    with patch(
        "app.services.strategies.agent_codegen.build_validate_server",
        return_value=(MagicMock(), "mcp__codegen__validate"),
    ), patch(
        "app.services.strategies.agent_codegen.is_task_cancelled", return_value=True
    ), patch(
        "app.services.strategies.agent_codegen._agent_env", return_value={}
    ):
        with pytest.raises(AgentCancelledError):
            await strategy.run(
                scenes=SCENES,
                render_engine="manim",
                style_components={},
                aspect_ratio="landscape",
                rejection_context=None,
                previous_code_scenes=None,
                task_id="t1",
            )

    assert not os.path.exists(captured_workdir["path"]), "取消后必须清理沙箱"


@pytest.mark.asyncio
async def test_trace_records_cost_and_model():
    agent_query = make_agent_query(
        per_call_messages=[[FakeResultMessage(total_cost_usd=0.34)]]
    )
    strategy = AgentCodegenStrategy(agent_query=agent_query)

    async def ok(workdir, scenes, render_engine):
        return True, ""

    with patch(
        "app.services.strategies.agent_codegen.validate_workdir", ok
    ), patch(
        "app.services.strategies.agent_codegen.read_scene_codes",
        return_value=["# code"],
    ), patch(
        "app.services.strategies.agent_codegen.build_validate_server",
        return_value=(MagicMock(), "mcp__codegen__validate"),
    ), patch(
        "app.services.strategies.agent_codegen.is_task_cancelled", return_value=False
    ), patch(
        "app.services.strategies.agent_codegen.record_agent_call", AsyncMock()
    ), patch(
        "app.services.strategies.agent_codegen._agent_env", return_value={}
    ):
        outcome = await strategy.run(
            scenes=SCENES,
            render_engine="manim",
            style_components={},
            aspect_ratio="landscape",
            rejection_context=None,
            previous_code_scenes=None,
            task_id="t1",
        )

    assert outcome.trace["execution_mode"] == "agent"
    assert outcome.trace["total_cost_usd"] == 0.34
    assert outcome.trace["resumed"] is False
    assert outcome.ai_model


@pytest.mark.asyncio
async def test_options_use_tool_whitelist_and_budget_and_no_setting_sources():
    """硬安全要求：只给 Read/Write/Edit/Glob，且显式清空 setting_sources。"""
    seen = []
    first_message = FakeResultMessage()
    first_message.session_id = "sess-1"
    agent_query = make_agent_query(
        per_call_messages=[[first_message], [FakeResultMessage()]],
        on_call=lambda index, options: seen.append(options),
    )
    strategy = AgentCodegenStrategy(agent_query=agent_query)

    validate_results = [(False, "scene 0: NameError"), (True, "")]

    async def fake_validate(workdir, scenes, render_engine):
        return validate_results.pop(0)

    with patch(
        "app.services.strategies.agent_codegen.validate_workdir", fake_validate
    ), patch(
        "app.services.strategies.agent_codegen.read_scene_codes",
        return_value=["# code"],
    ), patch(
        "app.services.strategies.agent_codegen.build_validate_server",
        return_value=(MagicMock(), "mcp__codegen__validate"),
    ), patch(
        "app.services.strategies.agent_codegen.is_task_cancelled", return_value=False
    ), patch(
        "app.services.strategies.agent_codegen.record_agent_call", AsyncMock()
    ), patch(
        "app.services.strategies.agent_codegen._agent_env", return_value={}
    ):
        await strategy.run(
            scenes=SCENES,
            render_engine="manim",
            style_components={},
            aspect_ratio="landscape",
            rejection_context=None,
            previous_code_scenes=None,
            task_id="t1",
        )

    first, second = seen
    assert first.tools == ["Read", "Write", "Edit", "Glob"]
    assert "Bash" not in (first.allowed_tools or [])
    assert first.setting_sources == []
    assert first.max_budget_usd
    assert not first.resume
    # resume 续跑必须带上上一轮的 session_id
    assert second.resume == "sess-1"
