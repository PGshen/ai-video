import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import settings
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
        "app.services.strategies.agent_codegen._agent_env_and_model",
        return_value=({}, "claude-opus-5"),
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
        "app.services.strategies.agent_codegen._agent_env_and_model",
        return_value=({}, "claude-opus-5"),
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
    """校验能过、但 Agent 以 error_max_turns 收尾 —— 仍必须判失败。"""
    agent_query = make_agent_query(
        per_call_messages=[
            [FakeResultMessage(subtype="error_max_turns")],
            [FakeResultMessage(subtype="error_max_turns")],
        ]
    )
    strategy = AgentCodegenStrategy(agent_query=agent_query)

    async def always_ok(workdir, scenes, render_engine):
        return True, ""

    with patch(
        "app.services.strategies.agent_codegen.validate_workdir", always_ok
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
        "app.services.strategies.agent_codegen._agent_env_and_model",
        return_value=({}, "claude-opus-5"),
    ):
        with pytest.raises(ValueError, match="error_max_turns"):
            await strategy.run(
                scenes=SCENES,
                render_engine="manim",
                style_components={},
                aspect_ratio="landscape",
                rejection_context=None,
                previous_code_scenes=None,
                task_id="t1",
            )

    assert agent_query.calls["n"] == 2


@pytest.mark.asyncio
async def test_missing_result_message_is_a_failure():
    """完全没有 ResultMessage（只有 SystemMessage）也不能算成功。"""

    class FakeSystemMessage:
        subtype = "init"  # 带 subtype 但不是 ResultMessage

    agent_query = make_agent_query(
        per_call_messages=[[FakeSystemMessage()], [FakeSystemMessage()]]
    )
    strategy = AgentCodegenStrategy(agent_query=agent_query)

    async def always_ok(workdir, scenes, render_engine):
        return True, ""

    with patch(
        "app.services.strategies.agent_codegen.validate_workdir", always_ok
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
        "app.services.strategies.agent_codegen._agent_env_and_model",
        return_value=({}, "claude-opus-5"),
    ):
        with pytest.raises(ValueError, match="result subtype"):
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
        "app.services.strategies.agent_codegen._agent_env_and_model",
        return_value=({}, "claude-opus-5"),
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
        "app.services.strategies.agent_codegen._agent_env_and_model",
        return_value=({}, "claude-opus-5"),
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
    assert outcome.ai_model == "claude-opus-5"


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
        "app.services.strategies.agent_codegen._agent_env_and_model",
        return_value=({}, "claude-opus-5"),
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
    assert "mcp__codegen__validate" in first.allowed_tools
    assert first.setting_sources == []
    assert first.max_budget_usd
    assert not first.resume
    # resume 续跑必须带上上一轮的 session_id
    assert second.resume == "sess-1"


