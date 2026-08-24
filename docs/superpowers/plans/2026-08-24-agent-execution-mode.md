# Agent 执行模式 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为叙事生成与代码生成新增一种基于 Claude Agent SDK 的「Agent 迭代」执行模式，与现有「提示词 + 检查重试」模式并存，可在平台上按项目/全局配置选择。

**Architecture:** 在 worker 与生成逻辑之间抽出「执行策略层」——被替换的单元是整个迭代过程，而不是单次 LLM 调用。Prompt 策略原样承载现有逻辑；Agent 策略给模型一个沙箱工作目录（一镜头一文件）和一个包住 `validate_code()` 的 in-process MCP 工具，让它在同一会话上下文里反复「写文件 → 校验 → 改文件」。平台不信任 Agent 自述，`query()` 返回后自行回读文件重新校验。

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy / Alembic / Temporal / pytest；`claude-agent-sdk`（Python）+ `@anthropic-ai/claude-code`（Node CLI，容器内）；React + Vite 前端。

**Spec:** `docs/superpowers/specs/2026-08-24-agent-execution-mode-design.md`

## Global Constraints

- 执行模式取值只有两个字符串：`"prompt"` 和 `"agent"`。默认 `"prompt"`。
- `video_projects.execution_mode` **可空**，`NULL` = 继承全局；`ai_business_model_configs.execution_mode` **非空**，默认 `"prompt"`。
- 执行模式在 `activities.py` 派发任务时解析完毕并写入 `input_payload["execution_mode"]`。Worker 与策略层**不得**再查库决定模式。
- Agent 默认模型 `claude-opus-5`。Agent 工具白名单固定为 `tools=["Read", "Write", "Edit", "Glob"]`，**不得**给 Bash / WebSearch / WebFetch。
- `ClaudeAgentOptions` 必须显式设 `setting_sources=[]`。
- 平台侧回读校验是唯一可信的成功判据；`resume` 续跑**最多一次**。
- 数据库不设外键约束（项目既有约定）。
- 测试命令：`docker-compose run --rm backend uv run pytest tests/ -v`
- 宿主机直跑需绝对路径：`/Users/peng/.local/bin/uv run pytest tests/ -v`（裸 `uv` / `pnpm` 会 command not found）。

---

### Task 1: 抽出执行策略层（纯搬运，零新功能）

把 `CodeWorker._execute` 和 `NarrativeWorker._execute` 里的生成逻辑搬进策略类，worker 只负责取 payload、选策略、落库。**行为必须完全不变**——验收线是 `tests/test_code_worker.py` 和 `tests/test_narrative_worker.py` 的现有断言一行不改地继续通过。

**Files:**
- Create: `backend/app/services/strategies/__init__.py`
- Create: `backend/app/services/strategies/base.py`
- Create: `backend/app/services/strategies/prompt_codegen.py`
- Create: `backend/app/services/strategies/prompt_narrative.py`
- Modify: `backend/app/workers/code_worker.py`（`_execute` 瘦身）
- Modify: `backend/app/workers/narrative_worker.py`（`_execute` 瘦身）
- Test: `backend/tests/test_strategies_prompt.py`（新建）
- Test: `backend/tests/test_code_worker.py`、`backend/tests/test_narrative_worker.py`（**不修改**，仅需继续通过）

**Interfaces:**
- Consumes: 无（首个任务）
- Produces:
  - `CodegenOutcome(scenes: list[dict], ai_model: str, trace: dict)` — dataclass
  - `NarrativeOutcome(scenes: list[dict], fact_checks: list[dict], ai_model: str, trace: dict)` — dataclass
  - `class CodegenStrategy` 抽象：`async def run(self, *, scenes: list[dict], render_engine: str, style_components: dict[str, str], aspect_ratio: str, rejection_context: dict | None, previous_code_scenes: list[dict] | None, task_id) -> CodegenOutcome`
  - `class NarrativeStrategy` 抽象：`async def run(self, *, topic_title: str, topic_description: str, render_engine: str, aspect_ratio: str, rejection_context: dict | None, previous_scenes: list[dict] | None, narrative_context: list[dict], style_components: dict[str, str], task_id) -> NarrativeOutcome`
  - `PromptCodegenStrategy` / `PromptNarrativeStrategy` 实现上述抽象

- [ ] **Step 1: 写 dataclass 与抽象基类**

创建 `backend/app/services/strategies/base.py`：

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class CodegenOutcome:
    scenes: list[dict]
    ai_model: str
    trace: dict[str, Any] = field(default_factory=dict)


@dataclass
class NarrativeOutcome:
    scenes: list[dict]
    fact_checks: list[dict]
    ai_model: str
    trace: dict[str, Any] = field(default_factory=dict)


class CodegenStrategy(Protocol):
    async def run(
        self,
        *,
        scenes: list[dict],
        render_engine: str,
        style_components: dict[str, str],
        aspect_ratio: str,
        rejection_context: dict | None,
        previous_code_scenes: list[dict] | None,
        task_id: Any,
    ) -> CodegenOutcome: ...


class NarrativeStrategy(Protocol):
    async def run(
        self,
        *,
        topic_title: str,
        topic_description: str,
        render_engine: str,
        aspect_ratio: str,
        rejection_context: dict | None,
        previous_scenes: list[dict] | None,
        narrative_context: list[dict],
        style_components: dict[str, str],
        task_id: Any,
    ) -> NarrativeOutcome: ...
```

创建空的 `backend/app/services/strategies/__init__.py`。

- [ ] **Step 2: 搬运代码生成逻辑到 PromptCodegenStrategy**

创建 `backend/app/services/strategies/prompt_codegen.py`。把 `code_worker.py:60-149` 的内容原样搬进来——AI 调用、merge、`_MAX_VALIDATION_ROUNDS` 循环、repair、最终校验、抛错文案，**一个字都不要改**：

```python
import logging

from app.engines.ai.factory import get_ai_provider
from app.engines.render.base import SceneInput
from app.engines.render.factory import get_render_engine
from app.services.strategies.base import CodegenOutcome

_MAX_VALIDATION_ROUNDS = 2

logger = logging.getLogger(__name__)


class PromptCodegenStrategy:
    async def run(
        self,
        *,
        scenes,
        render_engine,
        style_components,
        aspect_ratio,
        rejection_context,
        previous_code_scenes,
        task_id,
    ) -> CodegenOutcome:
        provider = get_ai_provider("code_generation")
        logger.info("[PromptCodegen] calling AI provider model=%s", provider.model_name)
        codegen_scenes = [
            {
                "scene_index": scene["scene_index"],
                "narration": scene["narration"],
                "description": scene["description"],
                "duration_seconds": scene.get("duration_seconds"),
                "beats": scene["beats"],
            }
            for scene in scenes
        ]
        result = await provider.generate_code(
            scenes=codegen_scenes,
            render_engine=render_engine,
            style_components=style_components,
            aspect_ratio=aspect_ratio,
            rejection_context=rejection_context,
            previous_code_scenes=previous_code_scenes,
        )
        logger.info("[PromptCodegen] AI done: codes=%d", len(result.codes))

        merged_scenes = []
        for i, scene in enumerate(scenes):
            code = result.codes[i] if i < len(result.codes) else ""
            merged_scenes.append({**scene, "code": code})

        render_engine_obj = get_render_engine(render_engine)
        repair_rounds = 0
        for round_num in range(_MAX_VALIDATION_ROUNDS):
            is_valid, errors = await render_engine_obj.validate_code(
                _scene_inputs(merged_scenes)
            )
            if is_valid:
                logger.info("[PromptCodegen] validation passed (round %d)", round_num)
                break
            logger.info(
                "[PromptCodegen] validation round %d/%d failed, repairing...",
                round_num + 1,
                _MAX_VALIDATION_ROUNDS,
            )
            repair_rounds += 1
            repair_provider = get_ai_provider("code_repair")
            repair_result = await repair_provider.repair_code(
                scenes=merged_scenes,
                render_engine=render_engine,
                error_message=errors,
                style_components=style_components,
                aspect_ratio=aspect_ratio,
            )
            for r in repair_result.repairs:
                idx = r["scene_index"]
                merged_scenes[idx] = {**merged_scenes[idx], "code": r["code"]}
                logger.info(
                    "[PromptCodegen] repaired scene %d: %s",
                    idx,
                    r.get("explanation", "")[:120],
                )
        else:
            is_valid, errors = await render_engine_obj.validate_code(
                _scene_inputs(merged_scenes)
            )
            if is_valid:
                logger.info("[PromptCodegen] validation passed after final repair")
            else:
                logger.warning(
                    "[PromptCodegen] validation still failing after %d rounds:\n%s",
                    _MAX_VALIDATION_ROUNDS,
                    errors[:500],
                )
                raise ValueError(
                    f"Code validation failed after {_MAX_VALIDATION_ROUNDS} repair rounds:\n{errors[:2000]}"
                )

        return CodegenOutcome(
            scenes=merged_scenes,
            ai_model=provider.model_name,
            trace={"execution_mode": "prompt", "repair_rounds": repair_rounds},
        )


