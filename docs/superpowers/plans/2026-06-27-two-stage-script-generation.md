# Two-Stage Script Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将脚本生成拆分为两阶段：先 AI 生成叙事脚本（旁白+画面描述），人工审核可内联编辑后，再 AI 一次性生成所有镜头渲染代码。

**Architecture:** 新增 `narrative_versions` 表和 `NarrativeVersion` ORM 模型存叙事脚本；新增 `NarrativeWorker`（task_type: `generate_narrative`）和 `CodeWorker`（task_type: `generate_code`）替换旧 `ScriptWorker`；Temporal Workflow 新增三个 signal 和两个 activity，重写主流程；后端 API 新增 `GET /narrative` 端点并扩展 review 端点支持 `gate="narrative"`；前端新增 `NarrativeReviewPanel` 组件并处理四个新状态。

**Tech Stack:** Python/FastAPI, SQLAlchemy, Alembic, Temporal, React/TypeScript, TanStack Query

## Global Constraints

- 命令路径：`/Users/peng/.local/bin/uv run pytest tests/ -v`（后端测试）
- 删除旧状态 `script_generating`、`script_failed`，新增 `narrative_generating`、`narrative_review`、`code_generating`、`narrative_failed`、`code_failed`
- 删除 `ScriptWorker`、`submit_script_generation_task` activity、`script_generated` signal
- 不改动 `brainstorm_topics`、`research_topic` 方法
- 所有新 API 端点均需要 `X-API-Key` 验证

---

### Task 1: DB Migration + ORM Model

**Files:**
- Create: `backend/app/models/narrative_version.py`
- Modify: `backend/app/models/project.py`
- Create: `backend/alembic/versions/XXXX_add_narrative_versions.py`（文件名以实际生成为准）
- Test: `backend/tests/test_models_narrative.py`（新建）

**Interfaces:**
- Produces: `NarrativeVersion` ORM 类，`VideoProject.current_narrative_version_id` 字段，供 Task 4、5、8 使用

- [ ] **Step 1: 创建 ORM Model**

新建 `backend/app/models/narrative_version.py`：

```python
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base


def utcnow():
    return datetime.now(timezone.utc)


class NarrativeVersion(Base):
    __tablename__ = "narrative_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    scenes: Mapped[Optional[list]] = mapped_column(JSONB)
    fact_checks: Mapped[Optional[list]] = mapped_column(JSONB)
    ai_model: Mapped[Optional[str]] = mapped_column(String(50))
    rejection_context: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
```

- [ ] **Step 2: 在 `VideoProject` 模型加列**

修改 `backend/app/models/project.py`，在 `current_video_asset_id` 下方加一行：

```python
current_narrative_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
    PGUUID(as_uuid=True)
)
```

- [ ] **Step 3: 确保 model 被 import（__init__.py）**

检查 `backend/app/models/__init__.py`，确认有以下导入（没有则添加）：

```python
from app.models.narrative_version import NarrativeVersion  # noqa
```

- [ ] **Step 4: 生成 Alembic migration**

```bash
cd backend
/Users/peng/.local/bin/uv run alembic revision --autogenerate -m "add_narrative_versions"
```

打开生成的 migration 文件，确认 `upgrade()` 包含：
1. `op.create_table("narrative_versions", ...)` 含所有字段
2. `op.add_column("video_projects", sa.Column("current_narrative_version_id", ...))`

如果 autogenerate 不完整，手动确保：

```python
def upgrade() -> None:
    op.create_table(
        "narrative_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("scenes", postgresql.JSONB()),
        sa.Column("fact_checks", postgresql.JSONB()),
        sa.Column("ai_model", sa.String(50)),
        sa.Column("rejection_context", postgresql.JSONB()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.add_column(
        "video_projects",
        sa.Column("current_narrative_version_id", postgresql.UUID(as_uuid=True)),
    )


def downgrade() -> None:
    op.drop_column("video_projects", "current_narrative_version_id")
    op.drop_table("narrative_versions")
```

- [ ] **Step 5: 运行 migration**

```bash
cd backend
/Users/peng/.local/bin/uv run alembic upgrade head
```

预期：成功，无 error。

- [ ] **Step 6: 写 smoke test 确认 model 可 import**

新建 `backend/tests/test_models_narrative.py`：

```python
from app.models.narrative_version import NarrativeVersion
from app.models.project import VideoProject


def test_narrative_version_model_has_expected_columns():
    cols = {c.key for c in NarrativeVersion.__table__.columns}
    assert "id" in cols
    assert "project_id" in cols
    assert "version_number" in cols
    assert "scenes" in cols
    assert "fact_checks" in cols
    assert "rejection_context" in cols


def test_video_project_has_narrative_version_id_column():
    cols = {c.key for c in VideoProject.__table__.columns}
    assert "current_narrative_version_id" in cols
```

- [ ] **Step 7: 运行测试**

```bash
cd backend
/Users/peng/.local/bin/uv run pytest tests/test_models_narrative.py -v
```

预期：2 PASSED。

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/narrative_version.py \
        backend/app/models/project.py \
        backend/app/models/__init__.py \
        backend/alembic/versions/ \
        backend/tests/test_models_narrative.py
git commit -m "feat: add narrative_versions table and ORM model"
```

---

### Task 2: Pydantic Schemas

**Files:**
- Create: `backend/app/schemas/narrative.py`
- Modify: `backend/app/schemas/review.py`
- Modify: `frontend/src/types/index.ts`

**Interfaces:**
- Produces: `NarrativeVersionSchema`（供 Task 8 API 使用），`EditedNarrativeScene`、更新后的 `ReviewRequest`（供 Task 8 review handler 使用），前端 `NarrativeVersion`、`NarrativeScene` 类型（供 Task 9 使用）

- [ ] **Step 1: 新建后端叙事 schema**

新建 `backend/app/schemas/narrative.py`：

```python
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from typing import Optional
from datetime import datetime
from uuid import UUID
from app.schemas.project import FactCheckItemSchema


class NarrativeSceneSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    scene_index: int
    narration: str
    description: str
    estimated_duration_seconds: Optional[float] = None


class NarrativeVersionSchema(BaseModel):
    model_config = ConfigDict(
        from_attributes=True, populate_by_name=True, alias_generator=to_camel
    )

    id: UUID
    project_id: UUID
    version_number: int
    scenes: Optional[list[NarrativeSceneSchema]]
    fact_checks: Optional[list[FactCheckItemSchema]]
    ai_model: Optional[str]
    created_at: datetime
```

- [ ] **Step 2: 更新 `ReviewRequest`（backend）**

修改 `backend/app/schemas/review.py`，替换为：

```python
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from typing import Literal, Optional


class FactCheckVerdict(BaseModel):
    index: int
    verdict: str
    note: str = ""


