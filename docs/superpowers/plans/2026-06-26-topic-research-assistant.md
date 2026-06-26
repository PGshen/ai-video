# Topic Research Assistant Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在选题 TopicSheet 中嵌入 AI 研究助手对话面板，审核人可多轮对话查询背景知识，历史持久化到数据库。

**Architecture:** 后端新增 SSE 流式接口 `POST /api/topics/{id}/research`，通过 `AIProvider.research_topic()` 调用 LLM；前端 `ResearchChat` 组件用 `ReadableStream` 消费 SSE，使用 `simple-ai` 的 `ChatMessage` 组件渲染对话，TopicSheet 改为宽屏左右分栏布局。

**Tech Stack:** FastAPI SSE (`StreamingResponse`)、SQLAlchemy JSONB、Alembic、React、`@simple-ai/chat-message`（shadcn 风格）、`ReadableStream` fetch API

## Global Constraints

- Python 包管理用 `uv`，绝对路径：`/Users/peng/.local/bin/uv`
- Node/pnpm 需要前置 PATH：`PATH="/Users/peng/.nvm/versions/node/v24.11.0/bin:$PATH" pnpm`
- 不设数据库外键约束
- `simple-ai` 组件安装方式：`npx shadcn@latest add @simple-ai/chat-message`（文件复制到项目，无 npm 包依赖）
- **不引入** `@ai-sdk/react`
- 前端 camelCase 与后端 snake_case 通过 `alias_generator=to_camel` 自动转换
- 测试用 `mock_db` fixture（`AsyncMock`），不连真实数据库
- 每个 Task 结束必须 commit

---

## File Map

| 文件 | 操作 | 职责 |
|------|------|------|
| `backend/alembic/versions/<rev>_add_research_data.py` | 新建 | 迁移：topics 表加 research_data 列 |
| `backend/app/models/topic.py` | 修改 | 新增 `research_data` 字段 |
| `backend/app/schemas/topic.py` | 修改 | `TopicResponse` + `ResearchMessageRequest` |
| `backend/app/engines/ai/base.py` | 修改 | `AIProvider` 协议新增 `research_topic` |
| `backend/app/api/topics.py` | 修改 | 新增 SSE 路由 |
| `backend/tests/test_topics.py` | 修改 | 新增研究接口测试 |
| `frontend/src/types/index.ts` | 修改 | `Topic` 新增 `researchData` |
| `frontend/src/components/ui/side-panel.tsx` | 修改 | 支持 `wide` 尺寸 |
| `frontend/src/components/ui/chat-message.tsx` | 新建（shadcn install） | simple-ai ChatMessage 组件 |
| `frontend/src/components/topics/ResearchChat.tsx` | 新建 | 对话面板组件 |
| `frontend/src/components/topics/TopicSheet.tsx` | 修改 | 宽屏分栏布局，集成 ResearchChat |

---

### Task 1: DB Migration + Model + Schema

**Files:**
- Create: `backend/alembic/versions/<rev>_add_research_data_to_topics.py`
- Modify: `backend/app/models/topic.py`
- Modify: `backend/app/schemas/topic.py`

**Interfaces:**
- Produces:
  - `Topic.research_data: list` — JSONB 字段，默认 `[]`
  - `TopicResponse.research_data: list[dict]` — API 响应中包含
  - `ResearchMessageRequest(message: str, use_default_prompt: bool = False)` — 研究接口请求体

- [ ] **Step 1: 生成 Alembic migration**

```bash
cd backend && /Users/peng/.local/bin/uv run alembic revision --autogenerate -m "add_research_data_to_topics"
```

预期输出：`Generating .../versions/xxxx_add_research_data_to_topics.py`

记录生成的文件名中的 revision ID（下一步用到）。

- [ ] **Step 2: 检查并修正生成的 migration 文件**

打开生成的文件，确认 `upgrade()` 和 `downgrade()` 内容正确（autogenerate 有时需要手动修正 JSONB）。确保文件内容如下：

```python
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


def upgrade() -> None:
    op.add_column(
        "topics",
        sa.Column("research_data", JSONB(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("topics", "research_data")
```

- [ ] **Step 3: 更新 SQLAlchemy 模型**

修改 `backend/app/models/topic.py`，在现有 import 行加入 JSONB，并在 `needs_recheck` 字段后新增：