@pytest.mark.asyncio
async def test_cancellation_records_a_cancelled_ai_call():
    async def fake_query(*, prompt, options):
        yield FakeResultMessage()

    strategy = AgentCodegenStrategy(agent_query=fake_query)
    recorder = AsyncMock()

    with patch(
        "app.services.strategies.agent_codegen.build_validate_server",
        return_value=(MagicMock(), "mcp__codegen__validate"),
    ), patch(
        "app.services.strategies.agent_codegen.is_task_cancelled", return_value=True
    ), patch(
        "app.services.strategies.agent_codegen.record_agent_call", recorder
    ), patch(
        "app.services.strategies.agent_codegen._agent_env_and_model",
        return_value=({}, "claude-opus-5"),
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

    assert recorder.await_args.kwargs["status"] == "cancelled"


@pytest.mark.asyncio
async def test_wall_clock_timeout_aborts_the_run():
    """CLI 子进程卡死时，AGENT_TIMEOUT_SECONDS 必须兜底。"""
    import asyncio

    async def hanging_query(*, prompt, options):
        await asyncio.sleep(10)
        yield FakeResultMessage()

    strategy = AgentCodegenStrategy(agent_query=hanging_query)

    with patch(
        "app.services.strategies.agent_codegen.build_validate_server",
        return_value=(MagicMock(), "mcp__codegen__validate"),
    ), patch(
        "app.services.strategies.agent_codegen.is_task_cancelled", return_value=False
    ), patch(
        "app.services.strategies.agent_codegen.record_agent_call", AsyncMock()
    ), patch(
        "app.services.strategies.agent_codegen._agent_env_and_model",
        return_value=({}, "claude-opus-5"),
    ), patch.object(
        settings, "AGENT_TIMEOUT_SECONDS", 0.05
    ):
        with pytest.raises(ValueError, match="超时"):
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
async def test_resume_cost_is_not_double_counted():
    """SDK 的 total_cost_usd 是会话累计值，resume 轮不得再加一遍。"""
    first = FakeResultMessage(total_cost_usd=0.4)
    first.session_id = "sess-1"
    agent_query = make_agent_query(
        per_call_messages=[[first], [FakeResultMessage(total_cost_usd=0.9)]]
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
        "app.services.strategies.agent_codegen._agent_env_and_model",
        return_value=({}, "claude-opus-5"),
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

    assert outcome.trace["total_cost_usd"] == 0.9


def test_agent_env_and_model_uses_provider_config():
    """SDK 自身做 {**os.environ, **options.env} 合并（subprocess_cli.py:809-813），
    因此这里除了 Anthropic 凭证，还必须把宿主机上会改变路由的变量显式置空；
    模型优先取 provider 配置里的模型行。"""
    from app.services.strategies.agent_codegen import _agent_env_and_model

    config = MagicMock()
    config.provider_type = "anthropic"
    config.api_key = "sk-test"
    config.base_url = "https://example.invalid"
    config.model = "claude-sonnet-9"
    with patch(
        "app.engines.ai.factory._provider_settings_from_db", return_value=config
    ):
        env, model = _agent_env_and_model()
    assert env["ANTHROPIC_API_KEY"] == "sk-test"
    assert env["ANTHROPIC_BASE_URL"] == "https://example.invalid"
    # 宿主机若设了 Bedrock/Vertex 路由，其优先级压过 ANTHROPIC_BASE_URL，
    # 会让平台配置的网关被静默忽略——必须逐个中和
    for name in ("CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX",
                 "ANTHROPIC_AUTH_TOKEN", "AWS_BEARER_TOKEN_BEDROCK"):
        assert env[name] == "", f"{name} 未被中和，宿主环境会渗进 Agent 会话"
    assert model == "claude-sonnet-9"


def test_agent_env_and_model_falls_back_to_settings_model():
    from app.services.strategies.agent_codegen import _agent_env_and_model

    config = MagicMock()
    config.provider_type = "anthropic"
    config.api_key = "sk-test"
    config.base_url = ""
    config.model = ""
    with patch(
        "app.engines.ai.factory._provider_settings_from_db", return_value=config
    ):
        env, model = _agent_env_and_model()
    assert env["ANTHROPIC_API_KEY"] == "sk-test"
    # base_url 留空表示走官方端点，仍须显式置空以盖掉宿主机的同名变量
    assert env["ANTHROPIC_BASE_URL"] == ""
    assert env["CLAUDE_CODE_USE_BEDROCK"] == ""
    assert model == settings.AGENT_MODEL


@pytest.mark.parametrize("config", [None, "non_anthropic"])
def test_agent_mode_requires_anthropic_provider(config):
    """没有 anthropic provider 时必须立刻失败，绝不能靠宿主残留的 key 静默跑。"""
    from app.services.strategies.agent_codegen import _agent_env_and_model

    resolved = None
    if config == "non_anthropic":
        resolved = MagicMock()
        resolved.provider_type = "openai"
    with patch(
        "app.engines.ai.factory._provider_settings_from_db", return_value=resolved
    ):
        with pytest.raises(ValueError, match="anthropic provider"):
            _agent_env_and_model()


@pytest.mark.asyncio
async def test_non_manim_render_engine_is_rejected_before_any_agent_call():
    """Agent 模式暂只支持 manim；Remotion 项目必须立刻失败，不烧预算。"""
    agent_query = make_agent_query(per_call_messages=[[FakeResultMessage()]])
    strategy = AgentCodegenStrategy(agent_query=agent_query)

    with pytest.raises(ValueError, match="manim"):
        await strategy.run(
            scenes=SCENES,
            render_engine="remotion",
            style_components={},
            aspect_ratio="landscape",
            rejection_context=None,
            previous_code_scenes=None,
            task_id="t1",
        )

    assert agent_query.calls["n"] == 0


@pytest.mark.asyncio
async def test_result_subtype_is_reset_between_runs():
    """首轮 success、resume 轮 error_max_turns —— 不得沿用首轮的 subtype 判成功。"""
    agent_query = make_agent_query(
        per_call_messages=[
            [FakeResultMessage(subtype="success")],
            [FakeResultMessage(subtype="error_max_turns")],
        ]
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
        "app.services.strategies.agent_codegen._agent_env_and_model",
        return_value=({}, "claude-opus-5"),
    ):
        with pytest.raises(ValueError, match="error_max_turns"):
            await strategy.run(
                scenes=SCENES,
                render_engine="manim",
                style_components={},
                aspect_ratio="landscape",
                rejection_context=None,
                previous_code_scenes=None,
                task_id="t1",
            )


def test_thinking_config_respects_settings():
    """思考预算可配；display 必须是 summarized，否则日志里看不到思考内容。"""
    from app.services.strategies.agent_codegen import _thinking_config

    with patch.object(settings, "AGENT_THINKING_MODE", "enabled"), patch.object(
        settings, "AGENT_THINKING_BUDGET_TOKENS", 4000
    ):
        assert _thinking_config() == {
            "type": "enabled",
            "budget_tokens": 4000,
            "display": "summarized",
        }

    with patch.object(settings, "AGENT_THINKING_MODE", "disabled"):
        assert _thinking_config() == {"type": "disabled"}

    with patch.object(settings, "AGENT_THINKING_MODE", "adaptive"):
        assert _thinking_config() == {"type": "adaptive", "display": "summarized"}


@pytest.mark.asyncio
async def test_prompt_states_absolute_workdir():
    """提示词必须给出工作目录绝对路径。

    只写相对文件名时，模型会凭空猜一个路径（实测猜成了
    /home/jun/repos/...），白白浪费开头两轮工具调用去读不存在的文件。
    """
    captured = {}

    async def fake_query(*, prompt, options):
        captured["prompt"] = prompt
        captured["cwd"] = str(options.cwd)
        yield FakeResultMessage()

    strategy = AgentCodegenStrategy(agent_query=fake_query)

    async def always_ok(workdir, scenes, render_engine):
        return True, ""

    with patch(
        "app.services.strategies.agent_codegen.validate_workdir", always_ok
    ), patch(
        "app.services.strategies.agent_codegen.read_scene_codes", return_value=["# code"]
    ), patch(
        "app.services.strategies.agent_codegen.build_validate_server",
        return_value=(MagicMock(), "mcp__codegen__validate"),
    ), patch(
        "app.services.strategies.agent_codegen.is_task_cancelled", return_value=False
    ), patch(
        "app.services.strategies.agent_codegen.record_agent_call", AsyncMock()
    ), patch(
        "app.services.strategies.agent_codegen._agent_env_and_model",
        return_value=({}, "claude-opus-5"),
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

    assert captured["cwd"] in captured["prompt"], "提示词里必须写明工作目录绝对路径"
    assert "{workdir}" not in captured["prompt"], "模板占位符未被替换"
