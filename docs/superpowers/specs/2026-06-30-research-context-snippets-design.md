# 研究上下文片段功能设计

**日期：** 2026-06-30  
**范围：** 选题打分页研究助手 → 创建项目 → 叙事生成

## 背景

选题打分页已接入 AI 研究助手（ResearchChat），用户可查询选题背景知识。但这些研究内容目前未被叙事生成利用，导致叙事与用户打分时看到的内容可能不一致。

本功能允许用户在研究对话中划选关键片段，带入项目创建，供叙事生成参考。

---

## 方案：方案 C（前端收集 + 随项目持久化）

片段在前端收集，随创建请求存入 `video_projects.narrative_context`，`NarrativeWorker` 读取后拼入 prompt。好处：交互简洁，数据可追溯。

---

## 数据模型

### `video_projects` 表新增字段

```sql
narrative_context  JSONB  NOT NULL  DEFAULT '[]'
```

存储结构：

```json
[
  { "text": "用户划选的文字片段" }
]
```

### `ProjectCreate` schema

```python
class ProjectCreate(BaseModel):
    topic_id: UUID
    render_engine: str
    tts_voice: str
    aspect_ratio: str
    narrative_context: list[dict] = []  # 新增
```

---

## 前端交互

### 1. 文本划选气泡（ResearchChat）

- 组件在根元素上监听 `mouseup`，检测 `window.getSelection()`
- 若选中文字非空，在选区末尾附近渲染一个浮层气泡按钮「＋ 加入上下文」
- 点击后调用 `onSnippetSelect(text: string)` 回调，气泡消失
- 气泡通过 `position: fixed` + `getBoundingClientRect()` 定位

### 2. `TopicSheet` 状态管理

```typescript
const [contextSnippets, setContextSnippets] = useState<string[]>([]);
```

- `handleSnippetSelect(text)` → `setContextSnippets(prev => [...prev, text])`
- 传给 `ResearchChat` 的 `onSnippetSelect` 回调
- 传给 `CreateProjectDialog` 的 `contextSnippets` prop

### 3. 右侧面板新增上下文片段区域

位置：在打分区域上方（或"研究助手"与"打分"之间）。

- 有片段时显示，无片段时整个区域隐藏
- 每条片段：截断至 2 行，超出省略；右侧 ✕ 删除按钮
- 标题：「上下文片段」（uppercase tracking-wide，与其他区域标题风格一致）

### 4. CreateProjectDialog 片段选择

- 接收 `contextSnippets: string[]` prop
- 若非空，弹窗内新增"研究上下文"区域，展示片段列表
- 每条片段前有 checkbox，默认全选
- 用户可取消不想带入的片段
- `handleSubmit` 时将选中片段映射为 `{ text }` 对象数组，通过 `narrativeContext` 字段传给 API

---

## 后端链路

### API 层（`POST /api/projects`）

接收 `narrative_context`，存入 `VideoProject.narrative_context`。

### Temporal Activity（`submit_narrative_task`）

读取 `project.narrative_context`，放入 `input_payload['narrative_context']`。

### NarrativeWorker

```python
narrative_context = payload.get("narrative_context", [])
result = await provider.generate_narrative(
    topic_title=topic_title,
    topic_description=topic_description,
    render_engine=render_engine,
    rejection_context=rejection_context,
    narrative_context=narrative_context,   # 新增
)
```

### AI Provider（`generate_narrative`）

`narrative_context` 非空时，在系统 prompt 末尾追加：

```
以下是创作者标注的参考内容，请在叙事中参考这些观点和表述方式：

{joined_snippets}
```

`joined_snippets` = 每条 snippet 的 `text` 用 `\n---\n` 连接。

---

## 组件职责边界

| 组件/模块 | 变化 |
|-----------|------|
| `ResearchChat` | 新增 `onSnippetSelect` 回调 prop；内部处理 mouseup 气泡逻辑 |
| `TopicSheet` | 持有 `contextSnippets` state；右侧面板新增片段展示区 |
| `CreateProjectDialog` | 接收 `contextSnippets`；内部管理选中态；传 `narrativeContext` 给 API |
| `useCreateProject` hook | 请求 body 增加 `narrativeContext` |
| DB migration | `video_projects` 表加 `narrative_context JSONB DEFAULT '[]'` |
| `ProjectCreate` schema | 增加 `narrative_context: list[dict] = []` |
| `submit_narrative_task` activity | payload 中透传 `narrative_context` |
| `NarrativeWorker` | 从 payload 取 `narrative_context`，传给 provider |
| AI provider `generate_narrative` | 增加 `narrative_context` 参数，拼入 prompt |

---

## 不在本次范围内

- 片段跨会话持久化到 topic 层
- 研究对话内容的自动全量带入
- 片段排序或重新编辑文字