class EditedNarrativeScene(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    scene_index: int
    narration: str
    description: str
    estimated_duration_seconds: Optional[float] = None


class ReviewRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    gate: Literal["narrative", "script", "video"]
    verdict: Literal["approved", "rejected", "abandoned"]
    rejection_type: Optional[str] = None
    rejection_detail: Optional[str] = None
    target_stage: Optional[str] = None
    fact_check_verdicts: Optional[list[FactCheckVerdict]] = None
    edited_scenes: Optional[list[EditedNarrativeScene]] = None


class ReviewResponse(BaseModel):
    status: str
    project_id: str
```

- [ ] **Step 3: 更新前端类型**

在 `frontend/src/types/index.ts` 中：

1. 将 `ProjectStatus` 替换为：

```typescript
export type ProjectStatus =
  | "draft"
  | "narrative_generating"
  | "narrative_review"
  | "narrative_failed"
  | "code_generating"
  | "code_failed"
  | "script_review"
  | "video_generating"
  | "video_failed"
  | "video_review"
  | "published"
  | "abandoned";
```

2. 在 `// ═══ 视频项目 ═══` 区块下方新增：

```typescript
export interface NarrativeScene {
  sceneIndex: number;
  narration: string;
  description: string;
  estimatedDurationSeconds: number | null;
}

export interface NarrativeVersion {
  id: string;
  versionNumber: number;
  scenes: NarrativeScene[];
  factChecks: FactCheckItem[];
  aiModel: string | null;
  createdAt: string;
}
```

3. 将 `ReviewRequest` 中 `gate` 字段更新：

```typescript
export interface ReviewRequest {
  gate: "narrative" | "script" | "video";
  verdict: "approved" | "rejected" | "abandoned";
  rejectionType?: string;
  rejectionDetail?: string;
  targetStage?: "narrative" | "code";
  factCheckVerdicts?: Array<{
    index: number;
    verdict: "approved" | "rejected" | "needs_revision";
    note: string;
  }>;
  editedScenes?: Array<{
    sceneIndex: number;
    narration: string;
    description: string;
    estimatedDurationSeconds?: number | null;
  }>;
}
```

- [ ] **Step 4: 写 schema 测试**

新建 `backend/tests/test_schemas_narrative.py`：

```python
from app.schemas.narrative import NarrativeVersionSchema, NarrativeSceneSchema
from app.schemas.review import ReviewRequest, EditedNarrativeScene
from uuid import uuid4
from datetime import datetime, timezone


def test_narrative_version_schema_from_dict():
    data = {
        "id": str(uuid4()),
        "project_id": str(uuid4()),
        "version_number": 1,
        "scenes": [
            {
                "scene_index": 0,
                "narration": "旁白",
                "description": "描述",
                "estimated_duration_seconds": 8.0,
            }
        ],
        "fact_checks": [],
        "ai_model": "deepseek",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    schema = NarrativeVersionSchema.model_validate(data)
    assert schema.version_number == 1
    assert schema.scenes[0].scene_index == 0


def test_review_request_narrative_gate():
    req = ReviewRequest(
        gate="narrative",
        verdict="approved",
        edited_scenes=[
            EditedNarrativeScene(
                scene_index=0,
                narration="旁白修改",
                description="描述修改",
            )
        ],
    )
    assert req.gate == "narrative"
    assert req.edited_scenes[0].scene_index == 0


def test_review_request_script_gate_with_target_stage():
    req = ReviewRequest(gate="script", verdict="rejected", target_stage="code")
    assert req.target_stage == "code"
```

- [ ] **Step 5: 运行测试**

```bash
cd backend
/Users/peng/.local/bin/uv run pytest tests/test_schemas_narrative.py -v
```

预期：3 PASSED。

- [ ] **Step 6: 确认全量测试无回归**

```bash
cd backend
/Users/peng/.local/bin/uv run pytest tests/ -v
```

预期：全部 PASS（部分旧 test_reviews.py 可能因 ReviewRequest gate 字段变化而失败，下一步修复）。

如果 `test_reviews.py` 有 `gate: "script"` 相关测试失败，将 gate 断言更新到新 Literal 即可。

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/narrative.py \
        backend/app/schemas/review.py \
        backend/tests/test_schemas_narrative.py \
        frontend/src/types/index.ts
git commit -m "feat: add narrative schemas and update ReviewRequest/frontend types"
```

---

### Task 3: AI Provider — generate_narrative()

**Files:**
- Modify: `backend/app/engines/ai/base.py`
- Modify: `backend/app/engines/ai/chat_provider.py`
- Modify: `backend/app/engines/ai/stub.py`
- Test: `backend/tests/test_narrative_provider.py`（新建）

**Interfaces:**
- Consumes: 无新依赖
- Produces: `NarrativeResult` dataclass，`ChatAIProvider.generate_narrative(topic_title, topic_description, render_engine, rejection_context=None) -> NarrativeResult`，`StubProvider.generate_narrative(...) -> NarrativeResult`，供 Task 4 NarrativeWorker 使用

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/test_narrative_provider.py`：

```python
import pytest
from app.engines.ai.chat_provider import ChatAIProvider
from app.engines.ai.stub import StubChatClient
from app.engines.ai.base import NarrativeResult


def make_provider():
    return ChatAIProvider(client=StubChatClient())


@pytest.mark.asyncio
async def test_generate_narrative_returns_narrative_result():
    provider = make_provider()
    result = await provider.generate_narrative(
        topic_title="为什么天空是蓝色的",
        topic_description="瑞利散射原理",
        render_engine="manim",
    )
    assert isinstance(result, NarrativeResult)
    assert isinstance(result.scenes, list)
    assert isinstance(result.fact_checks, list)


@pytest.mark.asyncio
async def test_generate_narrative_with_rejection_context():
    provider = make_provider()
    result = await provider.generate_narrative(
        topic_title="测试",
        topic_description="描述",
        render_engine="manim",
        rejection_context={"rejection_detail": "内容太空洞"},
    )
    assert isinstance(result, NarrativeResult)


def test_narrative_prompt_no_code_field():
    """叙事 prompt 不应要求 AI 生成 code 字段"""
    prompt = ChatAIProvider._NARRATIVE_SYSTEM_PROMPT
    assert "code" not in prompt.lower().replace("渲染代码", "").replace("code_generating", "")
    assert "旁白" in prompt or "narration" in prompt
    assert "description" in prompt or "描述" in prompt
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd backend
/Users/peng/.local/bin/uv run pytest tests/test_narrative_provider.py -v
```

预期：FAILED（`NarrativeResult` 和 `generate_narrative` 尚未定义）。

- [ ] **Step 3: 在 base.py 添加 NarrativeResult**

在 `backend/app/engines/ai/base.py` 中，`ScriptGenerationResult` 下方添加：

```python
@dataclass
class NarrativeResult:
    scenes: list[dict]
    fact_checks: list[dict]
```

同时在 `AIProvider` Protocol 中添加方法签名（在 `generate_script` 后面）：

```python
    async def generate_narrative(
        self,
        topic_title: str,
        topic_description: str,
        render_engine: str,
        rejection_context: dict | None = None,
    ) -> NarrativeResult: ...
```

- [ ] **Step 4: 在 chat_provider.py 实现 generate_narrative()**

在 `ChatAIProvider` 类中，在 `generate_script` 方法后面添加类属性和方法：

```python
    _NARRATIVE_SYSTEM_PROMPT = """\
你是知识视频叙事脚本生成器。请严格输出 JSON object，不要输出 Markdown。

JSON 格式示例：
{
  "scenes": [
    {
      "scene_index": 0,
      "narration": "旁白文稿——控制节奏、娓娓道来",
      "description": "画面描述（明确标注进场/变形/退场/跨镜头衔接）",
      "estimated_duration_seconds": 8.0
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

【叙事要求】
- 整体娓娓道来，从一个反直觉的问题或现象切入，逐步建立知识体系
- 旁白（narration）负责讲解，每句话清晰有力，不空洞
- 镜头数量根据内容自然分配，通常 8-20 个镜头
- estimated_duration_seconds 根据旁白长度和画面复杂度估算（通常 5-12 秒/镜头）

【画面描述规范】
description 字段将直接用于后续代码生成，必须足够精确：
- 优先使用图形、公式、数轴、几何图示表达概念，而非纯文字说明
- 明确标注每个元素的进场方式（如：用 Create 绘制/用 Write 书写/用 FadeIn 淡入/用 GrowArrow 生长）
- 明确标注跨镜头复用：哪些元素保留给下一镜头、如何变形（Transform/ReplacementTransform/.animate）
- 明确标注退场：哪些元素在本镜头末尾 FadeOut/移出画面（不再使用的元素必须清场）
- 每帧实际显示的文字不超过 15 个汉字（关键词、数字、公式、简短标注）
- 可参考的 Manim 元素类型：Circle/Arrow/NumberLine/Axes/Graph/VGroup/MathTex/Text

【跨镜头衔接示例（description 写法）】
场景：标题在镜头 0 引入，镜头 1 缩小到顶部
- 镜头 0 description："黑色背景。用 Write 写出标题'...'. 结尾保留 title 对象供下一镜头使用。"
- 镜头 1 description："承接 title 对象，用 title.animate.scale(0.5).to_edge(UP) 移动到顶部。下方用 Create 绘制..."

要求：
- scenes 是镜头数组，scene_index 从 0 连续递增
- 每个镜头包含 narration、description、estimated_duration_seconds
- fact_checks 覆盖脚本中的关键事实论断和可能争议点
- 只能输出合法 JSON object\
"""

    async def generate_narrative(
        self,
        topic_title: str,
        topic_description: str,
        render_engine: str,
        rejection_context: dict | None = None,
    ) -> "NarrativeResult":
        from app.engines.ai.base import NarrativeResult

        user_payload: dict = {
            "topic_title": topic_title,
            "topic_description": topic_description,
            "render_engine": render_engine,
        }
        if rejection_context:
            user_payload["rejection_context"] = rejection_context
            user_note = "（注意：这是一次重新生成，请参考 rejection_context 中的驳回原因修正叙事结构）"
        else:
            user_note = ""

        content = await self.client.create_chat_completion(
            messages=[
                {"role": "system", "content": self._NARRATIVE_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"请为以下选题生成知识视频叙事脚本 JSON{user_note}：\n"
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
            raise ValueError("Narrative response must contain scenes and fact_checks arrays")
        return NarrativeResult(scenes=scenes, fact_checks=fact_checks)
```

- [ ] **Step 5: 更新 stub.py**

在 `StubProvider` 中，`generate_script` 方法下方添加：

```python
    async def generate_narrative(
        self,
        topic_title: str,
        topic_description: str,
        render_engine: str,
        rejection_context: dict | None = None,
    ) -> "NarrativeResult":
        from app.engines.ai.base import NarrativeResult
        await asyncio.sleep(0)
        return NarrativeResult(scenes=[], fact_checks=[])
```

同时更新 `StubChatClient.create_chat_completion` 返回的 JSON，使其包含 `codes` 字段（为 Task 4 的 generate_code 准备），将返回值改为：

```python
        response = {"scenes": [], "fact_checks": [], "codes": []}
        return json.dumps(response, ensure_ascii=False)
```

- [ ] **Step 6: 运行测试**

```bash
cd backend
/Users/peng/.local/bin/uv run pytest tests/test_narrative_provider.py -v
```

预期：3 PASSED。

- [ ] **Step 7: 运行全量测试**

```bash
cd backend
/Users/peng/.local/bin/uv run pytest tests/ -v
```

预期：全部 PASS。

- [ ] **Step 8: Commit**

```bash
git add backend/app/engines/ai/base.py \
        backend/app/engines/ai/chat_provider.py \
        backend/app/engines/ai/stub.py \
        backend/tests/test_narrative_provider.py
git commit -m "feat: add generate_narrative() to AI provider"
```

---

### Task 4: AI Provider — generate_code()

**Files:**
- Modify: `backend/app/engines/ai/base.py`
- Modify: `backend/app/engines/ai/chat_provider.py`
- Modify: `backend/app/engines/ai/stub.py`
- Test: `backend/tests/test_code_provider.py`（新建）

**Interfaces:**
- Consumes: `_ENGINE_CODE_PROMPTS`（已有），`parse_json_object`（已有）
- Produces: `CodeGenerationResult` dataclass，`ChatAIProvider.generate_code(scenes: list[dict], render_engine: str) -> CodeGenerationResult`，`StubProvider.generate_code(...) -> CodeGenerationResult`，供 Task 5 CodeWorker 使用

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/test_code_provider.py`：

```python
import pytest
from app.engines.ai.chat_provider import ChatAIProvider
from app.engines.ai.stub import StubChatClient
from app.engines.ai.base import CodeGenerationResult

SAMPLE_SCENES = [
    {
        "scene_index": 0,
        "narration": "天空是蓝色的",
        "description": "黑色背景，用 Write 写出标题",
        "estimated_duration_seconds": 5.0,
    },
    {
        "scene_index": 1,
        "narration": "这是因为瑞利散射",
        "description": "承接标题，缩小到顶部，绘制散射图示",
        "estimated_duration_seconds": 7.0,
    },
]


def make_provider():
    return ChatAIProvider(client=StubChatClient())


@pytest.mark.asyncio
async def test_generate_code_returns_code_generation_result():
    provider = make_provider()
    result = await provider.generate_code(scenes=SAMPLE_SCENES, render_engine="manim")
    assert isinstance(result, CodeGenerationResult)
    assert isinstance(result.codes, list)


@pytest.mark.asyncio
async def test_generate_code_stub_returns_empty_list():
    provider = make_provider()
    result = await provider.generate_code(scenes=SAMPLE_SCENES, render_engine="manim")
    # Stub returns empty codes list
    assert result.codes == []


def test_generate_code_prompt_contains_engine_rules():
    """代码生成使用引擎特定规范"""
    manim_prompt = ChatAIProvider._ENGINE_CODE_PROMPTS["manim"]
    assert "construct()" in manim_prompt
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd backend
/Users/peng/.local/bin/uv run pytest tests/test_code_provider.py -v
```

预期：FAILED（`CodeGenerationResult` 未定义）。

- [ ] **Step 3: 在 base.py 添加 CodeGenerationResult**

在 `NarrativeResult` 下方添加：

```python
@dataclass
class CodeGenerationResult:
    codes: list[str]
```

同时在 `AIProvider` Protocol 中添加方法签名（在 `generate_narrative` 后面）：

```python
    async def generate_code(
        self,
        scenes: list[dict],
        render_engine: str,
    ) -> CodeGenerationResult: ...
```

- [ ] **Step 4: 在 chat_provider.py 实现 generate_code()**

在 `generate_narrative` 方法后面添加：

```python
    async def generate_code(
        self,
        scenes: list[dict],
        render_engine: str,
    ) -> "CodeGenerationResult":
        from app.engines.ai.base import CodeGenerationResult

        engine_hint = self._ENGINE_CODE_PROMPTS.get(
            render_engine, self._ENGINE_CODE_PROMPT_FALLBACK
        )
        system_prompt = f"""\
你是知识视频代码生成器。请严格输出 JSON object，不要输出 Markdown。

你将收到一个知识视频的所有镜头叙事脚本，需要为每个镜头生成渲染代码片段。

JSON 格式：
{{
  "codes": [
    "镜头 0 的代码片段",
    "镜头 1 的代码片段"
  ]
}}

codes 数组长度必须与输入 scenes 数组长度完全一致，按 scene_index 顺序对应。

渲染引擎：{render_engine}
{engine_hint}

【代码拼合规则】
所有镜头的 code 片段将被渲染引擎按顺序拼合为单个执行单元，每段之间插入注释分隔符。
音频由渲染引擎在每个镜头开始时自动注入，code 里不处理音频。

要求：
- 严格按照每个镜头的 description 实现动画逻辑
- 充分利用跨镜头变量复用（前面镜头声明的变量在后续镜头中可直接使用）
- 每个 code 片段不写外层结构（详见各引擎规范）
- 只能输出合法 JSON object\
"""
        content = await self.client.create_chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": "请为以下镜头脚本生成渲染代码 JSON：\n"
                    + json.dumps({"scenes": scenes}, ensure_ascii=False),
                },
            ],
            response_format={"type": "json_object"},
            max_tokens=self.script_max_tokens,
        )
        payload = parse_json_object(content)
        codes = payload.get("codes")
        if not isinstance(codes, list):
            raise ValueError("Code generation response must contain codes array")
        return CodeGenerationResult(codes=codes)
