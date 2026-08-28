from __future__ import annotations

import json
import logging
import os
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Callable, Literal

from app.config import settings
from app.engines.ai.base import normalize_usage
from app.engines.ai.factory import ProviderSettings
from app.services.strategies.agent_runtime import AgentCancelledError, AgentRunResult
from app.services.strategies.agent_sandbox import scene_filename, validate_workdir

logger = logging.getLogger(__name__)

MAX_CONTEXT_FILE_BYTES = 2_000_000
MAX_SCENE_FILE_BYTES = 500_000


def _sdk_version() -> str | None:
    try:
        return version("openai-agents")
    except PackageNotFoundError:  # pragma: no cover - 仅在未安装 SDK 时
        return None


class OpenAICodegenWorkspace:
    """OpenAI function tools 的受限工作区实现，不开放任意路径或 Shell。"""

    def __init__(
        self,
        workdir: str,
        scenes: list[dict],
        render_engine: str,
        is_cancelled: Callable[[], bool],
    ):
        self.root = Path(workdir).resolve()
        self.scenes_dir = (self.root / "scenes").resolve()
        self.scenes = scenes
        self.render_engine = render_engine
        self.is_cancelled = is_cancelled
        self.tool_calls: list[str] = []

    def _check_cancelled(self) -> None:
        if self.is_cancelled():
            raise AgentCancelledError("task cancelled during agent execution")

    def _record(self, name: str) -> None:
        self._check_cancelled()
        self.tool_calls.append(name)
        logger.info("[OpenAIAgentRuntime] 第 %d 次工具调用：%s", len(self.tool_calls), name)

    def _scene_path(self, scene_index: int) -> Path:
        if not isinstance(scene_index, int) or isinstance(scene_index, bool):
            raise ValueError("scene_index 必须是整数")
        if scene_index < 0 or scene_index >= len(self.scenes):
            raise ValueError(f"scene_index 超出范围：{scene_index}")
        path = (self.scenes_dir / scene_filename(scene_index)).resolve()
        if path.parent != self.scenes_dir:
            raise ValueError("非法镜头路径")
        return path

    def read_context_file(self, name: Literal["input.json", "STYLE.md"]) -> str:
        self._record("read_context_file")
        if name not in {"input.json", "STYLE.md"}:
            raise ValueError("只允许读取 input.json 或 STYLE.md")
        path = (self.root / name).resolve()
        if path.parent != self.root or not path.is_file():
            raise ValueError(f"上下文文件不存在：{name}")
        if path.stat().st_size > MAX_CONTEXT_FILE_BYTES:
            raise ValueError(f"上下文文件过大：{name}")
        return path.read_text(encoding="utf-8")

    def list_scene_files(self) -> str:
        self._record("list_scene_files")
        names = sorted(path.name for path in self.scenes_dir.glob("scene_*.py"))
        return json.dumps(names, ensure_ascii=False)

    def read_scene(self, scene_index: int) -> str:
        self._record("read_scene")
        path = self._scene_path(scene_index)
        if not path.exists():
            return ""
        if path.stat().st_size > MAX_SCENE_FILE_BYTES:
            raise ValueError(f"镜头文件过大：{path.name}")
        return path.read_text(encoding="utf-8")

    def write_scene(self, scene_index: int, content: str) -> str:
        self._record("write_scene")
        path = self._scene_path(scene_index)
        self._write(path, content)
        return f"已写入 {path.name}（{len(content)} 字符）"

    def edit_scene(
        self, scene_index: int, old_text: str, new_text: str
    ) -> str:
        self._record("edit_scene")
        if not old_text:
            raise ValueError("old_text 不能为空")
        path = self._scene_path(scene_index)
        if not path.exists():
            raise ValueError(f"镜头文件不存在：{path.name}")
        content = path.read_text(encoding="utf-8")
        matches = content.count(old_text)
        if matches != 1:
            raise ValueError(f"old_text 必须精确匹配一次，当前匹配 {matches} 次")
        updated = content.replace(old_text, new_text, 1)
        self._write(path, updated)
        return f"已更新 {path.name}"

    async def validate(self) -> str:
        self._record("validate")
        is_valid, errors = await validate_workdir(
            str(self.root), self.scenes, self.render_engine
        )
        if is_valid:
            return "校验通过。"
        return f"校验失败：\n{errors}"

    @staticmethod
    def _write(path: Path, content: str) -> None:
        if not isinstance(content, str):
            raise ValueError("content 必须是字符串")
        encoded = content.encode("utf-8")
        if len(encoded) > MAX_SCENE_FILE_BYTES:
            raise ValueError("镜头文件超过大小限制")
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_bytes(encoded)
        os.replace(tmp_path, path)