```python
# 在文件顶部已有的 import 中补充：
from sqlalchemy.dialects.postgresql import UUID as PGUUID, ARRAY, JSONB

# 在 needs_recheck 字段后新增：
research_data: Mapped[list] = mapped_column(
    JSONB, default=list, server_default="[]"
)
```

- [ ] **Step 4: 更新 `__init__` 默认值**

在 `Topic.__init__` 的 `kwargs.setdefault` 区块末尾补充：

```python
kwargs.setdefault("research_data", [])
```

- [ ] **Step 5: 更新 Pydantic Schema**

修改 `backend/app/schemas/topic.py`，在 `TopicResponse` 末尾新增字段，并在文件末尾新增请求体类：

```python
# TopicResponse 类内，在 needs_recheck 后新增：
research_data: list[dict] = []

# 文件末尾新增：
class ResearchMessageRequest(BaseModel):
    message: str = ""
    use_default_prompt: bool = False
```

- [ ] **Step 6: 写测试 — TopicResponse 包含 research_data**

在 `backend/tests/test_topics.py` 的 `make_topic()` 函数末尾补充：

```python
t.research_data = kwargs.get("research_data", [])
```

然后新增测试（在文件末尾追加）：

```python
def test_topic_response_includes_research_data(client, auth_headers, mock_db):
    topic = make_topic(research_data=[{"role": "user", "content": "hi", "createdAt": "2026-01-01T00:00:00Z"}])
    mock_db.execute.return_value.scalars.return_value.all.return_value = [topic]
    response = client.get("/api/topics", headers=auth_headers)
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert "researchData" in item
    assert item["researchData"][0]["role"] == "user"
```

- [ ] **Step 7: 运行测试确认通过**

```bash
cd backend && /Users/peng/.local/bin/uv run pytest tests/test_topics.py -v
```

预期：全部 PASS

- [ ] **Step 8: Commit**

```bash
git add backend/alembic/versions/ backend/app/models/topic.py backend/app/schemas/topic.py backend/tests/test_topics.py
git commit -m "feat: add research_data JSONB column to topics"
```

---

### Task 2: AIProvider Protocol Extension + Stub

**Files:**
- Modify: `backend/app/engines/ai/base.py`

**Interfaces:**
- Consumes: 无（纯协议定义）
- Produces:
  ```python
  async def research_topic(
      self,
      topic_title: str,
      topic_description: str,
      conversation_history: list[dict],
      new_message: str,
      use_default_prompt: bool = False,
  ) -> AsyncIterator[str]: ...
  ```

- [ ] **Step 1: 写测试 — stub 产出若干 chunk**

在 `backend/tests/` 新建 `test_ai_research.py`：

```python
import pytest
from unittest.mock import AsyncMock, MagicMock


class StubAIProvider:
    engine_name = "stub"
    model_name = "stub-model"

    async def generate_script(self, *args, **kwargs):
        pass

    async def research_topic(
        self,
        topic_title,
        topic_description,
        conversation_history,
        new_message,
        use_default_prompt=False,
    ):
        chunks = ["## 核心理论\n\n", "这是一个测试回复。"]
        for chunk in chunks:
            yield chunk


@pytest.mark.asyncio
async def test_stub_research_topic_yields_chunks():
    provider = StubAIProvider()
    chunks = []
    async for chunk in provider.research_topic(
        topic_title="测试选题",
        topic_description="描述",
        conversation_history=[],
        new_message="介绍核心理论",
    ):
        chunks.append(chunk)
    assert len(chunks) == 2
    assert "核心理论" in chunks[0]


@pytest.mark.asyncio
async def test_stub_research_topic_default_prompt():
    provider = StubAIProvider()
    chunks = []
    async for chunk in provider.research_topic(
        topic_title="测试选题",
        topic_description="描述",
        conversation_history=[],
        new_message="",
        use_default_prompt=True,
    ):
        chunks.append(chunk)
    assert len(chunks) > 0
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && /Users/peng/.local/bin/uv run pytest tests/test_ai_research.py -v
```

预期：PASS（StubAIProvider 已在测试文件中定义，此步验证 asyncio 环境可用）

- [ ] **Step 3: 更新 AIProvider Protocol**

修改 `backend/app/engines/ai/base.py` 全文如下：