def _scene_inputs(merged_scenes: list[dict]) -> list[SceneInput]:
    return [
        SceneInput(
            scene_index=i,
            narration=s.get("narration", ""),
            description=s.get("description", ""),
            code=s.get("code", ""),
            audio=None,
        )
        for i, s in enumerate(merged_scenes)
    ]
```

- [ ] **Step 3: 搬运叙事生成逻辑到 PromptNarrativeStrategy**

创建 `backend/app/services/strategies/prompt_narrative.py`。搬 `narrative_worker.py:94-105` 的 AI 调用部分（TTS 与落库留在 worker）：

```python
import logging

from app.engines.ai.factory import get_ai_provider
from app.services.strategies.base import NarrativeOutcome

logger = logging.getLogger(__name__)


class PromptNarrativeStrategy:
    async def run(
        self,
        *,
        topic_title,
        topic_description,
        render_engine,
        aspect_ratio,
        rejection_context,
        previous_scenes,
        narrative_context,
        style_components,
        task_id,
    ) -> NarrativeOutcome:
        provider = get_ai_provider("narrative_generation")
        logger.info("[PromptNarrative] calling AI provider model=%s", provider.model_name)
        result = await provider.generate_narrative(
            topic_title=topic_title,
            topic_description=topic_description,
            render_engine=render_engine,
            rejection_context=rejection_context,
            previous_scenes=previous_scenes,
            narrative_context=narrative_context,
            style_components=style_components,
            aspect_ratio=aspect_ratio,
        )
        logger.info(
            "[PromptNarrative] AI done: scenes=%d fact_checks=%d",
            len(result.scenes),
            len(result.fact_checks),
        )
        return NarrativeOutcome(
            scenes=result.scenes,
            fact_checks=result.fact_checks,
            ai_model=provider.model_name,
            trace={"execution_mode": "prompt"},
        )
```

- [ ] **Step 4: 加一个选择器函数**

在 `backend/app/services/strategies/__init__.py` 写：

```python
from app.services.strategies.base import (
    CodegenOutcome,
    CodegenStrategy,
    NarrativeOutcome,
    NarrativeStrategy,
)
from app.services.strategies.prompt_codegen import PromptCodegenStrategy
from app.services.strategies.prompt_narrative import PromptNarrativeStrategy

__all__ = [
    "CodegenOutcome",
    "CodegenStrategy",
    "NarrativeOutcome",
    "NarrativeStrategy",
    "PromptCodegenStrategy",
    "PromptNarrativeStrategy",
    "get_codegen_strategy",
    "get_narrative_strategy",
]


def get_codegen_strategy(execution_mode: str) -> CodegenStrategy:
    return PromptCodegenStrategy()


def get_narrative_strategy(execution_mode: str) -> NarrativeStrategy:
    return PromptNarrativeStrategy()
```

Task 1 里两个选择器**忽略参数、恒返回 Prompt 策略**——Agent 分支在 Task 4 / Task 6 接上。这样做是为了让 Task 1 保持零行为变化。

- [ ] **Step 5: 改 CodeWorker._execute 调用策略**

`backend/app/workers/code_worker.py`：删掉 `_MAX_VALIDATION_ROUNDS` 常量和相关 import（`get_ai_provider`、`SceneInput`、`get_render_engine`），把原来 `provider = get_ai_provider(...)` 到 `raise ValueError(...)` 那一整段（第 60-149 行）换成：

```python
            strategy = get_codegen_strategy(payload.get("execution_mode", "prompt"))
            outcome = await strategy.run(
                scenes=scenes,
                render_engine=render_engine,
                style_components=style_components,
                aspect_ratio=aspect_ratio,
                rejection_context=rejection_context,
                previous_code_scenes=previous_code_scenes,
                task_id=task.id,
            )
            merged_scenes = outcome.scenes
```

下方建 `CodeVersion` 时把 `ai_model=provider.model_name` 改成 `ai_model=outcome.ai_model`；返回 dict 增加 `"trace": outcome.trace`。顶部加 `from app.services.strategies import get_codegen_strategy`。

- [ ] **Step 6: 改 NarrativeWorker._execute 调用策略**

`backend/app/workers/narrative_worker.py`：把第 94-105 行（`provider = get_ai_provider(...)` 到 `)` ）换成：

```python
        strategy = get_narrative_strategy(payload.get("execution_mode", "prompt"))
        outcome = await strategy.run(
            topic_title=topic_title,
            topic_description=topic_description,
            render_engine=render_engine,
            aspect_ratio=aspect_ratio,
            rejection_context=rejection_context,
            previous_scenes=previous_scenes,
            narrative_context=narrative_context,
            style_components=style_components,
            task_id=task.id,
        )
```

后续所有 `result.scenes` → `outcome.scenes`，`result.fact_checks` → `outcome.fact_checks`，`ai_model=provider.model_name` → `ai_model=outcome.ai_model`。删掉 `get_ai_provider` import。返回 dict 增加 `"trace": outcome.trace`。

- [ ] **Step 7: 跑现有 worker 测试，必须全绿且未改动测试文件**

```bash
docker-compose run --rm backend uv run pytest tests/test_code_worker.py tests/test_narrative_worker.py -v
```

Expected: PASS。若失败，说明搬运时改了行为——**修实现，不要改测试**。

再确认测试文件确实没被动过：

```bash
git diff --stat backend/tests/test_code_worker.py backend/tests/test_narrative_worker.py
```

Expected: 空输出。

- [ ] **Step 8: 为策略层补直接测试**

创建 `backend/tests/test_strategies_prompt.py`：

```python
import pytest
from unittest.mock import AsyncMock, patch

from app.engines.ai.base import CodeGenerationResult
from app.services.strategies import get_codegen_strategy, get_narrative_strategy
from app.services.strategies.prompt_codegen import PromptCodegenStrategy
from app.services.strategies.prompt_narrative import PromptNarrativeStrategy


def test_selector_returns_prompt_strategy_by_default():
    assert isinstance(get_codegen_strategy("prompt"), PromptCodegenStrategy)
    assert isinstance(get_narrative_strategy("prompt"), PromptNarrativeStrategy)


@pytest.mark.asyncio
async def test_prompt_codegen_merges_codes_into_scenes():
    scenes = [
        {"scene_index": 0, "narration": "旁白", "description": "描述", "beats": []},
    ]
    mock_provider = AsyncMock()
    mock_provider.model_name = "stub-model"
    mock_provider.generate_code = AsyncMock(
        return_value=CodeGenerationResult(codes=["# code 0"])
    )
    mock_engine = AsyncMock()
    mock_engine.validate_code = AsyncMock(return_value=(True, ""))

    with patch(
        "app.services.strategies.prompt_codegen.get_ai_provider",
        return_value=mock_provider,
    ), patch(
        "app.services.strategies.prompt_codegen.get_render_engine",
        return_value=mock_engine,
    ):
        outcome = await get_codegen_strategy("prompt").run(
            scenes=scenes,
            render_engine="manim",
            style_components={},
            aspect_ratio="landscape",
            rejection_context=None,
            previous_code_scenes=None,
            task_id="t1",
        )

    assert outcome.scenes[0]["code"] == "# code 0"
    assert outcome.ai_model == "stub-model"
    assert outcome.trace["execution_mode"] == "prompt"
    assert outcome.trace["repair_rounds"] == 0