def build_openai_tools(workspace: OpenAICodegenWorkspace):
    from agents import function_tool

    @function_tool
    def read_context_file(name: Literal["input.json", "STYLE.md"]) -> str:
        """读取任务上下文文件。name 只能是 input.json 或 STYLE.md。"""
        return workspace.read_context_file(name)

    @function_tool
    def list_scene_files() -> str:
        """列出 scenes 目录中已经存在的镜头文件。"""
        return workspace.list_scene_files()

    @function_tool
    def read_scene(scene_index: int) -> str:
        """读取指定编号的镜头 Python 代码，文件不存在时返回空字符串。"""
        return workspace.read_scene(scene_index)

    @function_tool
    def write_scene(scene_index: int, content: str) -> str:
        """完整写入指定编号的镜头 Python 代码。"""
        return workspace.write_scene(scene_index, content)

    @function_tool
    def edit_scene(scene_index: int, old_text: str, new_text: str) -> str:
        """在指定镜头中精确替换唯一一处文本。"""
        return workspace.edit_scene(scene_index, old_text, new_text)

    @function_tool
    async def validate() -> str:
        """校验当前全部镜头代码；修改后必须调用直到返回校验通过。"""
        return await workspace.validate()

    return [
        read_context_file,
        list_scene_files,
        read_scene,
        write_scene,
        edit_scene,
        validate,
    ]


def _usage_dict(usage: Any) -> dict[str, Any]:
    input_details = getattr(usage, "input_tokens_details", None)
    output_details = getattr(usage, "output_tokens_details", None)
    return {
        "requests": int(getattr(usage, "requests", 0) or 0),
        "input_tokens": int(getattr(usage, "input_tokens", 0) or 0),
        "output_tokens": int(getattr(usage, "output_tokens", 0) or 0),
        "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
        "input_tokens_details": {
            "cached_tokens": int(getattr(input_details, "cached_tokens", 0) or 0),
            "cache_write_tokens": int(
                getattr(input_details, "cache_write_tokens", 0) or 0
            ),
        },
        "output_tokens_details": {
            "reasoning_tokens": int(
                getattr(output_details, "reasoning_tokens", 0) or 0
            )
        },
    }


class OpenAIBudgetExceededError(Exception):
    def __init__(self, usage: dict[str, Any], total_cost_usd: float):
        self.usage = usage
        self.total_cost_usd = total_cost_usd
        super().__init__(
            f"Agent 预算已用尽：${total_cost_usd:.6f} > "
            f"${settings.AGENT_MAX_BUDGET_USD:.6f}"
        )


def _cost_from_usage(usage: dict[str, Any], config: ProviderSettings) -> float:
    cached_input_cost = config.cached_input_cost_per_million
    if cached_input_cost <= 0:
        # 未单独配置缓存价时按普通输入价计费，预算保护宁可高估，不能静默漏算。
        cached_input_cost = config.input_cost_per_million
    normalized = normalize_usage(
        usage,
        {
            "input": config.input_cost_per_million,
            "cached_input": cached_input_cost,
            "output": config.output_cost_per_million,
        },
    )
    total_cost = normalized.get("total_cost")
    return float(total_cost) if total_cost is not None else 0.0


def _build_budget_hooks(config: ProviderSettings, previous_cost_usd: float):
    from agents import RunHooks

    class BudgetHooks(RunHooks):
        async def on_llm_start(self, context, agent, system_prompt, input_items):
            if previous_cost_usd >= settings.AGENT_MAX_BUDGET_USD:
                raise OpenAIBudgetExceededError({}, previous_cost_usd)

        async def on_llm_end(self, context, agent, response):
            usage = _usage_dict(context.usage)
            total = previous_cost_usd + _cost_from_usage(usage, config)
            if total > settings.AGENT_MAX_BUDGET_USD:
                raise OpenAIBudgetExceededError(usage, total)

    return BudgetHooks()