```python
from typing import Protocol, AsyncIterator
from dataclasses import dataclass


@dataclass
class ScriptGenerationResult:
    scenes: list[dict]
    fact_checks: list[dict]


class AIProvider(Protocol):
    @property
    def engine_name(self) -> str: ...

    @property
    def model_name(self) -> str: ...

    async def generate_script(
        self,
        topic_title: str,
        topic_description: str,
        render_engine: str,
        rejection_context: dict | None = None,
    ) -> ScriptGenerationResult: ...

    async def research_topic(
        self,
        topic_title: str,
        topic_description: str,
        conversation_history: list[dict],
        new_message: str,
        use_default_prompt: bool = False,
    ) -> AsyncIterator[str]: ...
```

- [ ] **Step 4: 运行全量测试确认无回归**

```bash
cd backend && /Users/peng/.local/bin/uv run pytest tests/ -v
```

预期：全部 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/engines/ai/base.py backend/tests/test_ai_research.py
git commit -m "feat: extend AIProvider protocol with research_topic method"
```

---

### Task 3: Backend SSE API Endpoint

**Files:**
- Modify: `backend/app/api/topics.py`
- Modify: `backend/tests/test_topics.py`

**Interfaces:**
- Consumes:
  - `Topic.research_data: list` （Task 1）
  - `ResearchMessageRequest(message: str, use_default_prompt: bool)` （Task 1）
- Produces: `POST /api/topics/{topic_id}/research` → `text/event-stream`

- [ ] **Step 1: 写测试 — 研究接口返回 SSE 流**

在 `backend/tests/test_topics.py` 末尾追加：

```python
def test_research_topic_streams_response(client, auth_headers, mock_db):
    from unittest.mock import patch

    topic = make_topic(
        title="量子纠缠",
        description="粒子间的神秘关联",
        research_data=[],
    )
    mock_db.get = AsyncMock(return_value=topic)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    async def fake_research(*args, **kwargs):
        for chunk in ["## 核心理论\n", "量子纠缠是..."]:
            yield chunk

    with patch(
        "app.api.topics.get_ai_provider",
        return_value=type("P", (), {"research_topic": lambda self, **kw: fake_research(**kw)})(),
    ):
        response = client.post(
            f"/api/topics/{topic.id}/research",
            headers=auth_headers,
            json={"message": "介绍核心理论", "use_default_prompt": False},
        )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    body = response.text
    assert "data: " in body
    assert "[DONE]" in body


def test_research_topic_404_when_not_found(client, auth_headers, mock_db):
    mock_db.get = AsyncMock(return_value=None)
    response = client.post(
        f"/api/topics/00000000-0000-0000-0000-000000000000/research",
        headers=auth_headers,
        json={"message": "test"},
    )
    assert response.status_code == 404


def test_research_topic_default_prompt(client, auth_headers, mock_db):
    from unittest.mock import patch

    topic = make_topic(title="黑洞", description="时空曲率极大处", research_data=[])
    mock_db.get = AsyncMock(return_value=topic)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    received_kwargs = {}

    async def fake_research(**kwargs):
        received_kwargs.update(kwargs)
        yield "测试内容"

    with patch(
        "app.api.topics.get_ai_provider",
        return_value=type("P", (), {"research_topic": lambda self, **kw: fake_research(**kw)})(),
    ):
        client.post(
            f"/api/topics/{topic.id}/research",
            headers=auth_headers,
            json={"use_default_prompt": True},
        )
    assert received_kwargs.get("use_default_prompt") is True
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && /Users/peng/.local/bin/uv run pytest tests/test_topics.py::test_research_topic_streams_response -v
```

预期：FAIL（路由不存在，404）

- [ ] **Step 3: 实现 SSE 路由**

在 `backend/app/api/topics.py` 顶部 import 区域补充：

```python
from datetime import datetime, timezone
from fastapi.responses import StreamingResponse
from app.schemas.topic import (
    TopicCreate, TopicUpdate, TopicResponse, TopicListResponse,
    BrainstormRequest, BrainstormResponse, ResearchMessageRequest,
)
```

在文件末尾，`update_topic` 路由之后新增：

```python
DEFAULT_RESEARCH_SYSTEM_PROMPT = """\
你是一位知识视频选题研究助手。当前研究的选题是：

标题：{topic_title}
描述：{topic_description}

请围绕该选题提供背景资料，内容以 Markdown 格式输出，重点包括：核心概念、相关理论、反直觉角度、可视化潜力等。\
"""