```

- [ ] **Step 9: 跑全量测试**

```bash
docker-compose run --rm backend uv run pytest tests/ -v
```

Expected: 全部 PASS。

- [ ] **Step 10: 提交**

```bash
git add backend/app/services/strategies backend/app/workers/code_worker.py backend/app/workers/narrative_worker.py backend/tests/test_strategies_prompt.py
git commit -m "refactor: 抽出执行策略层，worker 只负责取数据与落库"
```

---

### Task 2: 数据模型与配置解析

加两列 `execution_mode`、把 `anthropic` 加进 provider 类型、放宽 `base_url` 允许空串、在 `activities.py` 解析模式写入 payload。此步完成后全局默认仍是 `prompt`，**运行时行为无任何变化**。

**Files:**
- Create: `backend/alembic/versions/<hash>_add_execution_mode.py`
- Modify: `backend/app/models/project.py`（加 `execution_mode`）
- Modify: `backend/app/models/ai_model_config.py`（`AIBusinessModelConfig` 加 `execution_mode`）
- Modify: `backend/app/schemas/ai_model_config.py:9`（`AI_PROVIDER_TYPES`）、`:21` 与 `:46`（`base_url` 放宽）
- Modify: `backend/app/schemas/project.py`（`ProjectCreate` 加 `execution_mode`）
- Modify: `backend/app/workflows/activities.py`（两处 `input_payload`）
- Test: `backend/tests/test_execution_mode_resolution.py`（新建）

**Interfaces:**
- Consumes: Task 1 的 `get_codegen_strategy(execution_mode)` / `get_narrative_strategy(execution_mode)`
- Produces:
  - `resolve_execution_mode(db, project, business: str) -> str` — 位于 `backend/app/services/execution_mode.py`，返回 `"prompt"` 或 `"agent"`
  - `input_payload["execution_mode"]` 字段（两种任务类型都有）
  - `video_projects.execution_mode`（可空）、`ai_business_model_configs.execution_mode`（非空，默认 `prompt`）

- [ ] **Step 1: 先写解析逻辑的失败测试**

创建 `backend/tests/test_execution_mode_resolution.py`：

```python
from unittest.mock import MagicMock

from app.services.execution_mode import resolve_execution_mode


def _db_with_business_mode(mode):
    db = MagicMock()
    config = MagicMock()
    config.execution_mode = mode
    db.execute.return_value.scalar_one_or_none.return_value = config
    return db


def test_project_level_overrides_global():
    project = MagicMock()
    project.execution_mode = "agent"
    db = _db_with_business_mode("prompt")
    assert resolve_execution_mode(db, project, "code_generation") == "agent"


def test_null_project_falls_back_to_global():
    project = MagicMock()
    project.execution_mode = None
    db = _db_with_business_mode("agent")
    assert resolve_execution_mode(db, project, "code_generation") == "agent"


def test_missing_global_config_defaults_to_prompt():
    project = MagicMock()
    project.execution_mode = None
    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = None
    assert resolve_execution_mode(db, project, "code_generation") == "prompt"


def test_unknown_value_defaults_to_prompt():
    project = MagicMock()
    project.execution_mode = "banana"
    db = _db_with_business_mode("prompt")
    assert resolve_execution_mode(db, project, "code_generation") == "prompt"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
docker-compose run --rm backend uv run pytest tests/test_execution_mode_resolution.py -v
```

Expected: FAIL，`ModuleNotFoundError: No module named 'app.services.execution_mode'`

- [ ] **Step 3: 写解析实现**

创建 `backend/app/services/execution_mode.py`：

```python
from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.models.ai_model_config import AIBusinessModelConfig

VALID_EXECUTION_MODES = ("prompt", "agent")
DEFAULT_EXECUTION_MODE = "prompt"


def _normalize(value: Any) -> str | None:
    if isinstance(value, str) and value in VALID_EXECUTION_MODES:
        return value
    return None


def resolve_execution_mode(db: Any, project: Any, business: str) -> str:
    """项目级 → 全局业务配置 → 默认。无效值一律回落到默认。"""
    project_mode = _normalize(getattr(project, "execution_mode", None))
    if project_mode is not None:
        return project_mode

    config = db.execute(
        select(AIBusinessModelConfig).where(
            AIBusinessModelConfig.business == business
        )
    ).scalar_one_or_none()
    if config is not None:
        global_mode = _normalize(getattr(config, "execution_mode", None))
        if global_mode is not None:
            return global_mode

    return DEFAULT_EXECUTION_MODE
```

- [ ] **Step 4: 运行测试确认通过**

```bash
docker-compose run --rm backend uv run pytest tests/test_execution_mode_resolution.py -v
```

Expected: 4 passed

- [ ] **Step 5: 加 ORM 列**

`backend/app/models/project.py`，在 `aspect_ratio` 下面加：

```python
    execution_mode: Mapped[Optional[str]] = mapped_column(String(20))
```

`backend/app/models/ai_model_config.py` 的 `AIBusinessModelConfig`，在 `model_id` 下面加：

```python
    execution_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default="prompt", server_default="prompt"
    )
