# 选题研究助手 设计文档

**日期：** 2026-06-26  
**状态：** 已批准，待实现

## 背景

Sprint 1 完成后，选题打分（TopicSheet）只展示标题和描述，审核人信息不足，难以对反直觉度、可论证性等维度作出有质量的判断。本功能在 TopicSheet 中嵌入一个 AI 驱动的研究助手对话面板，让审核人可以边查阅背景知识边打分。

---

## 功能概述

- 触发方式：按需，审核人主动在输入框发送问题
- 内容形式：多轮对话，AI 回复以 Markdown 格式渲染
- 信息来源：LLM 自身知识（预留联网搜索扩展接口）
- 持久化：对话历史存入 `topics.research_data`（JSONB），下次打开自动恢复
- 布局：TopicSheet 扩宽，采用左右分栏——研究助手在左，打分/元数据在右

---

## 数据模型

### 数据库变更

`topics` 表新增一列：

```sql
ALTER TABLE topics ADD COLUMN research_data JSONB NOT NULL DEFAULT '[]';
```

### 存储格式

```json
[
  {
    "role": "user",
    "content": "这个话题的核心理论是什么？",
    "createdAt": "2026-06-26T10:00:00Z"
  },
  {
    "role": "assistant",
    "content": "## 核心理论\n\n...",
    "createdAt": "2026-06-26T10:00:05Z"
  }
]
```

### SQLAlchemy 模型（`backend/app/models/topic.py`）

新增字段：

```python
from sqlalchemy.dialects.postgresql import JSONB

research_data: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
```

### Pydantic Schema（`backend/app/schemas/topic.py`）

- `TopicResponse` 新增：`research_data: list[dict] = []`
- 新增请求体：

```python
class ResearchMessageRequest(BaseModel):
    message: str
```

---

## 后端 API

### 接口

```
POST /api/topics/{topic_id}/research
Content-Type: application/json
Accept: text/event-stream

{
  "message": "这个话题的核心理论是什么？",
  "use_default_prompt": false
}
```

- `message`：用户输入内容；若 `use_default_prompt: true` 则此字段可为空，后端使用预设问题
- `use_default_prompt`：是否使用系统 prompt 模板触发（默认 `false`）

**响应：** `text/event-stream`，每个 chunk 格式为 `data: <text>\n\n`，结束时发送 `data: [DONE]\n\n`。

### 处理逻辑

1. 从数据库读取 topic（含 `research_data` 历史对话）
2. 将历史对话转换为 LLM messages 数组 `[{role, content}, ...]`，保持完整上下文
3. 根据 `use_default_prompt` 决定如何构造本次调用：
   - **`true`（默认触发）**：注入系统 prompt（含选题标题、描述、研究助手角色），追加预设用户问题
   - **`false`（用户主动输入）**：直接追加用户消息，不注入系统 prompt，LLM 自由回答
4. 流式转发 LLM 输出到客户端
5. 流结束后，将 user 消息和完整 assistant 回复追加写入 `research_data`

### 系统 Prompt 模板（仅 `use_default_prompt: true` 时使用）

```
你是一位知识视频选题研究助手。当前研究的选题是：

标题：{topic_title}
描述：{topic_description}

请围绕该选题提供背景资料，内容以 Markdown 格式输出，重点包括：核心概念、相关理论、反直觉角度、可视化潜力等。
```

预设用户问题（后端固定）：`"请介绍这个选题的背景知识和核心理论"`

### AIProvider 协议扩展（`backend/app/engines/ai/base.py`）

```python
from typing import AsyncIterator

async def research_topic(
    self,
    topic_title: str,
    topic_description: str,
    conversation_history: list[dict],  # [{role, content}, ...]
    new_message: str,
    use_default_prompt: bool = False,
) -> AsyncIterator[str]: ...
```

**扩展点：** Sprint 后续接入 Tavily/Brave 搜索时，只需在实现层于调用 LLM 前先搜索并将结果拼入 context，协议接口不变。

---

## 前端

### 布局变更

TopicSheet 扩展为宽屏（`max-w-4xl`），SidePanelBody 内采用 CSS Grid 分栏：

```
┌──────────────────────────────────────────────────────┐
│ 标题 + 描述 + 标签（跨全宽 Header）                   │
├───────────────────────┬──────────────────────────────┤
│ 研究助手（左栏，弹性） │ 打分 + 元数据（右栏，320px） │
│                       │                              │
│ 对话气泡区域           │ 反直觉度  ① ② ③ ④ ⑤        │
│ （可滚动）             │ 可论证性  ① ② ③ ④ ⑤        │
│                       │ 可视化性  ① ② ③ ④ ⑤        │
│                       │ 新鲜度    ① ② ③ ④ ⑤        │
│                       │ ────────────────────────     │
│ [输入框]      [发送]  │ 状态 / 标签                  │
└───────────────────────┴──────────────────────────────┘
│          从此选题创建项目  │  保存                    │
└──────────────────────────────────────────────────────┘
```

实现细节：
- `SidePanel` width 改为 `max-w-4xl`
- SidePanelBody 内：`<div className="grid grid-cols-[1fr_320px] gap-6 h-full">`
- 左栏自身为 flex column：对话区域 `flex-1 overflow-y-auto` + 输入区域固定底部
- Footer 按钮布局不变，跨全宽

### 新增组件：`frontend/src/components/topics/ResearchChat.tsx`

使用 [simple-ai](https://www.simple-ai.dev/docs/components/chat-message) 的 `ChatMessage` 系列组件（shadcn 风格，`npx shadcn@latest add @simple-ai/chat-message` 安装），内置 Markdown 渲染和流式内容展示，**不引入 `@ai-sdk/react`**。

职责：
- 接收 `topic: Topic` prop
- 初始化时从 `topic.researchData` 加载历史，转换为组件所需的 `parts: [{type: "text", text}]` 格式（本地适配层，不污染存储格式）
- 维护本地 `messages` 状态（含流式中的临时 assistant 消息）
- 发送时调用 `fetch POST /api/topics/{id}/research`，用 `ReadableStream` 逐 chunk 更新当前 assistant 消息
- 流式进行中禁用输入框和发送按钮
- 当历史为空时，展示"查询背景资料"快捷按钮，点击后发送 `use_default_prompt: true` 触发默认查询；用户也可直接在输入框输入任意问题（`use_default_prompt: false`）

消息的本地格式（仅组件内部）：
```ts
interface ChatEntry {
  id: string;
  role: "user" | "assistant";
  parts: [{ type: "text"; text: string }];
}
```

持久化格式（存入 DB / `topic.researchData`）保持不变：`{role, content, createdAt}`。

### 新增 shadcn 组件

```bash
npx shadcn@latest add @simple-ai/chat-message
```

无需额外安装 npm 包（组件文件直接复制到项目中）。

### 修改文件

| 文件 | 变更 |
|------|------|
| `frontend/src/components/topics/TopicSheet.tsx` | 引入 ResearchChat，改为分栏布局，扩宽 SidePanel |
| `frontend/src/components/ui/side-panel.tsx` | 支持 `size` prop（`default` / `wide`）控制宽度 |
| `frontend/src/types/index.ts` | `Topic` 新增 `researchData: ResearchMessage[]` |
| `frontend/src/hooks/useTopics.ts` | 新增 `useResearchChat` hook（SSE fetch，管理流式状态） |

---

## 不在本次范围内

- 清空对话历史的按钮（可后续加）
- 联网搜索（接口已预留，Sprint 后续实现）
- 流式输出的错误重试 UI