DEFAULT_RESEARCH_QUESTION = "请介绍这个选题的背景知识和核心理论"


def get_ai_provider():
    """Returns the active AI provider. Replace with real implementation in Sprint 2."""
    from app.engines.ai.base import AIProvider

    class StubProvider:
        engine_name = "stub"
        model_name = "stub-model"

        async def generate_script(self, *args, **kwargs):
            from app.engines.ai.base import ScriptGenerationResult
            return ScriptGenerationResult(scenes=[], fact_checks=[])

        async def research_topic(
            self,
            topic_title: str,
            topic_description: str,
            conversation_history: list[dict],
            new_message: str,
            use_default_prompt: bool = False,
        ):
            import asyncio
            if use_default_prompt:
                chunks = [
                    f"## {topic_title} — 背景资料\n\n",
                    "**核心概念：** 这是一个由 AI Stub 生成的占位回复。\n\n",
                    "Sprint 2 接入真实 LLM 后将替换此内容。",
                ]
            else:
                chunks = [f"你问的是：{new_message}\n\n", "（Stub 回复，Sprint 2 替换）"]
            for chunk in chunks:
                await asyncio.sleep(0)
                yield chunk

    return StubProvider()


@router.post("/{topic_id}/research")
async def research_topic(
    topic_id: UUID,
    body: ResearchMessageRequest,
    db: AsyncSession = Depends(get_async_session),
    _=Depends(verify_api_key),
):
    topic = await db.get(Topic, topic_id)
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")

    history: list[dict] = topic.research_data or []
    conversation_history = [{"role": m["role"], "content": m["content"]} for m in history]

    if body.use_default_prompt:
        system_prompt = DEFAULT_RESEARCH_SYSTEM_PROMPT.format(
            topic_title=topic.title,
            topic_description=topic.description or "",
        )
        user_message = DEFAULT_RESEARCH_QUESTION
    else:
        system_prompt = None
        user_message = body.message

    provider = get_ai_provider()

    async def event_stream():
        full_response = []
        try:
            async for chunk in provider.research_topic(
                topic_title=topic.title,
                topic_description=topic.description or "",
                conversation_history=conversation_history,
                new_message=user_message,
                use_default_prompt=body.use_default_prompt,
            ):
                full_response.append(chunk)
                yield f"data: {chunk}\n\n"

            now = datetime.now(timezone.utc).isoformat()
            new_history = list(history) + [
                {"role": "user", "content": user_message, "createdAt": now},
                {"role": "assistant", "content": "".join(full_response), "createdAt": now},
            ]
            topic.research_data = new_history
            await db.commit()
        except Exception as e:
            yield f"data: [ERROR] {e}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd backend && /Users/peng/.local/bin/uv run pytest tests/test_topics.py -v
```

预期：全部 PASS

- [ ] **Step 5: 运行全量测试确认无回归**

```bash
cd backend && /Users/peng/.local/bin/uv run pytest tests/ -v
```

预期：全部 PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/topics.py backend/tests/test_topics.py
git commit -m "feat: add SSE research endpoint POST /api/topics/{id}/research"
```

---

### Task 4: Frontend Types + SidePanel Width + Install simple-ai

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/components/ui/side-panel.tsx`
- Create: `frontend/src/components/ui/chat-message.tsx`（shadcn install）

**Interfaces:**
- Produces:
  - `Topic.researchData: ResearchMessage[]`（`ResearchMessage = {role, content, createdAt}`）
  - `SidePanel` 接受 `wide?: boolean` prop，`wide=true` 时宽度为 `w-[860px]`
  - `ChatMessage` 等组件从 `@/components/ui/chat-message` 导入

- [ ] **Step 1: 更新前端 Topic 类型**

修改 `frontend/src/types/index.ts`，在 `Topic` interface 中，`needsRecheck` 之前新增：

```typescript
export interface ResearchMessage {
  role: "user" | "assistant";
  content: string;
  createdAt: string;
}
```

并在 `Topic` interface 末尾（`needsRecheck` 后）新增：

```typescript
  researchData: ResearchMessage[];
```

- [ ] **Step 2: 更新 SidePanel 支持宽屏**

修改 `frontend/src/components/ui/side-panel.tsx`，将 `SidePanelProps` 和 `SidePanel` 函数改为：

```typescript
interface SidePanelProps {
  open: boolean;
  onClose: () => void;
  children: React.ReactNode;
  className?: string;
  wide?: boolean;
}