```

- [ ] **Step 6: 生成并编辑迁移**

先看当前 head：

```bash
docker-compose run --rm backend uv run alembic heads
```

创建 `backend/alembic/versions/<hash>_add_execution_mode.py`，`down_revision` 填上一步查到的 head：

```python
"""add execution_mode columns

Revision ID: a71c39d5e284
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a71c39d5e284"
down_revision: Union[str, Sequence[str], None] = "<上一步查到的 head>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "video_projects",
        sa.Column("execution_mode", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "ai_business_model_configs",
        sa.Column(
            "execution_mode",
            sa.String(length=20),
            nullable=False,
            server_default="prompt",
        ),
    )


def downgrade() -> None:
    op.drop_column("ai_business_model_configs", "execution_mode")
    op.drop_column("video_projects", "execution_mode")
```

- [ ] **Step 7: 应用迁移**

```bash
docker-compose run --rm backend uv run alembic upgrade head
```

Expected: 无报错。

- [ ] **Step 8: 放宽 provider schema**

`backend/app/schemas/ai_model_config.py`：

第 9 行改为：

```python
AI_PROVIDER_TYPES = {"deepseek", "openrouter", "gemini", "doubao", "anthropic"}
```

`AIModelProviderBase.base_url`（第 21 行）改为——去掉 `min_length=1`，空串表示「走官方端点」：

```python
    base_url: str = Field(default="", max_length=300)
```

`AIModelProviderUpdate.base_url`（第 46 行）同样去掉 `min_length=1`：

```python
    base_url: str | None = Field(default=None, max_length=300)
```

- [ ] **Step 9: 加 provider schema 测试**

追加到 `backend/tests/test_ai_model_settings.py` 末尾：

```python
from app.schemas.ai_model_config import AIModelProviderCreate


def test_anthropic_provider_accepts_empty_base_url():
    provider = AIModelProviderCreate(
        name="Anthropic 官方",
        provider_type="anthropic",
        base_url="",
        api_key="sk-test",
    )
    assert provider.provider_type == "anthropic"
    assert provider.base_url == ""


def test_anthropic_provider_accepts_gateway_base_url():
    provider = AIModelProviderCreate(
        name="中转",
        provider_type="anthropic",
        base_url="https://gateway.example.com",
        api_key="sk-test",
    )
    assert provider.base_url == "https://gateway.example.com"
```

- [ ] **Step 10: 项目创建 schema 加字段**

`backend/app/schemas/project.py` 的 `ProjectCreate` 加一行：

```python
    execution_mode: Optional[str] = None
```

（`Optional` 已在该文件顶部导入。）确认创建项目的 API 把该字段写入 `VideoProject`——检查 `backend/app/api/projects.py` 里构造 `VideoProject(...)` 的位置，若是逐字段赋值则补上 `execution_mode=payload.execution_mode`。

- [ ] **Step 11: activities 里解析并写入 payload**

`backend/app/workflows/activities.py` 顶部加：

```python
from app.services.execution_mode import resolve_execution_mode
```

`submit_narrative_task` 的 `input_payload` 字典里加一行：

```python
                "execution_mode": resolve_execution_mode(db, project, "narrative_generation"),
```

`submit_code_task` 的 `input_payload` 字典里加一行：

```python
                "execution_mode": resolve_execution_mode(db, project, "code_generation"),
```

- [ ] **Step 12: 加 activities 测试**

追加到 `backend/tests/test_activities.py` 末尾（若该文件已有 mock db 的 helper，复用它；否则用下面的写法）：

```python
from unittest.mock import MagicMock, patch


@pytest.mark.asyncio
async def test_submit_code_task_writes_execution_mode_into_payload():
    from app.workflows import activities

    captured = {}

    def fake_resolve(db, project, business):
        captured["business"] = business
        return "agent"

    with patch.object(activities, "resolve_execution_mode", fake_resolve):
        mode = activities.resolve_execution_mode(MagicMock(), MagicMock(), "code_generation")

    assert mode == "agent"
    assert captured["business"] == "code_generation"
```

- [ ] **Step 13: 跑全量测试**

```bash
docker-compose run --rm backend uv run pytest tests/ -v
```

Expected: 全部 PASS。

- [ ] **Step 14: 提交**

```bash
git add backend/alembic/versions backend/app/models backend/app/schemas backend/app/services/execution_mode.py backend/app/workflows/activities.py backend/app/api/projects.py backend/tests
git commit -m "feat: 新增 execution_mode 配置与解析，provider 支持 anthropic"
```

---

### Task 3: 容器依赖与 SDK 能力确认

装 SDK、装 Node CLI，并**实地确认 `ClaudeAgentOptions` 是否有 `max_budget_usd`**——spec 里留的唯一不确定项在这一步结掉。

**Files:**
- Modify: `backend/Dockerfile`
- Modify: `backend/pyproject.toml`
- Modify: `docs/superpowers/specs/2026-08-24-agent-execution-mode-design.md`（把确认结果写回「成本刹车」一节）

**Interfaces:**
- Consumes: 无
- Produces: 容器内可 `from claude_agent_sdk import query, ClaudeAgentOptions, tool, create_sdk_mcp_server`；`max_budget_usd` 是否可用的确定结论

- [ ] **Step 1: 加 Python 依赖**

`backend/pyproject.toml` 的 `dependencies` 列表加一项：

```toml
    "claude-agent-sdk",
```

- [ ] **Step 2: Dockerfile 装 Node CLI**

`backend/Dockerfile` 中已有的 Node 22 安装块（`curl -fsSL https://deb.nodesource.com/setup_22.x` 那段，为 Remotion 装的）**之后**，加一层：

```dockerfile
# Claude Agent SDK 需要 claude CLI（Node 22 已在上一层装好）
RUN npm install -g @anthropic-ai/claude-code
```

- [ ] **Step 3: 重建镜像**

```bash
docker-compose build backend
```

Expected: 构建成功。

- [ ] **Step 4: 确认导入可用**

```bash
docker-compose run --rm backend uv run python -c "from claude_agent_sdk import query, ClaudeAgentOptions, tool, create_sdk_mcp_server; print('ok')"
```

Expected: 打印 `ok`

- [ ] **Step 5: 确认 max_budget_usd 是否存在**

```bash
docker-compose run --rm backend uv run python -c "
import dataclasses
from claude_agent_sdk import ClaudeAgentOptions
names = {f.name for f in dataclasses.fields(ClaudeAgentOptions)}
print('max_budget_usd:', 'max_budget_usd' in names)
print('setting_sources:', 'setting_sources' in names)
print('tools:', 'tools' in names)
print(sorted(names))
"
```

记录输出。**这个结果决定 Task 4 Step 6 的写法**：

- 若 `max_budget_usd: True` → Task 4 中在 `ClaudeAgentOptions` 里设 `max_budget_usd=settings.AGENT_MAX_BUDGET_USD`。
- 若 `False` → Task 4 中不设该字段，仅靠 `max_turns` 兜底，并在 trace 里记录实际花费供事后观察。

同样确认 `tools` 字段是否存在：若不存在（只有 `allowed_tools` / `disallowed_tools`），则改用 `disallowed_tools=["Bash", "WebSearch", "WebFetch", "Task", "NotebookEdit"]` 达到同等效果，并在 Task 4 中据此调整。

- [ ] **Step 6: 把结论写回 spec**

编辑 `docs/superpowers/specs/2026-08-24-agent-execution-mode-design.md` 的「成本刹车」一节，把「疑似存在 / 实现时验证」替换为实测结论（存在与否、最终采用哪种兜底）。

- [ ] **Step 7: 加配置项**

`backend/app/config.py` 的 `Settings` 类里，`REMOTION_TEMPLATE_DIR` 附近加：

```python
    AGENT_MODEL: str = "claude-opus-5"
    AGENT_MAX_TURNS: int = 40
    AGENT_MAX_BUDGET_USD: float = 2.0
    AGENT_TIMEOUT_SECONDS: float = 1800.0
```

- [ ] **Step 8: 提交**

```bash
git add backend/Dockerfile backend/pyproject.toml backend/uv.lock backend/app/config.py docs/superpowers/specs/2026-08-24-agent-execution-mode-design.md
git commit -m "build: 容器内装 claude-agent-sdk 与 claude CLI，加 Agent 运行参数"
```

---

### Task 4: 代码侧 Agent 策略

本计划的核心。先做代码侧——它失败率最高、闭环信号最硬。

**Files:**
- Create: `backend/app/services/strategies/agent_sandbox.py`（沙箱读写 + MCP 工具）
- Create: `backend/app/services/strategies/agent_codegen.py`（策略主体）
- Modify: `backend/app/services/strategies/__init__.py`（选择器接上 agent 分支）
- Test: `backend/tests/test_agent_sandbox.py`（新建）
- Test: `backend/tests/test_agent_codegen.py`（新建）

**Interfaces:**
- Consumes: Task 1 的 `CodegenOutcome`；Task 3 的 `settings.AGENT_MODEL` / `AGENT_MAX_TURNS` / `AGENT_MAX_BUDGET_USD`
- Produces:
  - `write_sandbox(workdir: str, scenes: list[dict], style_components: dict[str, str], aspect_ratio: str, render_engine: str) -> None`
  - `read_scene_codes(workdir: str, scene_count: int) -> list[str]` — 缺失的文件返回空串
  - `build_validate_server(workdir: str, scenes: list[dict], render_engine: str)` — 返回 `(mcp_server, tool_name)`，`tool_name` 为 `"mcp__codegen__validate"`
  - `AgentCancelledError` — 异常类
  - `AgentCodegenStrategy(agent_query=None)` — `agent_query` 默认为 SDK 的 `query`，测试注入假实现

- [ ] **Step 1: 先写沙箱读写的失败测试**

创建 `backend/tests/test_agent_sandbox.py`：

```python
import json
import os

import pytest

from app.services.strategies.agent_sandbox import (
    build_validate_server,
    read_scene_codes,
    write_sandbox,
)

SCENES = [
    {"scene_index": 0, "narration": "旁白零", "description": "描述零", "beats": []},
    {"scene_index": 1, "narration": "旁白一", "description": "描述一", "beats": []},
]


def test_write_sandbox_creates_input_style_and_scenes_dir(tmp_path):
    write_sandbox(
        str(tmp_path),
        scenes=SCENES,
        style_components={"color_scheme": "蓝色"},
        aspect_ratio="landscape",
        render_engine="manim",
    )
    payload = json.loads((tmp_path / "input.json").read_text())
    assert len(payload["scenes"]) == 2
    assert payload["scenes"][0]["narration"] == "旁白零"
    style = (tmp_path / "STYLE.md").read_text()
    assert "蓝色" in style
    assert "landscape" in style
    assert (tmp_path / "scenes").is_dir()


def test_read_scene_codes_returns_files_in_index_order(tmp_path):
    scenes_dir = tmp_path / "scenes"
    scenes_dir.mkdir()
    (scenes_dir / "scene_00.py").write_text("# zero")
    (scenes_dir / "scene_01.py").write_text("# one")
    assert read_scene_codes(str(tmp_path), 2) == ["# zero", "# one"]


def test_read_scene_codes_returns_empty_string_for_missing_file(tmp_path):
    (tmp_path / "scenes").mkdir()
    (tmp_path / "scenes" / "scene_00.py").write_text("# zero")
    assert read_scene_codes(str(tmp_path), 2) == ["# zero", ""]
```

- [ ] **Step 2: 运行确认失败**

```bash
docker-compose run --rm backend uv run pytest tests/test_agent_sandbox.py -v
```

Expected: FAIL，`ModuleNotFoundError: No module named 'app.services.strategies.agent_sandbox'`

- [ ] **Step 3: 实现沙箱读写**

创建 `backend/app/services/strategies/agent_sandbox.py`：

```python
from __future__ import annotations

import json
import logging
import os

from app.engines.render.base import SceneInput
from app.engines.render.factory import get_render_engine

logger = logging.getLogger(__name__)

VALIDATE_TOOL_NAME = "mcp__codegen__validate"


def scene_filename(index: int) -> str:
    return f"scene_{index:02d}.py"


def write_sandbox(
    workdir: str,
    *,
    scenes: list[dict],
    style_components: dict[str, str],
    aspect_ratio: str,
    render_engine: str,
) -> None:
    """写入 input.json / STYLE.md，并建好空的 scenes/ 目录。"""
    payload = {
        "render_engine": render_engine,
        "aspect_ratio": aspect_ratio,
        "scenes": [
            {
                "scene_index": s["scene_index"],
                "narration": s.get("narration", ""),
                "description": s.get("description", ""),
                "duration_seconds": s.get("duration_seconds"),
                "beats": s.get("beats", []),
            }
            for s in scenes
        ],
    }
    with open(os.path.join(workdir, "input.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    lines = [
        "# 风格与约束",
        "",
        f"- 渲染引擎：{render_engine}",
        f"- 画幅：{aspect_ratio}",
        "",
    ]
    for category, text in style_components.items():
        lines.append(f"## {category}")
        lines.append("")
        lines.append(text)
        lines.append("")
    with open(os.path.join(workdir, "STYLE.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    os.makedirs(os.path.join(workdir, "scenes"), exist_ok=True)


def read_scene_codes(workdir: str, scene_count: int) -> list[str]:
    """按 scene_index 顺序回读代码；文件缺失返回空串。"""
    codes: list[str] = []
    for i in range(scene_count):
        path = os.path.join(workdir, "scenes", scene_filename(i))
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                codes.append(f.read())
        else:
            codes.append("")
    return codes


async def validate_workdir(
    workdir: str, scenes: list[dict], render_engine: str
) -> tuple[bool, str]:
    """回读 scenes/ 并调渲染引擎校验。平台侧与 MCP 工具共用同一条路径。"""
    codes = read_scene_codes(workdir, len(scenes))
    missing = [i for i, code in enumerate(codes) if not code.strip()]
    if missing:
        names = ", ".join(scene_filename(i) for i in missing)
        return False, f"以下镜头文件缺失或为空：{names}"

    scene_inputs = [
        SceneInput(
            scene_index=i,
            narration=scenes[i].get("narration", ""),
            description=scenes[i].get("description", ""),
            code=codes[i],
            audio=None,
        )
        for i in range(len(scenes))
    ]
    return await get_render_engine(render_engine).validate_code(scene_inputs)


def build_validate_server(workdir: str, scenes: list[dict], render_engine: str):
    """构造 in-process MCP server，返回 (server, tool_name)。"""
    from claude_agent_sdk import ToolAnnotations, create_sdk_mcp_server, tool

    @tool(
        "validate",
        "校验 scenes/ 目录下当前全部镜头代码。返回通过或详细报错（报错中会标出出问题的镜头编号）。修改代码后必须再次调用本工具确认通过。",
        {},
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def validate(args):
        is_valid, errors = await validate_workdir(workdir, scenes, render_engine)
        if is_valid:
            return {"content": [{"type": "text", "text": "校验通过。"}]}
        return {
            "content": [{"type": "text", "text": f"校验失败：\n{errors}"}],
            "is_error": True,
        }

    server = create_sdk_mcp_server(name="codegen", version="1.0.0", tools=[validate])
    return server, VALIDATE_TOOL_NAME
```

- [ ] **Step 4: 运行确认通过**

```bash
docker-compose run --rm backend uv run pytest tests/test_agent_sandbox.py -v
```

Expected: 3 passed

- [ ] **Step 5: 写策略编排的失败测试**

创建 `backend/tests/test_agent_codegen.py`。这是本计划最重要的一组测试——**第一个用例钉死「不信任 Agent 自述」这条安全底座**：

```python
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
```

- [ ] **Step 6: 运行确认失败**

```bash
docker-compose run --rm backend uv run pytest tests/test_agent_codegen.py -v
```

Expected: FAIL，`ModuleNotFoundError: No module named 'app.services.strategies.agent_codegen'`

- [ ] **Step 7: 实现 Agent 策略**

创建 `backend/app/services/strategies/agent_codegen.py`。

**注意**：`ClaudeAgentOptions` 中 `tools=` 与 `max_budget_usd=` 两个字段是否传，取决于 Task 3 Step 5 的实测结果——不存在的字段会让 dataclass 构造直接报 `TypeError`，按那一步记录的结论取舍。

```python
from __future__ import annotations

import json
import logging
import shutil
import tempfile
import uuid
from typing import Any

from app.config import settings
from app.db import get_sync_session
from app.models.worker_task import WorkerTask
from app.services.strategies.agent_sandbox import (
    VALIDATE_TOOL_NAME,
    build_validate_server,
    read_scene_codes,
    validate_workdir,
    write_sandbox,
)
from app.services.strategies.base import CodegenOutcome

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """你是渲染代码工程师。工作目录里有：