```

- [ ] **Step 5: 更新 stub.py StubProvider**

在 `StubProvider` 中，`generate_narrative` 方法下方添加：

```python
    async def generate_code(
        self,
        scenes: list[dict],
        render_engine: str,
    ) -> "CodeGenerationResult":
        from app.engines.ai.base import CodeGenerationResult
        await asyncio.sleep(0)
        return CodeGenerationResult(codes=["" for _ in scenes])
```

- [ ] **Step 6: 运行测试**

```bash
cd backend
/Users/peng/.local/bin/uv run pytest tests/test_code_provider.py -v
```

预期：3 PASSED。

- [ ] **Step 7: 运行全量测试**

```bash
cd backend
/Users/peng/.local/bin/uv run pytest tests/ -v
```

预期：全部 PASS。

- [ ] **Step 8: Commit**

```bash
git add backend/app/engines/ai/base.py \
        backend/app/engines/ai/chat_provider.py \
        backend/app/engines/ai/stub.py \
        backend/tests/test_code_provider.py
git commit -m "feat: add generate_code() to AI provider"
```

---

### Task 5: NarrativeWorker + Activity

**Files:**
- Create: `backend/app/workers/narrative_worker.py`
- Modify: `backend/app/workflows/activities.py`（新增 `submit_narrative_task`）
- Test: `backend/tests/test_narrative_worker.py`（新建）

**Interfaces:**
- Consumes: `NarrativeVersion` ORM，`NarrativeResult`，`get_ai_provider()`，`get_sync_session()`
- Produces: `NarrativeWorker` class（task_type: `"generate_narrative"`），`submit_narrative_task` Temporal activity，供 Task 7 Workflow 使用

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/test_narrative_worker.py`：