export function SidePanel({ open, onClose, children, className, wide = false }: SidePanelProps) {
```

将 Panel div 中的宽度类从：

```typescript
          width,
          "sm:max-w-[460px]",
```

改为：

```typescript
          wide ? "w-[860px] max-w-[95vw]" : "w-[460px] max-w-[95vw]",
```

（同时删除原来 `width` prop 的接口定义和默认值）

- [ ] **Step 3: 安装 simple-ai ChatMessage 组件**

```bash
cd frontend && PATH="/Users/peng/.nvm/versions/node/v24.11.0/bin:$PATH" npx shadcn@latest add @simple-ai/chat-message
```

预期：在 `frontend/src/components/ui/` 下生成 `chat-message.tsx`（及可能的依赖组件）。

如果安装过程有交互提示，选择确认安装。

- [ ] **Step 4: 确认组件可用**

```bash
ls frontend/src/components/ui/chat-message* 2>/dev/null || echo "NOT FOUND"
```

预期：显示 `chat-message.tsx` 路径。

若文件不存在（网络或 CLI 问题），手动创建最小可用版本：

```bash
# 仅在上一步失败时执行
```

```typescript
// frontend/src/components/ui/chat-message.tsx
// 手动创建最小版 — 正式安装时删除此文件替换为 simple-ai 版本

import ReactMarkdown from "react-markdown";

export function ChatMessageMarkdown({ content }: { content: string }) {
  return <ReactMarkdown>{content}</ReactMarkdown>;
}
export function ChatMessage({ children }: { children: React.ReactNode }) {
  return <div className="py-3">{children}</div>;
}
export function ChatMessageContent({ children }: { children: React.ReactNode }) {
  return <div className="text-sm">{children}</div>;
}
```

（若使用手动版本，需额外安装：`PATH="..." pnpm add react-markdown`）

- [ ] **Step 5: 确认 TypeScript 编译通过**

```bash
cd frontend && PATH="/Users/peng/.nvm/versions/node/v24.11.0/bin:$PATH" pnpm tsc --noEmit
```

预期：无错误输出

- [ ] **Step 6: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/components/ui/side-panel.tsx frontend/src/components/ui/chat-message*
git commit -m "feat: add ResearchMessage type, wide SidePanel, install simple-ai chat-message"
```

---

### Task 5: ResearchChat Component + TopicSheet Layout

**Files:**
- Create: `frontend/src/components/topics/ResearchChat.tsx`
- Modify: `frontend/src/components/topics/TopicSheet.tsx`

**Interfaces:**
- Consumes:
  - `Topic` with `researchData: ResearchMessage[]`（Task 4）
  - `SidePanel` with `wide?: boolean`（Task 4）
  - `ChatMessage*` components from `@/components/ui/chat-message`（Task 4）
  - `POST /api/topics/{id}/research` SSE endpoint（Task 3）
- Produces: 完整的研究助手对话界面，嵌入 TopicSheet 左栏

- [ ] **Step 1: 创建 ResearchChat.tsx**

新建 `frontend/src/components/topics/ResearchChat.tsx`：

```typescript
import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { SendHorizontal } from "lucide-react";
import type { Topic, ResearchMessage } from "@/types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const API_KEY = import.meta.env.VITE_API_KEY ?? "";

interface ChatEntry {
  id: string;
  role: "user" | "assistant";
  text: string;
}

function toEntries(messages: ResearchMessage[]): ChatEntry[] {
  return messages.map((m, i) => ({
    id: String(i),
    role: m.role,
    text: m.content,
  }));
}

interface Props {
  topic: Topic;
}

export function ResearchChat({ topic }: Props) {
  const [entries, setEntries] = useState<ChatEntry[]>(() =>
    toEntries(topic.researchData ?? [])
  );
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [entries]);

  // Re-sync when topic changes (panel re-opened with different topic)
  useEffect(() => {
    setEntries(toEntries(topic.researchData ?? []));
  }, [topic.id]);

  async function send(message: string, useDefaultPrompt: boolean) {
    const userEntry: ChatEntry = {
      id: Date.now() + "-u",
      role: "user",
      text: useDefaultPrompt ? "请介绍这个选题的背景知识和核心理论" : message,
    };
    const assistantEntry: ChatEntry = {
      id: Date.now() + "-a",
      role: "assistant",
      text: "",
    };
    setEntries((prev) => [...prev, userEntry, assistantEntry]);
    setInput("");
    setStreaming(true);

    try {
      const res = await fetch(`${BASE_URL}/api/topics/${topic.id}/research`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": API_KEY,
        },
        body: JSON.stringify({ message, use_default_prompt: useDefaultPrompt }),
      });

      if (!res.ok || !res.body) return;

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const payload = line.slice(6);
          if (payload === "[DONE]" || payload.startsWith("[ERROR]")) break;
          setEntries((prev) =>
            prev.map((e) =>
              e.id === assistantEntry.id
                ? { ...e, text: e.text + payload }
                : e
            )
          );
        }
      }
    } finally {
      setStreaming(false);
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim() || streaming) return;
    send(input.trim(), false);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!input.trim() || streaming) return;
      send(input.trim(), false);
    }
  }

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Messages area */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto space-y-4 pr-1"
      >
        {entries.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full gap-3 text-center">
            <p className="text-sm text-muted-foreground">
              使用 AI 查询该选题的背景资料，辅助打分判断
            </p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => send("", true)}
              disabled={streaming}
            >
              查询背景资料
            </Button>
          </div>
        ) : (
          entries.map((entry) => <MessageBubble key={entry.id} entry={entry} />)
        )}
      </div>

      {/* Input area */}
      <form onSubmit={handleSubmit} className="flex gap-2 pt-3 border-t mt-3">
        <Textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入问题，Enter 发送，Shift+Enter 换行"
          className="resize-none text-sm min-h-[40px] max-h-[120px]"
          rows={1}
          disabled={streaming}
        />
        <Button
          type="submit"
          size="icon"
          disabled={!input.trim() || streaming}
          className="shrink-0 self-end"
        >
          <SendHorizontal className="w-4 h-4" />
        </Button>
      </form>
    </div>
  );
}
```

- [ ] **Step 2: 创建 MessageBubble 子组件（追加到同文件）**

在 `ResearchChat.tsx` 末尾追加（在 export 之前加入 import，在组件定义之后）：

在文件顶部 import 区域补充：

```typescript
import ReactMarkdown from "react-markdown";
```

在 `ResearchChat` 函数定义之前插入：

```typescript
function MessageBubble({ entry }: { entry: ChatEntry }) {
  if (entry.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="bg-muted rounded-lg px-3 py-2 text-sm max-w-[85%]">
          {entry.text}
        </div>
      </div>
    );
  }
  return (
    <div className="prose prose-sm dark:prose-invert max-w-none text-sm">
      <ReactMarkdown>{entry.text || "▋"}</ReactMarkdown>
    </div>
  );
}
```

> **注意：** 若 `simple-ai` 的 `ChatMessageMarkdown` 可直接替换 `ReactMarkdown`，则将上述 `ReactMarkdown` 替换为 `ChatMessageMarkdown`，删除 `react-markdown` import。

- [ ] **Step 3: 安装 react-markdown（若 simple-ai 未内置）**

检查是否需要：

```bash
cd frontend && grep -r "react-markdown" src/components/ui/chat-message* 2>/dev/null | head -3
```

若无结果（simple-ai 组件不含 react-markdown），则安装：

```bash
cd frontend && PATH="/Users/peng/.nvm/versions/node/v24.11.0/bin:$PATH" pnpm add react-markdown
```

若 simple-ai 已内置 Markdown 渲染，跳过此步，并将 `MessageBubble` 中的 `ReactMarkdown` 替换为 `ChatMessageMarkdown`（从 `@/components/ui/chat-message` 导入）。

- [ ] **Step 4: 更新 TopicSheet — 宽屏分栏布局**

修改 `frontend/src/components/topics/TopicSheet.tsx`：

**4a. 新增 import：**

```typescript
import { ResearchChat } from "./ResearchChat";
```

**4b. 将 `<SidePanel open={!!topic} onClose={onClose}>` 改为：**

```typescript
<SidePanel open={!!topic} onClose={onClose} wide>
```

**4c. 将 `<SidePanelBody className="space-y-6">` 及其全部子节点替换为分栏布局：**

```typescript
        <SidePanelBody className="p-0 overflow-hidden">
          <div className="grid grid-cols-[1fr_320px] h-full">
            {/* Left: Research Assistant */}
            <div className="flex flex-col min-h-0 px-5 py-5 border-r">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">
                研究助手
              </p>
              <ResearchChat topic={displayTopic} />
            </div>

            {/* Right: Scoring + Meta */}
            <div className="overflow-y-auto px-5 py-5 space-y-6">
              {/* Scoring */}
              <section className="space-y-4">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">打分</p>
                {SCORE_DIMENSIONS.map(({ key, label, desc }) => (
                  <div key={key} className="space-y-2">
                    <div className="flex items-baseline gap-2">
                      <Label className="text-sm font-medium">{label}</Label>
                      <span className="text-xs text-muted-foreground">{desc}</span>
                    </div>
                    <ScorePicker
                      value={scores[key]}
                      onChange={(v) => setScores((prev) => ({ ...prev, [key]: v }))}
                    />
                  </div>
                ))}
              </section>

              {/* Meta */}
              <section className="space-y-4">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">元数据</p>
                <div className="space-y-1.5">
                  <Label className="text-sm">状态</Label>
                  <Select value={status} onValueChange={(v) => v && setStatus(v)}>
                    <SelectTrigger className="w-full"><SelectValue>{TOPIC_STATUS_LABELS[status]}</SelectValue></SelectTrigger>
                    <SelectContent>
                      {Object.entries(TOPIC_STATUS_LABELS).map(([val, lbl]) => (
                        <SelectItem key={val} value={val}>{lbl}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <Label className="text-sm">标签</Label>
                  <Input
                    value={tagsInput}
                    onChange={(e) => setTagsInput(e.target.value)}
                    placeholder="科学, 物理, 认知"
                    className="text-sm"
                  />
                  <p className="text-xs text-muted-foreground">逗号分隔多个标签</p>
                </div>
              </section>
            </div>
          </div>
        </SidePanelBody>
```

- [ ] **Step 5: 确认 TypeScript 编译通过**

```bash
cd frontend && PATH="/Users/peng/.nvm/versions/node/v24.11.0/bin:$PATH" pnpm tsc --noEmit
```

预期：无错误

若有 `react-markdown` 类型缺失错误，安装类型：

```bash
cd frontend && PATH="/Users/peng/.nvm/versions/node/v24.11.0/bin:$PATH" pnpm add -D @types/react-markdown 2>/dev/null || true
```

- [ ] **Step 6: 构建确认**

```bash
cd frontend && PATH="/Users/peng/.nvm/versions/node/v24.11.0/bin:$PATH" pnpm build
```

预期：Build completed，无错误

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/topics/ResearchChat.tsx frontend/src/components/topics/TopicSheet.tsx frontend/src/components/ui/side-panel.tsx frontend/package.json frontend/pnpm-lock.yaml
git commit -m "feat: add ResearchChat component and two-column TopicSheet layout"
```

---

## Self-Review

### Spec Coverage

| Spec 要求 | 任务 |
|-----------|------|
| `topics.research_data` JSONB 列 | Task 1 |
| `TopicResponse.research_data` | Task 1 |
| `ResearchMessageRequest` schema | Task 1 |
| `AIProvider.research_topic` 协议 | Task 2 |
| Stub 实现（可替换） | Task 3 `get_ai_provider()` |
| `POST /api/topics/{id}/research` SSE | Task 3 |
| `use_default_prompt` 两种模式 | Task 3 |
| 历史消息传给 LLM | Task 3 |
| 流结束后写入 DB | Task 3 |
| `Topic.researchData` TS 类型 | Task 4 |
| `SidePanel wide` prop | Task 4 |
| `@simple-ai/chat-message` 安装 | Task 4 |
| `ResearchChat` 组件 | Task 5 |
| 流式 SSE 消费 | Task 5 |
| 历史为空时"查询背景资料"按钮 | Task 5 |
| TopicSheet 宽屏分栏布局 | Task 5 |
| Markdown 渲染 | Task 5 |

### 无 Placeholder ✓

所有步骤包含完整代码，无 TBD。

### 类型一致性 ✓

- `research_data`（后端）↔ `researchData`（前端）via `to_camel`
- `ResearchMessage.content` ↔ DB `content` 字段
- `AIProvider.research_topic` 签名与 Task 3 调用参数一致