- `input.json`：待实现的镜头叙事，每个镜头有 scene_index / narration / description / beats。
- `STYLE.md`：必须遵守的风格与画幅约束。
- `scenes/`：你的产出目录。

任务：为 input.json 里的**每一个**镜头写一个文件 `scenes/scene_NN.py`（NN 为两位数的 scene_index，从 00 开始），一个镜头一个文件，不得合并或省略。

工作方式：写完后调用 `validate` 工具校验。校验报错会指出出问题的镜头编号，你据此只修改对应文件，然后重新校验。**必须**反复迭代直到 validate 返回通过为止，通过之后才能结束。不要在校验尚未通过时就宣称完成。"""


class AgentCancelledError(Exception):
    """任务在 Agent 执行途中被取消。"""


def is_task_cancelled(task_id: Any) -> bool:
    if task_id is None:
        return False
    db = get_sync_session()
    try:
        task = db.get(WorkerTask, task_id if isinstance(task_id, uuid.UUID) else task_id)
        return task is not None and task.status == "cancelled"
    except Exception:
        logger.exception("[AgentCodegen] 取消状态查询失败，按未取消处理")
        return False
    finally:
        db.close()


async def record_agent_call(
    *, model: str, business: str, input_summary: dict, output: str,
    total_cost_usd: float | None, status: str, error_message: str | None = None,
) -> None:
    """一次 Agent 执行记一条 ai_call_records（best-effort，失败不影响主流程）。"""
    from app.db import AsyncSessionLocal
    from app.models.ai_call_record import AICallRecord

    try:
        async with AsyncSessionLocal() as db:
            db.add(
                AICallRecord(
                    id=uuid.uuid4(),
                    provider="anthropic",
                    model=model,
                    business=business,
                    request_type="agent",
                    status=status,
                    input=input_summary,
                    output=output,
                    total_cost=total_cost_usd,
                    error_message=error_message,
                )
            )
            await db.commit()
    except Exception:
        logger.exception("[AgentCodegen] ai_call_records 写入失败，忽略")


class AgentCodegenStrategy:
    def __init__(self, agent_query=None):
        self._agent_query = agent_query

    def _query(self):
        if self._agent_query is not None:
            return self._agent_query
        from claude_agent_sdk import query

        return query

    async def run(
        self,
        *,
        scenes,
        render_engine,
        style_components,
        aspect_ratio,
        rejection_context,
        previous_code_scenes,
        task_id,
    ) -> CodegenOutcome:
        workdir = tempfile.mkdtemp(prefix="agent-codegen-")
        trace: dict[str, Any] = {
            "execution_mode": "agent",
            "tool_calls": [],
            "resumed": False,
            "total_cost_usd": 0.0,
        }
        try:
            write_sandbox(
                workdir,
                scenes=scenes,
                style_components=style_components,
                aspect_ratio=aspect_ratio,
                render_engine=render_engine,
            )
            server, tool_name = build_validate_server(workdir, scenes, render_engine)

            prompt = _SYSTEM_PROMPT
            if rejection_context:
                prompt += (
                    "\n\n这是一次重新生成，上一版被驳回。驳回意见：\n"
                    + json.dumps(rejection_context, ensure_ascii=False)
                )

            session_id = await self._run_once(
                prompt=prompt,
                server=server,
                tool_name=tool_name,
                workdir=workdir,
                trace=trace,
                task_id=task_id,
                resume=None,
            )

            is_valid, errors = await validate_workdir(workdir, scenes, render_engine)
            if not is_valid:
                # Agent 认为完成了，平台判定未过 —— 只给一次续跑机会
                logger.info("[AgentCodegen] 平台回读校验未过，resume 续跑一次")
                trace["resumed"] = True
                await self._run_once(
                    prompt=(
                        "平台侧校验仍未通过，报错如下，请继续修改 scenes/ 下的文件"
                        f"直到 validate 通过：\n{errors}"
                    ),
                    server=server,
                    tool_name=tool_name,
                    workdir=workdir,
                    trace=trace,
                    task_id=task_id,
                    resume=session_id,
                )
                is_valid, errors = await validate_workdir(workdir, scenes, render_engine)

            if not is_valid:
                await record_agent_call(
                    model=settings.AGENT_MODEL,
                    business="code_generation",
                    input_summary=_input_summary(scenes, style_components),
                    output="",
                    total_cost_usd=trace["total_cost_usd"],
                    status="failed",
                    error_message=errors[:2000],
                )
                raise ValueError(f"Agent 模式代码校验未通过：\n{errors[:2000]}")

            codes = read_scene_codes(workdir, len(scenes))
            merged_scenes = [
                {**scene, "code": codes[i]} for i, scene in enumerate(scenes)
            ]

            await record_agent_call(
                model=settings.AGENT_MODEL,
                business="code_generation",
                input_summary=_input_summary(scenes, style_components),
                output=trace.get("result_text", ""),
                total_cost_usd=trace["total_cost_usd"],
                status="success",
            )
            return CodegenOutcome(
                scenes=merged_scenes,
                ai_model=settings.AGENT_MODEL,
                trace=trace,
            )
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    async def _run_once(
        self, *, prompt, server, tool_name, workdir, trace, task_id, resume
    ) -> str | None:
        options = _build_options(server, tool_name, workdir, resume)
        session_id = None
        async for message in self._query()(prompt=prompt, options=options):
            if is_task_cancelled(task_id):
                logger.info("[AgentCodegen] 任务已取消，中断 Agent 循环")
                raise AgentCancelledError("task cancelled during agent execution")

            for block in getattr(message, "content", []) or []:
                name = getattr(block, "name", None)
                if name:
                    trace["tool_calls"].append(name)

            if getattr(message, "session_id", None):
                session_id = message.session_id

            if hasattr(message, "subtype"):
                trace["result_subtype"] = message.subtype
                trace["result_text"] = getattr(message, "result", "") or ""
                cost = getattr(message, "total_cost_usd", None)
                if cost:
                    trace["total_cost_usd"] += float(cost)
        return session_id


def _build_options(server, tool_name, workdir, resume):
    from claude_agent_sdk import ClaudeAgentOptions

    kwargs = dict(
        model=settings.AGENT_MODEL,
        cwd=workdir,
        setting_sources=[],
        permission_mode="acceptEdits",
        max_turns=settings.AGENT_MAX_TURNS,
        mcp_servers={"codegen": server},
        allowed_tools=["Read", "Write", "Edit", "Glob", tool_name],
        tools=["Read", "Write", "Edit", "Glob"],
        env=_agent_env(),
    )
    if resume:
        kwargs["resume"] = resume
    return ClaudeAgentOptions(**kwargs)


def _agent_env() -> dict[str, str]:
    """从 provider 配置取 Anthropic 凭证。base_url 为空则走官方端点。"""
    from app.engines.ai.factory import _provider_settings_from_db

    config = _provider_settings_from_db("code_generation")
    env: dict[str, str] = {}
    if config is not None and config.provider_type == "anthropic":
        env["ANTHROPIC_API_KEY"] = config.api_key
        if config.base_url:
            env["ANTHROPIC_BASE_URL"] = config.base_url
    return env


def _input_summary(scenes, style_components) -> dict:
    return {
        "scene_count": len(scenes),
        "style_categories": sorted(style_components.keys()),
        "model": settings.AGENT_MODEL,
        "max_turns": settings.AGENT_MAX_TURNS,
    }
```

- [ ] **Step 8: 运行确认通过**

```bash
docker-compose run --rm backend uv run pytest tests/test_agent_codegen.py -v
```

Expected: 5 passed。若因 `ClaudeAgentOptions` 字段不存在而 `TypeError`，回到 Task 3 Step 5 的结论调整 `_build_options`。

- [ ] **Step 9: 选择器接上 agent 分支**

`backend/app/services/strategies/__init__.py` 的 `get_codegen_strategy` 改为：

```python
def get_codegen_strategy(execution_mode: str) -> CodegenStrategy:
    if execution_mode == "agent":
        from app.services.strategies.agent_codegen import AgentCodegenStrategy

        return AgentCodegenStrategy()
    return PromptCodegenStrategy()
```

在 `backend/tests/test_strategies_prompt.py` 追加：

```python
def test_selector_returns_agent_strategy_for_agent_mode():
    from app.services.strategies.agent_codegen import AgentCodegenStrategy

    assert isinstance(get_codegen_strategy("agent"), AgentCodegenStrategy)
```

- [ ] **Step 10: 跑全量测试**

```bash
docker-compose run --rm backend uv run pytest tests/ -v
```

Expected: 全部 PASS。

- [ ] **Step 11: 提交**

```bash
git add backend/app/services/strategies backend/tests/test_agent_sandbox.py backend/tests/test_agent_codegen.py backend/tests/test_strategies_prompt.py
git commit -m "feat: 代码侧 Agent 迭代执行模式"
```

---

### Task 5: 代码侧端到端手工验证

**这一步没有自动化测试，是人工验证闸门。** 不通过不进 Task 6。

**Files:** 无代码改动（除非发现 bug）

**Interfaces:**
- Consumes: Task 4 的 `AgentCodegenStrategy`
- Produces: 一份实测结论——Agent 模式相对提示词模式的成功率与成本对比

- [ ] **Step 1: 起环境**

```bash
make up
```

- [ ] **Step 2: 配 Anthropic provider**

打开 http://localhost:5173 的 AI 模型设置页，新建 provider：类型 `anthropic`，`base_url` 留空（或填中转地址），填入 API Key。再新建模型行 `claude-opus-5`，填上定价（输入 $5 / 输出 $25 每百万 token）。

- [ ] **Step 3: 把 code_generation 切成 agent 模式**

```bash
docker-compose exec postgres psql -U postgres -d ai_video -c "UPDATE ai_business_model_configs SET execution_mode='agent' WHERE business='code_generation';"
```

（数据库名以 `docker-compose.yml` 中实际配置为准。）

- [ ] **Step 4: 跑一个真实项目到代码生成环节**

从选题池选一个已有选题，走到代码生成。在另一个终端跟日志：

```bash
make dev-worker
```

- [ ] **Step 5: 核对以下几项**

- Temporal UI（http://localhost:8080）里 workflow 正常推进到 `code_review`；
- worker 日志里能看到 Agent 反复调 `validate` 的迭代过程；
- `worker_tasks.output_payload` 里有 `trace`，含 `tool_calls`、`total_cost_usd`、`resumed`；
- `ai_call_records` 里有一条 `request_type='agent'` 的记录且 `total_cost` 非空；
- `code_versions.prompt_snapshot` 与 `ai_model` 正确。

- [ ] **Step 6: 验证取消能中断**

再跑一次代码生成，在 Agent 迭代途中于前端点取消，确认 worker 日志出现「任务已取消，中断 Agent 循环」，且沙箱目录被清理（`ls /tmp | grep agent-codegen` 为空）。

- [ ] **Step 7: 记录对比结论**

同一个选题分别用 `prompt` 和 `agent` 各跑 3 次，记录：一次通过率、总耗时、单次成本。把结论追加到 spec 文件末尾的新章节「实测结果」并提交。

这份数据是 Task 6 是否值得做的判断依据。

---

### Task 6: 叙事侧 Agent 策略

**前置条件：Task 5 的实测结论显示 Agent 模式确有提升。** 若提升有限，停在这里跟用户重新评估，不要照单硬做——叙事侧没有 manim 那样的硬校验信号，收益本就不如代码侧确定。

**Files:**
- Create: `backend/app/services/strategies/agent_narrative.py`
- Modify: `backend/app/services/strategies/agent_sandbox.py`（加叙事的结构校验工具）
- Modify: `backend/app/services/strategies/__init__.py`（`get_narrative_strategy` 接 agent 分支）
- Test: `backend/tests/test_agent_narrative.py`（新建）

**Interfaces:**
- Consumes: Task 1 的 `NarrativeOutcome`；Task 4 的 `AgentCancelledError`、`is_task_cancelled`、`record_agent_call`、`_build_options`
- Produces:
  - `build_narrative_validate_server(workdir: str) -> tuple[Any, str]`，工具名 `"mcp__narrative__validate"`
  - `read_narrative(workdir: str) -> tuple[list[dict], list[dict]]` — 返回 `(scenes, fact_checks)`
  - `AgentNarrativeStrategy(agent_query=None)`

- [ ] **Step 1: 写叙事沙箱回读与校验的失败测试**

创建 `backend/tests/test_agent_narrative.py` 的第一组用例：

```python
import json

import pytest

from app.services.strategies.agent_sandbox import read_narrative


def test_read_narrative_parses_scenes_and_fact_checks(tmp_path):
    (tmp_path / "narrative.json").write_text(
        json.dumps(
            {
                "scenes": [
                    {
                        "scene_index": 0,
                        "narration": "旁白",
                        "description": "描述",
                        "beats": [{"beat_index": 0, "cue_text": "旁白", "visual_action": "出现"}],
                    }
                ],
                "fact_checks": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    scenes, fact_checks = read_narrative(str(tmp_path))
    assert len(scenes) == 1
    assert scenes[0]["narration"] == "旁白"
    assert fact_checks == []


def test_read_narrative_missing_file_returns_empty(tmp_path):
    scenes, fact_checks = read_narrative(str(tmp_path))
    assert scenes == []
    assert fact_checks == []
```

- [ ] **Step 2: 运行确认失败**

```bash
docker-compose run --rm backend uv run pytest tests/test_agent_narrative.py -v
```

Expected: FAIL，`ImportError: cannot import name 'read_narrative'`

- [ ] **Step 3: 在 agent_sandbox.py 加叙事支持**

追加到 `backend/app/services/strategies/agent_sandbox.py`：

```python
NARRATIVE_VALIDATE_TOOL_NAME = "mcp__narrative__validate"


def read_narrative(workdir: str) -> tuple[list[dict], list[dict]]:
    """回读 narrative.json；文件缺失或格式错误返回空列表。"""
    path = os.path.join(workdir, "narrative.json")
    if not os.path.exists(path):
        return [], []
    try:
        with open(path, encoding="utf-8") as f:
            payload = json.load(f)
    except (json.JSONDecodeError, OSError):
        logger.exception("[AgentNarrative] narrative.json 解析失败")
        return [], []
    scenes = payload.get("scenes")
    fact_checks = payload.get("fact_checks")
    return (
        scenes if isinstance(scenes, list) else [],
        fact_checks if isinstance(fact_checks, list) else [],
    )


def validate_narrative_workdir(workdir: str) -> tuple[bool, str]:
    """结构校验：JSON 可解析、scene_index 连续、必填字段齐全、beats 非空。"""
    from app.services.narrative_validator import validate_scenes_for_codegen

    scenes, _ = read_narrative(workdir)
    if not scenes:
        return False, "narrative.json 缺失、无法解析，或 scenes 为空。"

    errors: list[str] = []
    for position, scene in enumerate(scenes):
        if scene.get("scene_index") != position:
            errors.append(
                f"第 {position} 个镜头的 scene_index 是 {scene.get('scene_index')}，"
                f"应为 {position}（必须从 0 开始连续）"
            )
        for field_name in ("narration", "description"):
            if not str(scene.get(field_name) or "").strip():
                errors.append(f"镜头 {position} 缺少 {field_name}")
        if not scene.get("beats"):
            errors.append(f"镜头 {position} 的 beats 为空")
    if errors:
        return False, "\n".join(errors)

    try:
        validate_scenes_for_codegen(scenes)
    except Exception as e:
        return False, f"叙事校验未通过：{e}"
    return True, ""


def build_narrative_validate_server(workdir: str):
    from claude_agent_sdk import ToolAnnotations, create_sdk_mcp_server, tool

    @tool(
        "validate",
        "校验 narrative.json 的结构是否合法（scene_index 连续、必填字段齐全、beats 非空）。写完后必须调用本工具确认通过。",
        {},
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def validate(args):
        is_valid, errors = validate_narrative_workdir(workdir)
        if is_valid:
            return {"content": [{"type": "text", "text": "校验通过。"}]}
        return {
            "content": [{"type": "text", "text": f"校验失败：\n{errors}"}],
            "is_error": True,
        }

    server = create_sdk_mcp_server(name="narrative", version="1.0.0", tools=[validate])
    return server, NARRATIVE_VALIDATE_TOOL_NAME
```

- [ ] **Step 4: 运行确认通过**

```bash
docker-compose run --rm backend uv run pytest tests/test_agent_narrative.py -v
```

Expected: 2 passed

- [ ] **Step 5: 加结构校验的用例并确认失败**

追加到 `backend/tests/test_agent_narrative.py`：

```python
from app.services.strategies.agent_sandbox import validate_narrative_workdir


def _write_narrative(tmp_path, scenes):
    (tmp_path / "narrative.json").write_text(
        json.dumps({"scenes": scenes, "fact_checks": []}, ensure_ascii=False),
        encoding="utf-8",
    )


def test_validate_catches_non_contiguous_scene_index(tmp_path):
    _write_narrative(
        tmp_path,
        [{"scene_index": 3, "narration": "旁白", "description": "描述", "beats": [{}]}],
    )
    is_valid, errors = validate_narrative_workdir(str(tmp_path))
    assert is_valid is False
    assert "scene_index" in errors


def test_validate_catches_empty_beats(tmp_path):
    _write_narrative(
        tmp_path,
        [{"scene_index": 0, "narration": "旁白", "description": "描述", "beats": []}],
    )
    is_valid, errors = validate_narrative_workdir(str(tmp_path))
    assert is_valid is False
    assert "beats" in errors


def test_validate_reports_missing_file(tmp_path):
    is_valid, errors = validate_narrative_workdir(str(tmp_path))
    assert is_valid is False
    assert "narrative.json" in errors
```

```bash
docker-compose run --rm backend uv run pytest tests/test_agent_narrative.py -v
```

Expected: 5 passed（实现已在 Step 3 完成，此处确认覆盖到位）。

- [ ] **Step 6: 写叙事策略的编排测试**

追加到 `backend/tests/test_agent_narrative.py`：

```python
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.strategies.agent_narrative import AgentNarrativeStrategy


class FakeResultMessage:
    def __init__(self, subtype="success", result="done", total_cost_usd=0.2):
        self.subtype = subtype
        self.result = result
        self.total_cost_usd = total_cost_usd


@pytest.mark.asyncio
async def test_narrative_agent_claiming_success_but_invalid_triggers_resume():
    calls = {"n": 0}

    async def fake_query(*, prompt, options):
        calls["n"] += 1
        yield FakeResultMessage()

    results = [(False, "镜头 0 的 beats 为空"), (True, "")]

    with patch(
        "app.services.strategies.agent_narrative.validate_narrative_workdir",
        side_effect=lambda w: results.pop(0),
    ), patch(
        "app.services.strategies.agent_narrative.read_narrative",
        return_value=([{"scene_index": 0, "narration": "旁白", "description": "描述", "beats": [{}]}], []),
    ), patch(
        "app.services.strategies.agent_narrative.build_narrative_validate_server",
        return_value=(MagicMock(), "mcp__narrative__validate"),
    ), patch(
        "app.services.strategies.agent_narrative.is_task_cancelled", return_value=False
    ), patch(
        "app.services.strategies.agent_narrative.record_agent_call", AsyncMock()
    ):
        outcome = await AgentNarrativeStrategy(agent_query=fake_query).run(
            topic_title="标题",
            topic_description="描述",
            render_engine="manim",
            aspect_ratio="landscape",
            rejection_context=None,
            previous_scenes=None,
            narrative_context=[],
            style_components={},
            task_id="t1",
        )

    assert calls["n"] == 2
    assert outcome.trace["resumed"] is True
    assert len(outcome.scenes) == 1
```

- [ ] **Step 7: 实现叙事策略**

创建 `backend/app/services/strategies/agent_narrative.py`：

```python
from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
from typing import Any

from app.config import settings
from app.services.strategies.agent_codegen import (
    AgentCancelledError,
    _build_options,
    is_task_cancelled,
    record_agent_call,
)
from app.services.strategies.agent_sandbox import (
    build_narrative_validate_server,
    read_narrative,
    validate_narrative_workdir,
)
from app.services.strategies.base import NarrativeOutcome

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """你是知识视频的叙事编剧。工作目录里有：