```python
import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from app.workers.narrative_worker import NarrativeWorker
from app.engines.ai.base import NarrativeResult


def make_task(**kwargs):
    task = MagicMock()
    task.project_id = kwargs.get("project_id", uuid.uuid4())
    task.input_payload = kwargs.get("input_payload", {
        "topic_title": "测试选题",
        "topic_description": "测试描述",
        "render_engine": "manim",
        "rejection_context": None,
    })
    return task


@pytest.mark.asyncio
async def test_narrative_worker_supported_task_types():
    assert "generate_narrative" in NarrativeWorker.supported_task_types


@pytest.mark.asyncio
async def test_narrative_worker_execute_writes_narrative_version():
    task = make_task()
    mock_provider = AsyncMock()
    mock_provider.model_name = "stub-model"
    mock_provider.generate_narrative = AsyncMock(
        return_value=NarrativeResult(
            scenes=[{"scene_index": 0, "narration": "旁白", "description": "描述"}],
            fact_checks=[],
        )
    )

    mock_project = MagicMock()
    mock_project.id = task.project_id
    mock_project.current_narrative_version_id = None

    mock_db = MagicMock()
    mock_db.get.return_value = mock_project
    mock_db.execute.return_value.scalar.return_value = None

    with patch("app.workers.narrative_worker.get_ai_provider", return_value=mock_provider), \
         patch("app.workers.narrative_worker.get_sync_session", return_value=mock_db):
        worker = NarrativeWorker(worker_id="test", temporal_client=AsyncMock())
        result = await worker._execute(task)

    assert "narrative_version_id" in result
    assert result["scene_count"] == 1
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd backend
/Users/peng/.local/bin/uv run pytest tests/test_narrative_worker.py -v
```

预期：FAILED（`NarrativeWorker` 未定义）。

- [ ] **Step 3: 实现 NarrativeWorker**

新建 `backend/app/workers/narrative_worker.py`：

```python
import uuid
from sqlalchemy import func, select
from app.db import get_sync_session
from app.engines.ai.factory import get_ai_provider
from app.models.project import VideoProject
from app.models.narrative_version import NarrativeVersion
from app.workers.base import BaseWorker


class NarrativeWorker(BaseWorker):
    supported_task_types = ["generate_narrative"]

    async def _execute(self, task) -> dict:
        payload = task.input_payload or {}
        topic_title = payload.get("topic_title", "")
        topic_description = payload.get("topic_description", "")
        render_engine = payload.get("render_engine", "manim")
        rejection_context = payload.get("rejection_context")

        provider = get_ai_provider()
        result = await provider.generate_narrative(
            topic_title=topic_title,
            topic_description=topic_description,
            render_engine=render_engine,
            rejection_context=rejection_context,
        )

        db = get_sync_session()
        try:
            project = db.get(VideoProject, task.project_id)
            if project is None:
                raise ValueError(f"Project {task.project_id} not found")

            max_version = db.execute(
                select(func.max(NarrativeVersion.version_number)).where(
                    NarrativeVersion.project_id == task.project_id
                )
            ).scalar()
            next_version = (max_version or 0) + 1

            nv = NarrativeVersion(
                id=uuid.uuid4(),
                project_id=task.project_id,
                version_number=next_version,
                scenes=result.scenes,
                fact_checks=result.fact_checks,
                ai_model=provider.model_name,
                rejection_context=rejection_context,
            )
            db.add(nv)
            db.flush()

            project.current_narrative_version_id = nv.id
            db.commit()

            return {
                "narrative_version_id": str(nv.id),
                "scene_count": len(result.scenes),
                "fact_check_count": len(result.fact_checks),
            }
        finally:
            db.close()
```

- [ ] **Step 4: 添加 `submit_narrative_task` activity**

在 `backend/app/workflows/activities.py` 末尾添加（保留所有现有 activity，只新增）：

```python
@activity.defn
async def submit_narrative_task(project_id: str) -> None:
    db = get_sync_session()
    try:
        project = db.get(VideoProject, uuid.UUID(project_id))
        if project is None:
            return
        topic = db.get(Topic, project.topic_id)

        rejection_event = db.execute(
            select(ProjectEvent)
            .where(
                ProjectEvent.project_id == project.id,
                ProjectEvent.event_type == "review_rejected",
            )
            .order_by(desc(ProjectEvent.created_at))
        ).scalars().first()
        rejection_context = rejection_event.payload if rejection_event else None

        task = WorkerTask(
            project_id=project.id,
            task_type="generate_narrative",
            engine=project.render_engine,
            status="pending",
            input_payload={
                "topic_title": topic.title if topic else "",
                "topic_description": topic.description if topic else "",
                "render_engine": project.render_engine,
                "rejection_context": rejection_context,
            },
            temporal_workflow_id=f"video-production-{project_id}",
            signal_name="narrative_generated",
            max_retries=3,
        )
        db.add(task)
        db.commit()
    finally:
        db.close()
```

- [ ] **Step 5: 运行测试**

```bash
cd backend
/Users/peng/.local/bin/uv run pytest tests/test_narrative_worker.py -v
```

预期：2 PASSED。

- [ ] **Step 6: Commit**

```bash
git add backend/app/workers/narrative_worker.py \
        backend/app/workflows/activities.py \
        backend/tests/test_narrative_worker.py
git commit -m "feat: add NarrativeWorker and submit_narrative_task activity"
```

---

### Task 6: CodeWorker + Activity + Delete ScriptWorker

**Files:**
- Create: `backend/app/workers/code_worker.py`
- Modify: `backend/app/workflows/activities.py`（新增 `submit_code_task`，删除 `submit_script_generation_task`）
- Delete: `backend/app/workers/script_worker.py`
- Delete: `backend/tests/test_script_worker.py`
- Modify: `backend/app/workers/combined_worker.py`
- Test: `backend/tests/test_code_worker.py`（新建）

**Interfaces:**
- Consumes: `NarrativeVersion`、`ScriptVersion`、`CodeGenerationResult`、`get_ai_provider()`
- Produces: `CodeWorker` class（task_type: `"generate_code"`），`submit_code_task` activity，供 Task 7 Workflow 使用

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/test_code_worker.py`：

```python
import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from app.workers.code_worker import CodeWorker
from app.engines.ai.base import CodeGenerationResult


def make_task(**kwargs):
    task = MagicMock()
    task.project_id = kwargs.get("project_id", uuid.uuid4())
    task.input_payload = kwargs.get("input_payload", {"render_engine": "manim"})
    return task


@pytest.mark.asyncio
async def test_code_worker_supported_task_types():
    assert "generate_code" in CodeWorker.supported_task_types


@pytest.mark.asyncio
async def test_code_worker_execute_creates_script_version():
    task = make_task()
    narrative_scenes = [
        {"scene_index": 0, "narration": "旁白", "description": "描述", "estimated_duration_seconds": 5.0}
    ]

    mock_provider = AsyncMock()
    mock_provider.model_name = "stub-model"
    mock_provider.generate_code = AsyncMock(
        return_value=CodeGenerationResult(codes=["# code 0"])
    )

    mock_narrative = MagicMock()
    mock_narrative.scenes = narrative_scenes
    mock_narrative.fact_checks = []

    mock_project = MagicMock()
    mock_project.id = task.project_id
    mock_project.current_narrative_version_id = uuid.uuid4()
    mock_project.render_engine = "manim"
    mock_project.current_script_version_id = None

    mock_db = MagicMock()
    mock_db.get.side_effect = lambda model, pk: (
        mock_project if model.__name__ == "VideoProject" else mock_narrative
    )
    mock_db.execute.return_value.scalar.return_value = None

    with patch("app.workers.code_worker.get_ai_provider", return_value=mock_provider), \
         patch("app.workers.code_worker.get_sync_session", return_value=mock_db):
        worker = CodeWorker(worker_id="test", temporal_client=AsyncMock())
        result = await worker._execute(task)

    assert "script_version_id" in result
    assert result["scene_count"] == 1
    mock_db.add.assert_called_once()
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd backend
/Users/peng/.local/bin/uv run pytest tests/test_code_worker.py -v
```

预期：FAILED（`CodeWorker` 未定义）。

- [ ] **Step 3: 实现 CodeWorker**

新建 `backend/app/workers/code_worker.py`：

```python
import uuid
from sqlalchemy import func, select
from app.db import get_sync_session
from app.engines.ai.factory import get_ai_provider
from app.models.project import VideoProject
from app.models.narrative_version import NarrativeVersion
from app.models.script_version import ScriptVersion
from app.workers.base import BaseWorker