class OpenAIAgentRuntime:
    provider = "openai"
    sdk_name = "openai-agents"

    def __init__(self, config: ProviderSettings, *, runner_run=None):
        if not config.api_key:
            raise ValueError("OpenAI Agent 模式需要配置 API Key")
        if not config.model:
            raise ValueError("OpenAI Agent 模式需要配置模型")
        if (
            config.input_cost_per_million <= 0
            or config.output_cost_per_million <= 0
        ):
            raise ValueError(
                "OpenAI Agent 模式需要为模型配置大于 0 的输入和输出单价，"
                "否则无法执行 AGENT_MAX_BUDGET_USD 预算保护"
            )
        self.config = config
        self.model = config.model
        self.sdk_version = _sdk_version()
        self._runner_run = runner_run

    async def run(
        self,
        *,
        instructions: str,
        input_text: str,
        workdir: str,
        scenes: list[dict],
        render_engine: str,
        continuation: Any | None,
        is_cancelled: Callable[[], bool],
    ) -> AgentRunResult:
        if is_cancelled():
            raise AgentCancelledError("task cancelled during agent execution")

        from agents import (
            Agent,
            AsyncOpenAI,
            ModelSettings,
            OpenAIResponsesModel,
            RunConfig,
            Runner,
        )

        client_kwargs: dict[str, Any] = {
            "api_key": self.config.api_key,
            "timeout": self.config.timeout_seconds,
        }
        if self.config.base_url:
            client_kwargs["base_url"] = self.config.base_url
        client = AsyncOpenAI(**client_kwargs)
        workspace = OpenAICodegenWorkspace(
            workdir, scenes, render_engine, is_cancelled
        )
        agent = Agent(
            name="Manim code generator",
            instructions=instructions,
            model=OpenAIResponsesModel(model=self.model, openai_client=client),
            model_settings=ModelSettings(
                parallel_tool_calls=False,
                include_usage=True,
                store=False,
                timeout=self.config.timeout_seconds,
            ),
            tools=build_openai_tools(workspace),
        )
        run_input: Any = input_text
        previous_cost = 0.0
        if isinstance(continuation, dict):
            previous_cost = float(continuation.get("spent_usd") or 0)
            history = continuation.get("history") or []
            run_input = [
                *history,
                {"role": "user", "content": input_text},
            ]
        runner_run = self._runner_run or Runner.run
        try:
            result = await runner_run(
                agent,
                run_input,
                max_turns=settings.AGENT_MAX_TURNS,
                hooks=_build_budget_hooks(self.config, previous_cost),
                run_config=RunConfig(
                    tracing_disabled=True,
                    workflow_name="AI video code generation",
                ),
            )
        except OpenAIBudgetExceededError as exc:
            return AgentRunResult(
                status="error_max_budget",
                continuation={"history": [], "spent_usd": exc.total_cost_usd},
                usage=exc.usage,
                total_cost_usd=max(exc.total_cost_usd - previous_cost, 0.0),
                num_turns=int(exc.usage.get("requests", 0) or 0),
                tool_calls=list(workspace.tool_calls),
            )
        except Exception as exc:
            from agents.exceptions import MaxTurnsExceeded

            if isinstance(exc, MaxTurnsExceeded):
                return AgentRunResult(
                    status="error_max_turns",
                    tool_calls=list(workspace.tool_calls),
                )
            raise
        if is_cancelled():
            raise AgentCancelledError("task cancelled during agent execution")

        usage = _usage_dict(result.context_wrapper.usage)
        total_cost = _cost_from_usage(usage, self.config)
        return AgentRunResult(
            status="success",
            final_output=str(result.final_output or ""),
            continuation={
                "history": result.to_input_list(),
                "spent_usd": previous_cost + total_cost,
            },
            usage=usage,
            total_cost_usd=total_cost,
            num_turns=usage["requests"],
            tool_calls=list(workspace.tool_calls),
        )