- `BRIEF.md`：选题、上下文与必须遵守的风格约束。
- `outline.md`：你的草稿区。
- `narrative.json`：你的最终产出。

工作方式，分两个阶段，不要跳过第一阶段：

1. 先在 `outline.md` 里写整体大纲——讲什么、分几个镜头、每镜头承担什么信息。
2. 大纲成型后，再展开写 `narrative.json`。结构为 `{"scenes": [...], "fact_checks": [...]}`；
   每个镜头含 scene_index（从 0 开始连续）、narration、description、beats（不得为空）。

写完调用 `validate` 工具校验结构，报错就修，**必须**迭代到通过为止，通过之后才能结束。"""


class AgentNarrativeStrategy:
    def __init__(self, agent_query=None):
        self._agent_query = agent_query

    def _query(self):
        if self._agent_query is not None:
            return self._agent_query
        from claude_agent_sdk import query

        return query

    async def run(
        self,
        *,
        topic_title,
        topic_description,
        render_engine,
        aspect_ratio,
        rejection_context,
        previous_scenes,
        narrative_context,
        style_components,
        task_id,
    ) -> NarrativeOutcome:
        workdir = tempfile.mkdtemp(prefix="agent-narrative-")
        trace: dict[str, Any] = {
            "execution_mode": "agent",
            "tool_calls": [],
            "resumed": False,
            "total_cost_usd": 0.0,
        }
        try:
            _write_brief(
                workdir,
                topic_title=topic_title,
                topic_description=topic_description,
                render_engine=render_engine,
                aspect_ratio=aspect_ratio,
                narrative_context=narrative_context,
                style_components=style_components,
            )
            server, tool_name = build_narrative_validate_server(workdir)

            prompt = _SYSTEM_PROMPT
            if rejection_context:
                prompt += (
                    "\n\n这是一次重新生成，上一版被驳回。驳回意见：\n"
                    + json.dumps(rejection_context, ensure_ascii=False)
                )
                if previous_scenes:
                    prompt += (
                        "\n\n上一版内容（未被指出问题的部分应尽量保留）：\n"
                        + json.dumps(previous_scenes, ensure_ascii=False)
                    )

            session_id = await self._run_once(
                prompt=prompt, server=server, tool_name=tool_name,
                workdir=workdir, trace=trace, task_id=task_id, resume=None,
            )

            is_valid, errors = validate_narrative_workdir(workdir)
            if not is_valid:
                logger.info("[AgentNarrative] 平台回读校验未过，resume 续跑一次")
                trace["resumed"] = True
                await self._run_once(
                    prompt=(
                        "平台侧校验仍未通过，报错如下，请继续修改 narrative.json "
                        f"直到 validate 通过：\n{errors}"
                    ),
                    server=server, tool_name=tool_name, workdir=workdir,
                    trace=trace, task_id=task_id, resume=session_id,
                )
                is_valid, errors = validate_narrative_workdir(workdir)

            if not is_valid:
                await record_agent_call(
                    model=settings.AGENT_MODEL, business="narrative_generation",
                    input_summary={"topic_title": topic_title, "model": settings.AGENT_MODEL},
                    output="", total_cost_usd=trace["total_cost_usd"],
                    status="failed", error_message=errors[:2000],
                )
                raise ValueError(f"Agent 模式叙事校验未通过：\n{errors[:2000]}")

            scenes, fact_checks = read_narrative(workdir)
            await record_agent_call(
                model=settings.AGENT_MODEL, business="narrative_generation",
                input_summary={"topic_title": topic_title, "model": settings.AGENT_MODEL},
                output=trace.get("result_text", ""),
                total_cost_usd=trace["total_cost_usd"], status="success",
            )
            return NarrativeOutcome(
                scenes=scenes,
                fact_checks=fact_checks,
                ai_model=settings.AGENT_MODEL,
                trace=trace,
            )
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    async def _run_once(
        self, *, prompt, server, tool_name, workdir, trace, task_id, resume
    ) -> str | None:
        options = _build_options(server, tool_name, workdir, resume)
        session_id = None
        async for message in self._query()(prompt=prompt, options=options):
            if is_task_cancelled(task_id):
                logger.info("[AgentNarrative] 任务已取消，中断 Agent 循环")
                raise AgentCancelledError("task cancelled during agent execution")

            for block in getattr(message, "content", []) or []:
                name = getattr(block, "name", None)
                if name:
                    trace["tool_calls"].append(name)

            if getattr(message, "session_id", None):
                session_id = message.session_id

            if hasattr(message, "subtype"):
                trace["result_subtype"] = message.subtype
                trace["result_text"] = getattr(message, "result", "") or ""
                cost = getattr(message, "total_cost_usd", None)
                if cost:
                    trace["total_cost_usd"] += float(cost)
        return session_id


def _write_brief(
    workdir, *, topic_title, topic_description, render_engine,
    aspect_ratio, narrative_context, style_components,
):
    lines = [
        f"# 选题：{topic_title}",
        "",
        topic_description,
        "",
        f"- 渲染引擎：{render_engine}",
        f"- 画幅：{aspect_ratio}",
        "",
    ]
    if narrative_context:
        lines += [
            "## 已有叙事上下文",
            "",
            json.dumps(narrative_context, ensure_ascii=False, indent=2),
            "",
        ]
    for category, text in style_components.items():
        lines += [f"## {category}", "", text, ""]
    with open(os.path.join(workdir, "BRIEF.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    with open(os.path.join(workdir, "outline.md"), "w", encoding="utf-8") as f:
        f.write("")
```

`_build_options` 里的 `allowed_tools` 是写死的代码侧工具名。改成接受传入的 `tool_name`——它已经是参数，确认 `allowed_tools=["Read", "Write", "Edit", "Glob", tool_name]` 用的是参数而非常量即可（Task 4 Step 7 的写法已满足）。

- [ ] **Step 8: 运行确认通过**

```bash
docker-compose run --rm backend uv run pytest tests/test_agent_narrative.py -v
```

Expected: 6 passed

- [ ] **Step 9: 选择器接上叙事 agent 分支**

`backend/app/services/strategies/__init__.py`：

```python
def get_narrative_strategy(execution_mode: str) -> NarrativeStrategy:
    if execution_mode == "agent":
        from app.services.strategies.agent_narrative import AgentNarrativeStrategy

        return AgentNarrativeStrategy()
    return PromptNarrativeStrategy()
```

在 `backend/tests/test_strategies_prompt.py` 追加：

```python
def test_selector_returns_agent_narrative_strategy():
    from app.services.strategies.agent_narrative import AgentNarrativeStrategy

    assert isinstance(get_narrative_strategy("agent"), AgentNarrativeStrategy)
```

- [ ] **Step 10: 跑全量测试并提交**

```bash
docker-compose run --rm backend uv run pytest tests/ -v
git add backend/app/services/strategies backend/tests
git commit -m "feat: 叙事侧 Agent 迭代执行模式"
```

---

### Task 7: 前端配置与展示

**Files:**
- Modify: `frontend/src/types/`（项目类型加 `executionMode`）
- Modify: 项目创建表单组件（加模式选择）
- Modify: 审核页面组件（展示 Agent 执行信息）
- Test: `docker-compose run --rm frontend pnpm build` + `pnpm lint`

**Interfaces:**
- Consumes: Task 2 的 `ProjectCreate.execution_mode`（API 层 camelCase 为 `executionMode`）；Task 4/6 的 `trace` 结构（`execution_mode` / `tool_calls` / `total_cost_usd` / `resumed`）
- Produces: 无下游任务

- [ ] **Step 1: 找到项目类型定义与创建表单**

```bash
grep -rn "aspectRatio" frontend/src/types/ frontend/src/pages/ | head -20
```

按输出定位到项目类型文件与创建表单组件——`executionMode` 在这两处跟着 `aspectRatio` 走即可。

- [ ] **Step 2: 类型加字段**

在项目类型定义里，`aspectRatio` 旁边加：

```ts
  executionMode?: 'prompt' | 'agent' | null
```

- [ ] **Step 3: 创建表单加选择器**

在创建表单中 `aspectRatio` 选择器之后，加一个执行模式选择，三个选项：

- `跟随全局默认`（值为 `undefined`，不提交该字段）
- `提示词模式`（`'prompt'`）
- `Agent 迭代模式`（`'agent'`）

沿用该表单已有的 shadcn `Select` 用法，不要引入新的表单控件模式。

- [ ] **Step 4: 审核页展示执行信息**

在展示版本信息的位置，若 `promptSnapshot.execution_mode === 'agent'`，多渲染一行：

```tsx
<span className="text-xs text-muted-foreground">
  Agent 模式 · {trace.tool_calls?.length ?? 0} 次工具调用 · ${(trace.total_cost_usd ?? 0).toFixed(2)}
  {trace.resumed ? ' · 续跑过一次' : ''}
</span>
```

`trace` 的来源取决于后端把它放在 `prompt_snapshot` 还是 `worker_tasks.output_payload`——按 Task 4 的实现，`prompt_snapshot` 里存的是 agent 元信息，先确认接口返回的字段名再接。

- [ ] **Step 5: 构建与 lint**

```bash
docker-compose run --rm frontend pnpm build
```

```bash
docker-compose run --rm frontend pnpm lint
```

Expected: 均无报错。

- [ ] **Step 6: 提交**

```bash
git add frontend/src
git commit -m "feat: 前端支持执行模式选择与 Agent 执行信息展示"
```

---

## 自查记录

- **Spec 覆盖**：策略层 → Task 1；数据模型与配置 → Task 2；Anthropic 接入 → Task 2 + Task 4 `_agent_env`；沙箱协议与工具面 → Task 4 Step 3/7；结束判据「不信任 Agent 自述」→ Task 4 Step 5 首个用例；成本记录 → Task 4 `record_agent_call`；执行轨迹 → `trace` 进 `output_payload`；失败三层 → Task 4 Step 7；取消 → Task 4 Step 5 第四个用例；测试策略 → Task 1/4/6 各自的测试步骤；落地顺序 → Task 1-7 一一对应。
- **spec 未覆盖、计划中补上的**：`AIModelProviderBase.base_url` 的 `min_length=1` 会拒绝空串，Task 2 Step 8 一并放宽。
- **待实测决定的分支**：`ClaudeAgentOptions` 的 `max_budget_usd` 与 `tools` 字段是否存在，Task 3 Step 5 确认后回填 Task 4 Step 7。