class CodeWorker(BaseWorker):
    supported_task_types = ["generate_code"]

    async def _execute(self, task) -> dict:
        payload = task.input_payload or {}
        render_engine = payload.get("render_engine", "manim")

        db = get_sync_session()
        try:
            project = db.get(VideoProject, task.project_id)
            if project is None:
                raise ValueError(f"Project {task.project_id} not found")

            narrative = db.get(NarrativeVersion, project.current_narrative_version_id)
            if narrative is None:
                raise ValueError("No narrative version found for project")

            scenes = list(narrative.scenes or [])
            fact_checks = list(narrative.fact_checks or [])

            provider = get_ai_provider()
            result = await provider.generate_code(
                scenes=scenes,
                render_engine=render_engine,
            )

            # Merge code into scenes (match by position / scene_index order)
            merged_scenes = []
            for i, scene in enumerate(scenes):
                code = result.codes[i] if i < len(result.codes) else ""
                merged_scenes.append({**scene, "code": code})

            max_version = db.execute(
                select(func.max(ScriptVersion.version_number)).where(
                    ScriptVersion.project_id == task.project_id
                )
            ).scalar()
            next_version = (max_version or 0) + 1

            sv = ScriptVersion(
                id=uuid.uuid4(),
                project_id=task.project_id,
                version_number=next_version,
                scenes=merged_scenes,
                fact_checks=fact_checks,
                render_engine=render_engine,
                ai_model=provider.model_name,
            )
            db.add(sv)
            db.flush()

            project.current_script_version_id = sv.id
            db.commit()

            return {
                "script_version_id": str(sv.id),
                "scene_count": len(merged_scenes),
                "fact_check_count": len(fact_checks),
            }
        finally:
            db.close()
```

- [ ] **Step 4: 添加 `submit_code_task` activity**

在 `backend/app/workflows/activities.py` 末尾添加：

```python
@activity.defn
async def submit_code_task(project_id: str) -> None:
    db = get_sync_session()
    try:
        project = db.get(VideoProject, uuid.UUID(project_id))
        if project is None:
            return
        task = WorkerTask(
            project_id=project.id,
            task_type="generate_code",
            engine=project.render_engine,
            status="pending",
            input_payload={"render_engine": project.render_engine},
            temporal_workflow_id=f"video-production-{project_id}",
            signal_name="code_generated",
            max_retries=3,
        )
        db.add(task)
        db.commit()
    finally:
        db.close()
```

然后**删除** `submit_script_generation_task` 函数（从 activities.py 中移除）。

- [ ] **Step 5: 删除旧文件**

```bash
rm backend/app/workers/script_worker.py
rm backend/tests/test_script_worker.py
```

- [ ] **Step 6: 运行测试**

```bash
cd backend
/Users/peng/.local/bin/uv run pytest tests/test_code_worker.py -v
```

预期：2 PASSED。

- [ ] **Step 7: Commit（暂不更新 combined_worker，Task 7 一并更新）**

```bash
git add backend/app/workers/code_worker.py \
        backend/app/workflows/activities.py \
        backend/tests/test_code_worker.py
git rm backend/app/workers/script_worker.py backend/tests/test_script_worker.py
git commit -m "feat: add CodeWorker, submit_code_task; delete ScriptWorker"
```

---

### Task 7: Temporal Workflow 改造

**Files:**
- Modify: `backend/app/workflows/video_production.py`（完全重写主流程）
- Modify: `backend/app/workers/combined_worker.py`（注册新 worker/activities，移除旧的）
- Test: `backend/tests/test_workflow.py`（新建）

**Interfaces:**
- Consumes: `submit_narrative_task`、`submit_code_task`、`submit_video_generation_task`、`update_project_status`、`check_and_increment_retry`
- Produces: 更新后的 `VideoProductionWorkflow`，信号 `narrative_generated`、`narrative_review`、`code_generated`（旧 `script_generated` 删除）

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/test_workflow.py`：

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.workflows.video_production import VideoProductionWorkflow


def test_workflow_has_narrative_generated_signal():
    wf = VideoProductionWorkflow()
    assert hasattr(wf, "narrative_generated")


def test_workflow_has_narrative_review_signal():
    wf = VideoProductionWorkflow()
    assert hasattr(wf, "narrative_review")


def test_workflow_has_code_generated_signal():
    wf = VideoProductionWorkflow()
    assert hasattr(wf, "code_generated")


def test_workflow_does_not_have_script_generated_signal():
    wf = VideoProductionWorkflow()
    assert not hasattr(wf, "script_generated")
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd backend
/Users/peng/.local/bin/uv run pytest tests/test_workflow.py -v
```

预期：`test_workflow_does_not_have_script_generated_signal` PASS，其余 3 个 FAILED。

- [ ] **Step 3: 重写 video_production.py**

完全替换 `backend/app/workflows/video_production.py` 内容：

```python
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from app.workflows.activities import (
        update_project_status,
        submit_narrative_task,
        submit_code_task,
        submit_video_generation_task,
        check_and_increment_retry,
    )

_ACTIVITY_OPTS = dict(
    start_to_close_timeout=timedelta(seconds=30),
    retry_policy=RetryPolicy(maximum_attempts=3),
)
_STATUS_OPTS = dict(
    start_to_close_timeout=timedelta(seconds=10),
    retry_policy=RetryPolicy(maximum_attempts=3),
)


@workflow.defn
class VideoProductionWorkflow:

    def __init__(self):
        self._signals: dict[str, list] = {}

    @workflow.signal
    async def narrative_generated(self, payload: dict) -> None:
        self._signals.setdefault("narrative_generated", []).append(payload)

    @workflow.signal
    async def narrative_review(self, payload: dict) -> None:
        self._signals.setdefault("narrative_review", []).append(payload)

    @workflow.signal
    async def code_generated(self, payload: dict) -> None:
        self._signals.setdefault("code_generated", []).append(payload)

    @workflow.signal
    async def script_review(self, payload: dict) -> None:
        self._signals.setdefault("script_review", []).append(payload)

    @workflow.signal
    async def render_completed(self, payload: dict) -> None:
        self._signals.setdefault("render_completed", []).append(payload)

    @workflow.signal
    async def video_review(self, payload: dict) -> None:
        self._signals.setdefault("video_review", []).append(payload)

    @workflow.signal
    async def cancel(self, payload: dict) -> None:
        self._signals.setdefault("cancel", []).append(payload)

    @workflow.run
    async def run(self, project_id: str) -> None:
        need_narrative = True

        # Phase 1 outer loop: narrative + code + script review
        while True:
            if need_narrative:
                narrative_result = await self._generate_and_review_narrative(project_id)
                if narrative_result == "abandoned":
                    await self._update_status(project_id, "abandoned")
                    return
                # narrative_result == "approved" → fall through to code generation

            code_result = await self._generate_code_and_review_script(project_id)
            if code_result == "approved":
                break
            elif code_result == "back_to_narrative":
                need_narrative = True
                continue
            elif code_result == "back_to_code":
                need_narrative = False
                continue
            elif code_result == "abandoned":
                await self._update_status(project_id, "abandoned")
                return

        # Phase 2: video generation loop
        while True:
            result = await self._generate_and_review_video(project_id)
            if result == "approved":
                break
            elif result == "abandoned":
                await self._update_status(project_id, "abandoned")
                return
            elif result == "back_to_script":
                # go back to narrative generation
                need_narrative = True
                while True:
                    if need_narrative:
                        narrative_result = await self._generate_and_review_narrative(project_id)
                        if narrative_result == "abandoned":
                            await self._update_status(project_id, "abandoned")
                            return
                    code_result = await self._generate_code_and_review_script(project_id)
                    if code_result == "approved":
                        break
                    elif code_result == "back_to_narrative":
                        need_narrative = True
                        continue
                    elif code_result == "back_to_code":
                        need_narrative = False
                        continue
                    elif code_result == "abandoned":
                        await self._update_status(project_id, "abandoned")
                        return

        await self._update_status(project_id, "published")

    async def _generate_and_review_narrative(self, project_id: str) -> str:
        await self._update_status(project_id, "narrative_generating")
        await workflow.execute_activity(
            submit_narrative_task, args=[project_id], **_ACTIVITY_OPTS
        )

        while True:
            result = await self._wait_signal("narrative_generated")
            if result["success"]:
                break
            can_retry = await workflow.execute_activity(
                check_and_increment_retry,
                args=[project_id, "narrative_generating", result.get("error", "")],
                **_STATUS_OPTS,
            )
            if not can_retry:
                await self._update_status(project_id, "narrative_failed")
                return "abandoned"
            await workflow.execute_activity(
                submit_narrative_task, args=[project_id], **_ACTIVITY_OPTS
            )

        await self._update_status(project_id, "narrative_review")
        review = await self._wait_signal("narrative_review")
        verdict = review.get("verdict")
        if verdict == "approved":
            return "approved"
        elif verdict == "abandoned":
            return "abandoned"
        # rejected → retry narrative
        return "rejected_retry"

    async def _generate_code_and_review_script(self, project_id: str) -> str:
        await self._update_status(project_id, "code_generating")
        await workflow.execute_activity(
            submit_code_task, args=[project_id], **_ACTIVITY_OPTS
        )

        while True:
            result = await self._wait_signal("code_generated")
            if result["success"]:
                break
            can_retry = await workflow.execute_activity(
                check_and_increment_retry,
                args=[project_id, "code_generating", result.get("error", "")],
                **_STATUS_OPTS,
            )
            if not can_retry:
                await self._update_status(project_id, "code_failed")
                return "abandoned"
            await workflow.execute_activity(
                submit_code_task, args=[project_id], **_ACTIVITY_OPTS
            )

        await self._update_status(project_id, "script_review")
        review = await self._wait_signal("script_review")
        verdict = review.get("verdict")
        if verdict == "approved":
            return "approved"
        elif verdict == "abandoned":
            return "abandoned"
        # rejected: check target_stage
        target = review.get("target_stage", "narrative")
        if target == "code":
            return "back_to_code"
        return "back_to_narrative"

    async def _generate_and_review_video(self, project_id: str) -> str:
        await self._update_status(project_id, "video_generating")
        await workflow.execute_activity(
            submit_video_generation_task, args=[project_id], **_ACTIVITY_OPTS
        )

        while True:
            result = await self._wait_signal("render_completed")
            if result["success"]:
                break
            can_retry = await workflow.execute_activity(
                check_and_increment_retry,
                args=[project_id, "video_generating", result.get("error", "")],
                **_STATUS_OPTS,
            )
            if not can_retry:
                await self._update_status(project_id, "video_failed")
                return "abandoned"
            await workflow.execute_activity(
                submit_video_generation_task, args=[project_id], **_ACTIVITY_OPTS
            )

        await self._update_status(project_id, "video_review")
        review = await self._wait_signal("video_review")
        verdict = review["verdict"]
        if verdict == "approved":
            return "approved"
        elif verdict == "abandoned":
            return "abandoned"
        return "back_to_script"

    async def _update_status(self, project_id: str, status: str) -> None:
        await workflow.execute_activity(
            update_project_status, args=[project_id, status], **_STATUS_OPTS
        )

    async def _wait_signal(self, name: str) -> dict:
        await workflow.wait_condition(
            lambda: bool(self._signals.get(name))
        )
        return self._signals[name].pop(0)
```

- [ ] **Step 4: 更新 combined_worker.py**

完全替换 `backend/app/workers/combined_worker.py`：

```python
"""
开发环境用合并 Worker。
单进程同时运行 Temporal Worker（Workflow + Activity）和 BaseWorker（任务轮询）。
"""
import asyncio
import logging
from temporalio.client import Client
from temporalio.worker import Worker as TemporalWorker
from app.workers.narrative_worker import NarrativeWorker
from app.workers.code_worker import CodeWorker
from app.workers.render_worker import RenderWorker
from app.workflows.video_production import VideoProductionWorkflow
from app.workflows.activities import (
    update_project_status,
    submit_narrative_task,
    submit_code_task,
    submit_video_generation_task,
    check_and_increment_retry,
)
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    logger.info("Connecting to Temporal at %s", settings.TEMPORAL_ADDRESS)
    client = await Client.connect(settings.TEMPORAL_ADDRESS)

    temporal_worker = TemporalWorker(
        client,
        task_queue=settings.TEMPORAL_TASK_QUEUE,
        workflows=[VideoProductionWorkflow],
        activities=[
            update_project_status,
            submit_narrative_task,
            submit_code_task,
            submit_video_generation_task,
            check_and_increment_retry,
        ],
    )

    narrative_worker = NarrativeWorker(
        worker_id="narrative-worker-01",
        temporal_client=client,
        poll_interval=2.0,
    )

    code_worker = CodeWorker(
        worker_id="code-worker-01",
        temporal_client=client,
        poll_interval=2.0,
    )

    render_worker = RenderWorker(
        worker_id="render-worker-01",
        temporal_client=client,
        poll_interval=2.0,
    )

    logger.info("Workers started.")
    await asyncio.gather(
        temporal_worker.run(),
        narrative_worker.run(),
        code_worker.run(),
        render_worker.run(),
    )


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 5: 运行测试**

```bash
cd backend
/Users/peng/.local/bin/uv run pytest tests/test_workflow.py -v
```

预期：4 PASSED。

- [ ] **Step 6: 运行全量测试**

```bash
cd backend
/Users/peng/.local/bin/uv run pytest tests/ -v
```

预期：全部 PASS（`test_activities.py` 若有 `submit_script_generation_task` 测试，删除对应测试函数）。

- [ ] **Step 7: Commit**

```bash
git add backend/app/workflows/video_production.py \
        backend/app/workers/combined_worker.py \
        backend/tests/test_workflow.py
git commit -m "feat: rewrite Temporal workflow for two-stage script generation"
```

---

### Task 8: Backend API

**Files:**
- Modify: `backend/app/api/projects.py`（新增 `GET /narrative`）
- Modify: `backend/app/api/reviews.py`（扩展 review handler 支持 `gate="narrative"`）
- Test: `backend/tests/test_api_narrative.py`（新建）

**Interfaces:**
- Consumes: `NarrativeVersion` ORM，`NarrativeVersionSchema`，`EditedNarrativeScene`，`ReviewRequest`
- Produces: `GET /api/projects/{id}/narrative`，扩展后的 `POST /api/projects/{id}/review`

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/test_api_narrative.py`：

```python
import pytest
from unittest.mock import MagicMock, AsyncMock
from uuid import uuid4
from datetime import datetime, timezone
from app.schemas.narrative import NarrativeVersionSchema


def make_project(**kwargs):
    p = MagicMock()
    p.id = kwargs.get("id", uuid4())
    p.topic_id = uuid4()
    p.status = "narrative_review"
    p.current_narrative_version_id = kwargs.get("narrative_version_id", uuid4())
    p.temporal_workflow_id = f"video-production-{p.id}"
    return p


def make_narrative_version(project_id, **kwargs):
    nv = MagicMock()
    nv.id = kwargs.get("id", uuid4())
    nv.project_id = project_id
    nv.version_number = 1
    nv.scenes = [
        {"scene_index": 0, "narration": "旁白", "description": "描述", "estimated_duration_seconds": 5.0}
    ]
    nv.fact_checks = []
    nv.ai_model = "deepseek"
    nv.created_at = datetime.now(timezone.utc)
    return nv


def test_get_narrative_not_found_project(client, auth_headers, mock_db):
    mock_db.get.return_value = None
    response = client.get(f"/api/projects/{uuid4()}/narrative", headers=auth_headers)
    assert response.status_code == 404


def test_get_narrative_no_narrative_yet(client, auth_headers, mock_db):
    project = make_project()
    project.current_narrative_version_id = None
    mock_db.get.return_value = project
    response = client.get(f"/api/projects/{project.id}/narrative", headers=auth_headers)
    assert response.status_code == 404


def test_get_narrative_returns_version(client, auth_headers, mock_db):
    project = make_project()
    nv = make_narrative_version(project.id)
    mock_db.get.side_effect = lambda model, pk: (
        project if "VideoProject" in str(model) else nv
    )
    response = client.get(f"/api/projects/{project.id}/narrative", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["versionNumber"] == 1


def test_review_narrative_approved_sends_signal(client, auth_headers, mock_db, mock_temporal):
    project = make_project()
    nv = make_narrative_version(project.id)
    mock_db.get.side_effect = lambda model, pk: (
        project if "VideoProject" in str(model) else nv
    )
    mock_db.commit = AsyncMock()
    mock_temporal.get_workflow_handle.return_value.signal = AsyncMock()

    response = client.post(
        f"/api/projects/{project.id}/review",
        headers=auth_headers,
        json={
            "gate": "narrative",
            "verdict": "approved",
            "editedScenes": [
                {"sceneIndex": 0, "narration": "修改旁白", "description": "修改描述"}
            ],
        },
    )
    assert response.status_code == 200
    mock_temporal.get_workflow_handle.return_value.signal.assert_awaited_once()
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd backend
/Users/peng/.local/bin/uv run pytest tests/test_api_narrative.py -v
```

预期：多个 FAILED（`/narrative` 端点不存在，review handler 未处理 narrative gate）。

- [ ] **Step 3: 在 projects.py 添加 GET /narrative 端点**

在 `backend/app/api/projects.py` 中，在现有 import 块添加：

```python
from app.models.narrative_version import NarrativeVersion
from app.schemas.narrative import NarrativeVersionSchema
```

然后在文件末尾（`record_performance` 路由前）添加：

```python
@router.get("/{project_id}/narrative", response_model=NarrativeVersionSchema)
async def get_current_narrative(
    project_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_api_key),
):
    project = await db.get(VideoProject, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.current_narrative_version_id:
        raise HTTPException(status_code=404, detail="No narrative generated yet")
    nv = await db.get(NarrativeVersion, project.current_narrative_version_id)
    if nv is None:
        raise HTTPException(status_code=404, detail="Narrative version not found")
    return nv
```

- [ ] **Step 4: 扩展 reviews.py 支持 gate="narrative"**

替换 `backend/app/api/reviews.py` 内容：

```python
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
from temporalio.client import Client as TemporalClient
from app.auth import verify_api_key
from app.db import get_async_session
from app.deps import get_temporal_client
from app.models.project import VideoProject
from app.models.narrative_version import NarrativeVersion
from app.models.script_version import ScriptVersion
from app.schemas.review import ReviewRequest

router = APIRouter(prefix="/api/projects", tags=["reviews"])


@router.post("/{project_id}/review")
async def submit_review(
    project_id: UUID,
    body: ReviewRequest,
    db: AsyncSession = Depends(get_async_session),
    temporal: TemporalClient = Depends(get_temporal_client),
    _=Depends(verify_api_key),
):
    project = await db.get(VideoProject, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.temporal_workflow_id:
        raise HTTPException(status_code=400, detail="Project has no active workflow")

    if body.gate == "narrative":
        # 若有内联编辑，更新叙事版本的 scenes
        if body.edited_scenes and project.current_narrative_version_id:
            nv = await db.get(NarrativeVersion, project.current_narrative_version_id)
            if nv and isinstance(nv.scenes, list):
                edited_map = {s.scene_index: s for s in body.edited_scenes}
                updated_scenes = []
                for scene in nv.scenes:
                    idx = scene.get("scene_index", -1)
                    if idx in edited_map:
                        edit = edited_map[idx]
                        updated_scenes.append({
                            **scene,
                            "narration": edit.narration,
                            "description": edit.description,
                            **({"estimated_duration_seconds": edit.estimated_duration_seconds}
                               if edit.estimated_duration_seconds is not None else {}),
                        })
                    else:
                        updated_scenes.append(scene)
                nv.scenes = updated_scenes
                flag_modified(nv, "scenes")
                await db.commit()

        signal_name = "narrative_review"

    elif body.gate == "script":
        # 写回 fact_check verdicts
        if body.fact_check_verdicts:
            sv = await db.get(ScriptVersion, project.current_script_version_id)
            if sv and isinstance(sv.fact_checks, list):
                fact_checks = list(sv.fact_checks)
                for v in body.fact_check_verdicts:
                    if 0 <= v.index < len(fact_checks):
                        fact_checks[v.index] = {
                            **dict(fact_checks[v.index]),
                            "reviewer_verdict": v.verdict,
                            "reviewer_note": v.note or None,
                        }
                sv.fact_checks = fact_checks
                flag_modified(sv, "fact_checks")
                await db.commit()

        signal_name = "script_review"

    else:  # video
        signal_name = "video_review"

    payload = {
        "verdict": body.verdict,
        "rejection_type": body.rejection_type,
        "rejection_detail": body.rejection_detail,
        "target_stage": body.target_stage,
    }

    handle = temporal.get_workflow_handle(project.temporal_workflow_id)
    await handle.signal(signal_name, payload)
    return {"status": "ok"}
```

- [ ] **Step 5: 运行测试**

```bash
cd backend
/Users/peng/.local/bin/uv run pytest tests/test_api_narrative.py -v
```

预期：4 PASSED。

- [ ] **Step 6: 运行全量测试**

```bash
cd backend
/Users/peng/.local/bin/uv run pytest tests/ -v
```

预期：全部 PASS。

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/projects.py \
        backend/app/api/reviews.py \
        backend/tests/test_api_narrative.py
git commit -m "feat: add GET /narrative endpoint and narrative gate in review handler"
```

---

### Task 9: Frontend — Types, API, NarrativeReviewPanel, Status Handling

**Files:**
- Modify: `frontend/src/lib/api.ts`（新增 fetchNarrative）
- Create: `frontend/src/hooks/useNarrative.ts`
- Create: `frontend/src/components/projects/NarrativeReviewPanel.tsx`
- Modify: `frontend/src/components/projects/ProjectSheet.tsx`（处理新状态，调整 script_review 驳回）

**Interfaces:**
- Consumes: `NarrativeVersion`、`NarrativeScene` 类型（Task 2），`GET /api/projects/{id}/narrative`（Task 8），`POST /api/projects/{id}/review` with `gate="narrative"`（Task 8）
- Produces: 完整的叙事审核 UI 和新状态处理

- [ ] **Step 1: 在 api.ts 添加 fetchNarrative**

在 `frontend/src/lib/api.ts` 末尾的 `api` 对象中（或独立导出），添加：

```typescript
export function fetchNarrative(projectId: string) {
  return api.get<import("@/types").NarrativeVersion>(
    `/api/projects/${projectId}/narrative`
  );
}
```

- [ ] **Step 2: 新建 useNarrative hook**

新建 `frontend/src/hooks/useNarrative.ts`：

```typescript
import { useQuery } from "@tanstack/react-query";
import { fetchNarrative } from "@/lib/api";

export function useNarrative(projectId: string) {
  return useQuery({
    queryKey: ["narrative", projectId],
    queryFn: () => fetchNarrative(projectId),
    enabled: !!projectId,
    retry: false,
  });
}
```

- [ ] **Step 3: 新建 NarrativeReviewPanel 组件**

新建 `frontend/src/components/projects/NarrativeReviewPanel.tsx`：

```tsx
import { useState } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { useSubmitReview } from "@/hooks/useProjects";
import type { NarrativeVersion, NarrativeScene } from "@/types";

interface Props {
  projectId: string;
  narrative: NarrativeVersion;
}

export function NarrativeReviewPanel({ projectId, narrative }: Props) {
  const submitReview = useSubmitReview();

  // Local editable state: map from scene_index to edited values
  const [editedScenes, setEditedScenes] = useState<
    Map<number, { narration: string; description: string }>
  >(
    new Map(
      narrative.scenes.map((s) => [
        s.sceneIndex,
        { narration: s.narration, description: s.description },
      ])
    )
  );

  const [rejectionDetail, setRejectionDetail] = useState("");
  const [showRejectInput, setShowRejectInput] = useState(false);

  const updateScene = (
    idx: number,
    field: "narration" | "description",
    value: string
  ) => {
    setEditedScenes((prev) => {
      const next = new Map(prev);
      next.set(idx, { ...next.get(idx)!, [field]: value });
      return next;
    });
  };

  const buildEditedScenes = () =>
    Array.from(editedScenes.entries()).map(([sceneIndex, vals]) => ({
      sceneIndex,
      ...vals,
    }));

  const handleApprove = () => {
    submitReview.mutate({
      projectId,
      gate: "narrative",
      verdict: "approved",
      editedScenes: buildEditedScenes(),
    });
  };

  const handleReject = () => {
    submitReview.mutate({
      projectId,
      gate: "narrative",
      verdict: "rejected",
      rejectionDetail,
      editedScenes: buildEditedScenes(),
    });
  };

  const handleAbandon = () => {
    submitReview.mutate({
      projectId,
      gate: "narrative",
      verdict: "abandoned",
    });
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex flex-1 overflow-hidden gap-4">
        {/* Left: scene list */}
        <ScrollArea className="flex-1">
          <div className="space-y-4 pr-2">
            {narrative.scenes.map((scene) => {
              const edited = editedScenes.get(scene.sceneIndex)!;
              return (
                <div
                  key={scene.sceneIndex}
                  className="border rounded-lg p-4 space-y-3"
                >
                  <div className="flex items-center gap-2">
                    <Badge variant="outline">镜头 {scene.sceneIndex}</Badge>
                    {scene.estimatedDurationSeconds && (
                      <span className="text-xs text-muted-foreground">
                        {scene.estimatedDurationSeconds}s
                      </span>
                    )}
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-medium text-muted-foreground">
                      旁白
                    </label>
                    <Textarea
                      value={edited.narration}
                      onChange={(e) =>
                        updateScene(scene.sceneIndex, "narration", e.target.value)
                      }
                      rows={3}
                      className="text-sm"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-medium text-muted-foreground">
                      画面描述
                    </label>
                    <Textarea
                      value={edited.description}
                      onChange={(e) =>
                        updateScene(scene.sceneIndex, "description", e.target.value)
                      }
                      rows={4}
                      className="text-sm"
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </ScrollArea>

        {/* Right: fact checks (read-only) */}
        <ScrollArea className="w-72 shrink-0">
          <div className="space-y-3 pr-1">
            <p className="text-xs font-medium text-muted-foreground">
              事实核查（将在代码审核阶段标注）
            </p>
            {narrative.factChecks.map((fc, i) => (
              <div key={i} className="border rounded-lg p-3 space-y-1">
                <p className="text-xs">{fc.claimText}</p>
                <Badge
                  variant={
                    fc.confidence === "high"
                      ? "default"
                      : fc.confidence === "low"
                      ? "destructive"
                      : "secondary"
                  }
                  className="text-xs"
                >
                  {fc.confidence}
                </Badge>
                <p className="text-xs text-muted-foreground">
                  {fc.sourceDescription}
                </p>
              </div>
            ))}
          </div>
        </ScrollArea>
      </div>

      {/* Bottom action bar */}
      <div className="border-t pt-4 mt-4 space-y-3">
        {showRejectInput && (
          <Textarea
            placeholder="请说明驳回原因..."
            value={rejectionDetail}
            onChange={(e) => setRejectionDetail(e.target.value)}
            rows={2}
          />
        )}
        <div className="flex gap-2">
          <Button
            onClick={handleApprove}
            disabled={submitReview.isPending}
            className="flex-1"
          >
            确认通过（进入代码生成）
          </Button>
          <Button
            variant="outline"
            onClick={() => {
              if (showRejectInput) {
                handleReject();
              } else {
                setShowRejectInput(true);
              }
            }}
            disabled={submitReview.isPending}
          >
            驳回重生成
          </Button>
          <Button
            variant="ghost"
            onClick={handleAbandon}
            disabled={submitReview.isPending}
          >
            废弃
          </Button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: 更新 useProjects hook（submitReview 支持 editedScenes）**

找到 `frontend/src/hooks/useProjects.ts`（或类似文件），确认 `useSubmitReview` 的 mutate 参数类型与 `ReviewRequest` 对齐，接受 `editedScenes` 字段。如果 hook 内部直接构造 body，确保透传 `editedScenes`。

检查当前实现：

```bash
grep -n "submitReview\|useSubmitReview\|submit_review\|fact_check_verdicts" /Users/peng/Me/Ai/ai-video/frontend/src/hooks/useProjects.ts
```

如果 `useSubmitReview` 的参数类型是 `ReviewRequest`（已在 Task 2 更新过 types/index.ts），无需额外修改。只需确认 `api.post` 的 body 直接使用传入参数即可。

- [ ] **Step 5: 更新 ProjectSheet.tsx 处理新状态**

在 `ProjectSheet.tsx` 中：

1. 在现有 imports 中添加：
```tsx
import { NarrativeReviewPanel } from "@/components/projects/NarrativeReviewPanel";
import { useNarrative } from "@/hooks/useNarrative";
```

2. 在组件内部，在 `useProjectScript` 下方添加：
```tsx
const { data: narrative } = useNarrative(displayProject?.id ?? "");
```

3. 找到渲染内容区域，在 `isScriptReview` 相关判断逻辑前增加叙事审核处理。当前状态判断模式（根据实际代码结构调整）：

```tsx
const isNarrativeReview = project?.status === "narrative_review";
const isNarrativeGenerating = project?.status === "narrative_generating";
const isCodeGenerating = project?.status === "code_generating";
```

4. 在渲染区域加入新状态的 UI（在现有 `isScriptReview` 块之前）：

```tsx
{isNarrativeGenerating && (
  <div className="flex items-center gap-2 text-muted-foreground py-8 justify-center">
    <span className="animate-spin">⏳</span>
    AI 正在生成叙事脚本…
  </div>
)}

{isNarrativeReview && narrative && (
  <NarrativeReviewPanel
    projectId={displayProject!.id}
    narrative={narrative}
  />
)}

{isCodeGenerating && (
  <div className="flex items-center gap-2 text-muted-foreground py-8 justify-center">
    <span className="animate-spin">⏳</span>
    AI 正在生成动画代码…
  </div>
)}
```

5. 在 `script_review` 驳回逻辑中，增加 `targetStage` 选项。找到现有驳回处理（`showRejectInput` 展开部分），添加 target_stage 下拉或 radio：

```tsx
{showRejectInput && (
  <div className="space-y-2">
    <Textarea
      placeholder="请说明驳回原因..."
      value={rejectionDetail}
      onChange={(e) => setRejectionDetail(e.target.value)}
      rows={2}
    />
    <div className="flex gap-4 text-sm">
      <label className="flex items-center gap-1">
        <input
          type="radio"
          name="targetStage"
          value="narrative"
          checked={targetStage === "narrative"}
          onChange={() => setTargetStage("narrative")}
        />
        重写叙事脚本
      </label>
      <label className="flex items-center gap-1">
        <input
          type="radio"
          name="targetStage"
          value="code"
          checked={targetStage === "code"}
          onChange={() => setTargetStage("code")}
        />
        仅重新生成代码
      </label>
    </div>
  </div>
)}
```

需要在组件顶部增加 state：`const [targetStage, setTargetStage] = useState<"narrative" | "code">("narrative");`

驳回提交时传入 `targetStage`：
```tsx
submitReview.mutate({
  projectId: displayProject!.id,
  gate: "script",
  verdict: "rejected",
  rejectionDetail,
  targetStage,
  factCheckVerdicts: buildVerdictList(),
});
```

- [ ] **Step 6: 前端构建验证**

```bash
cd frontend
PATH="/Users/peng/.nvm/versions/node/v24.11.0/bin:$PATH" pnpm build
```

预期：build 成功，无 TypeScript 错误。

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/api.ts \
        frontend/src/hooks/useNarrative.ts \
        frontend/src/components/projects/NarrativeReviewPanel.tsx \
        frontend/src/components/projects/ProjectSheet.tsx
git commit -m "feat: add NarrativeReviewPanel and new status handling in frontend"
```

---

## 自检：规格覆盖

| 规格要求 | 对应 Task |
|----------|-----------|
| narrative_versions 新表 | Task 1 |
| video_projects 加 current_narrative_version_id | Task 1 |
| NarrativeResult + generate_narrative() | Task 3 |
| CodeGenerationResult + generate_code() | Task 4 |
| NarrativeWorker + submit_narrative_task | Task 5 |
| CodeWorker + submit_code_task | Task 6 |
| 删除 ScriptWorker | Task 6 |
| Workflow 新增 3 个 signal，重写主流程 | Task 7 |
| combined_worker 更新 | Task 7 |
| GET /api/projects/{id}/narrative | Task 8 |
| review handler 支持 gate="narrative" | Task 8 |
| 叙事内联编辑写回 DB | Task 8 |
| 前端新 ProjectStatus 类型 | Task 2 |
| NarrativeVersion 前端类型 | Task 2 |
| useNarrative hook | Task 9 |
| NarrativeReviewPanel | Task 9 |
| narrative_generating/code_generating 状态展示 | Task 9 |
| script_review 驳回 target_stage | Task 9 |
