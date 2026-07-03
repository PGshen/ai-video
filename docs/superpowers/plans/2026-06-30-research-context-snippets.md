# Research Context Snippets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow users to select text from the AI research chat and carry those snippets as context into narrative generation when creating a project.

**Architecture:** Snippets are collected in frontend state (TopicSheet), passed through CreateProjectDialog to the API, persisted in `video_projects.narrative_context`, and injected into the narrative generation prompt by NarrativeWorker via the AI provider.

**Tech Stack:** Python/FastAPI/SQLAlchemy (backend), Alembic (migrations), React/TypeScript/TanStack Query (frontend), Temporal (workflow), pytest/AsyncMock (tests).

## Global Constraints

- Use `/Users/peng/.local/bin/uv run pytest` — never bare `pytest`
- Use `PATH="/Users/peng/.nvm/versions/node/v24.11.0/bin:$PATH" pnpm` — never bare `pnpm`
- No DB foreign key constraints — app-layer only
- `narrative_context` stores `list[dict]` with shape `{"text": str}`
- Follow existing camelCase alias pattern in Pydantic schemas (`alias_generator=to_camel`)
- All backend tests go in `backend/tests/`
- Commit after each task

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/alembic/versions/<rev>_add_narrative_context_to_projects.py` | Create | DB migration |
| `backend/app/models/project.py` | Modify | Add `narrative_context` ORM field |
| `backend/app/schemas/project.py` | Modify | Add `narrative_context` to `ProjectCreate` |
| `backend/app/api/projects.py` | Modify | Store `narrative_context` on project creation |
| `backend/app/workflows/activities.py` | Modify | Pass `narrative_context` in `submit_narrative_task` payload |
| `backend/app/workers/narrative_worker.py` | Modify | Extract + forward `narrative_context` to provider |
| `backend/app/engines/ai/base.py` | Modify | Add `narrative_context` param to abstract `generate_narrative` |
| `backend/app/engines/ai/chat_provider.py` | Modify | Inject context snippets into narrative prompt |
| `backend/tests/test_narrative_provider.py` | Modify | Tests for narrative_context prompt injection |
| `backend/tests/test_narrative_worker.py` | Modify | Tests for narrative_context payload forwarding |
| `frontend/src/hooks/useProjects.ts` | Modify | Add `narrativeContext` to `useCreateProject` mutation |
| `frontend/src/components/topics/ResearchChat.tsx` | Modify | Text-selection bubble + `onSnippetSelect` callback |
| `frontend/src/components/topics/TopicSheet.tsx` | Modify | `contextSnippets` state + right panel snippet list |
| `frontend/src/components/topics/CreateProjectDialog.tsx` | Modify | Snippet checkbox list + send `narrativeContext` |

---

## Task 1: DB migration, model, schema, API endpoint

**Files:**
- Create: `backend/alembic/versions/<rev>_add_narrative_context_to_projects.py`
- Modify: `backend/app/models/project.py`
- Modify: `backend/app/schemas/project.py`
- Modify: `backend/app/api/projects.py`
- Test: `backend/tests/test_projects.py`

**Interfaces:**
- Produces: `VideoProject.narrative_context: list` (ORM field, JSONB, default `[]`)
- Produces: `ProjectCreate.narrative_context: list[dict] = []` (Pydantic schema)
- Produces: `POST /api/projects` stores `narrative_context` on the ORM object

- [ ] **Step 1: Write the failing test**

In `backend/tests/test_projects.py`, find the existing `test_create_project` test (or add after it):

```python
@pytest.mark.asyncio
async def test_create_project_stores_narrative_context(async_client, db_session):
    # Create a topic first
    topic = Topic(title="测试", source="manual", status="stocked")
    db_session.add(topic)
    await db_session.commit()

    payload = {
        "topic_id": str(topic.id),
        "render_engine": "manim",
        "tts_voice": "zizi",
        "aspect_ratio": "landscape",
        "narrative_context": [{"text": "关键参考片段一"}, {"text": "片段二"}],
    }
    resp = await async_client.post("/api/projects", json=payload)
    assert resp.status_code == 201
    project_id = resp.json()["id"]

    # Verify it was persisted
    from app.models.project import VideoProject
    import uuid
    project = await db_session.get(VideoProject, uuid.UUID(project_id))
    assert project.narrative_context == [{"text": "关键参考片段一"}, {"text": "片段二"}]
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd backend && /Users/peng/.local/bin/uv run pytest tests/test_projects.py::test_create_project_stores_narrative_context -v
```

Expected: FAIL (field doesn't exist yet)

- [ ] **Step 3: Create the Alembic migration**

```bash
cd backend && /Users/peng/.local/bin/uv run alembic revision --autogenerate -m "add_narrative_context_to_projects"
```

Then open the generated file and verify `upgrade` adds the column. If autogenerate didn't pick it up, write it manually:

```python
from sqlalchemy.dialects.postgresql import JSONB
import sqlalchemy as sa

def upgrade() -> None:
    op.add_column(
        "video_projects",
        sa.Column("narrative_context", JSONB(), nullable=False, server_default="[]"),
    )

def downgrade() -> None:
    op.drop_column("video_projects", "narrative_context")
```

- [ ] **Step 4: Add ORM field to `backend/app/models/project.py`**

After the `retry_count` field:

```python
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB

narrative_context: Mapped[list] = mapped_column(
    JSONB, default=list, server_default="[]"
)
```

- [ ] **Step 5: Add field to `ProjectCreate` schema in `backend/app/schemas/project.py`**

```python
class ProjectCreate(BaseModel):
    topic_id: UUID
    render_engine: str
    tts_voice: str
    aspect_ratio: str
    narrative_context: list[dict] = []
```

- [ ] **Step 6: Store field in `backend/app/api/projects.py` `create_project` endpoint**

In the `orm_project = VideoProject(...)` block, add:

```python
orm_project = VideoProject(
    topic_id=body.topic_id,
    status="draft",
    render_engine=body.render_engine,
    tts_voice=body.tts_voice,
    aspect_ratio=body.aspect_ratio,
    temporal_workflow_id=workflow_id,
    narrative_context=body.narrative_context,   # ← add this line
)
```

- [ ] **Step 7: Run migration against local DB**

```bash
cd backend && /Users/peng/.local/bin/uv run alembic upgrade head
```

Expected: `Running upgrade ... -> <rev>, add_narrative_context_to_projects`

- [ ] **Step 8: Run test to confirm it passes**

```bash
cd backend && /Users/peng/.local/bin/uv run pytest tests/test_projects.py::test_create_project_stores_narrative_context -v
```

Expected: PASS

- [ ] **Step 9: Run full test suite to check for regressions**

```bash
cd backend && /Users/peng/.local/bin/uv run pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: all previously-passing tests still pass

- [ ] **Step 10: Commit**

```bash
git add backend/alembic/versions/ backend/app/models/project.py backend/app/schemas/project.py backend/app/api/projects.py backend/tests/test_projects.py
git commit -m "feat: add narrative_context field to video_projects and ProjectCreate schema"
```

---

## Task 2: Activities + Worker + AI Provider

**Files:**
- Modify: `backend/app/workflows/activities.py`
- Modify: `backend/app/workers/narrative_worker.py`
- Modify: `backend/app/engines/ai/base.py`
- Modify: `backend/app/engines/ai/chat_provider.py`
- Modify: `backend/tests/test_narrative_provider.py`
- Modify: `backend/tests/test_narrative_worker.py`

**Interfaces:**
- Consumes: `VideoProject.narrative_context: list` (from Task 1)
- Produces: `submit_narrative_task` puts `narrative_context` in `input_payload`
- Produces: `NarrativeWorker._execute` passes `narrative_context` to `provider.generate_narrative`
- Produces: `ChatAIProvider.generate_narrative(narrative_context: list[dict] = [])` injects snippets into prompt

- [ ] **Step 1: Write failing test for prompt injection**

In `backend/tests/test_narrative_provider.py`, add:

```python
@pytest.mark.asyncio
async def test_generate_narrative_with_context_snippets():
    provider = make_provider()
    result = await provider.generate_narrative(
        topic_title="测试",
        topic_description="描述",
        render_engine="manim",
        narrative_context=[{"text": "参考内容：量子纠缠的直觉解释"}],
    )
    assert isinstance(result, NarrativeResult)


def test_generate_narrative_context_injected_into_user_payload():
    """When narrative_context is provided, snippets appear in the user message."""
    from unittest.mock import AsyncMock, MagicMock
    import asyncio

    captured = {}

    async def fake_completion(messages, **kwargs):
        captured["messages"] = messages
        return '{"scenes": [], "fact_checks": []}'

    client = MagicMock()
    client.engine_name = "stub"
    client.model_name = "stub-model"
    client.create_chat_completion = fake_completion

    provider = ChatAIProvider(client=client)
    asyncio.get_event_loop().run_until_complete(
        provider.generate_narrative(
            topic_title="T",
            topic_description="D",
            render_engine="manim",
            narrative_context=[{"text": "片段A"}, {"text": "片段B"}],
        )
    )
    user_msg = captured["messages"][-1]["content"]
    assert "片段A" in user_msg
    assert "片段B" in user_msg
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd backend && /Users/peng/.local/bin/uv run pytest tests/test_narrative_provider.py::test_generate_narrative_with_context_snippets tests/test_narrative_provider.py::test_generate_narrative_context_injected_into_user_payload -v
```

Expected: FAIL (unexpected keyword argument `narrative_context`)

- [ ] **Step 3: Update abstract base signature in `backend/app/engines/ai/base.py`**

```python
async def generate_narrative(
    self,
    topic_title: str,
    topic_description: str,
    render_engine: str,
    rejection_context: dict | None = None,
    narrative_context: list[dict] | None = None,
) -> NarrativeResult: ...
```

- [ ] **Step 4: Update `ChatAIProvider.generate_narrative` in `backend/app/engines/ai/chat_provider.py`**

Change the signature:

```python
async def generate_narrative(
    self,
    topic_title: str,
    topic_description: str,
    render_engine: str,
    rejection_context: dict | None = None,
    narrative_context: list[dict] | None = None,
) -> NarrativeResult:
```

After building `user_payload` and `user_note`, add the context block before the `create_chat_completion` call:

```python
        context_note = ""
        if narrative_context:
            snippets_text = "\n---\n".join(
                item["text"] for item in narrative_context if item.get("text")
            )
            if snippets_text:
                context_note = (
                    "\n\n以下是创作者标注的参考内容，请在叙事中参考这些观点和表述方式：\n\n"
                    + snippets_text
                )

        content = await self.client.create_chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"请为以下选题生成知识视频叙事脚本 JSON{user_note}：\n"
                    + json.dumps(user_payload, ensure_ascii=False)
                    + context_note,
                },
            ],
            response_format={"type": "json_object"},
            max_tokens=self.script_max_tokens,
        )
```

- [ ] **Step 5: Run provider tests**

```bash
cd backend && /Users/peng/.local/bin/uv run pytest tests/test_narrative_provider.py -v
```

Expected: all pass

- [ ] **Step 6: Write failing test for NarrativeWorker forwarding**

In `backend/tests/test_narrative_worker.py`, add:

```python
@pytest.mark.asyncio
async def test_narrative_worker_passes_context_to_provider():
    task = make_task(input_payload={
        "topic_title": "T",
        "topic_description": "D",
        "render_engine": "manim",
        "rejection_context": None,
        "narrative_context": [{"text": "参考片段"}],
    })
    project_id = task.project_id
    captured_kwargs = {}

    async def fake_generate_narrative(**kwargs):
        captured_kwargs.update(kwargs)
        return NarrativeResult(
            scenes=[{"scene_index": 0, "narration": "旁白", "description": "描述"}],
            fact_checks=[],
        )

    mock_provider = AsyncMock()
    mock_provider.model_name = "stub-model"
    mock_provider.generate_narrative = fake_generate_narrative

    mock_project = MagicMock()
    mock_project.id = project_id
    mock_project.tts_voice = "zizi"
    mock_project.current_narrative_version_id = None

    nv_id = uuid.uuid4()
    mock_nv = MagicMock()
    mock_nv.id = nv_id
    mock_nv.scenes = []

    mock_db = MagicMock()
    mock_db.get.side_effect = lambda model, pid: mock_project if model.__name__ == "VideoProject" else mock_nv
    mock_db.execute.return_value.scalar.return_value = None

    with patch("app.workers.narrative_worker.get_ai_provider", return_value=mock_provider), \
         patch("app.workers.narrative_worker.get_sync_session", return_value=mock_db), \
         patch("app.workers.narrative_worker._synthesize_scenes_tts", new_callable=AsyncMock) as mock_tts, \
         patch("app.workers.narrative_worker.upload_bytes"):
        mock_tts.return_value = [{"scene_index": 0, "tts_status": "ready"}]
        worker = NarrativeWorker()
        await worker._execute(task)

    assert captured_kwargs.get("narrative_context") == [{"text": "参考片段"}]
```

- [ ] **Step 7: Run test to confirm it fails**

```bash
cd backend && /Users/peng/.local/bin/uv run pytest tests/test_narrative_worker.py::test_narrative_worker_passes_context_to_provider -v
```

Expected: FAIL

- [ ] **Step 8: Update `NarrativeWorker._execute` in `backend/app/workers/narrative_worker.py`**

Extract `narrative_context` from payload and pass to provider:

```python
async def _execute(self, task) -> dict:
    payload = task.input_payload or {}
    topic_title = payload.get("topic_title", "")
    topic_description = payload.get("topic_description", "")
    render_engine = payload.get("render_engine", "manim")
    rejection_context = payload.get("rejection_context")
    narrative_context = payload.get("narrative_context") or []   # ← add this

    # ...existing logging...

    provider = get_ai_provider()
    result = await provider.generate_narrative(
        topic_title=topic_title,
        topic_description=topic_description,
        render_engine=render_engine,
        rejection_context=rejection_context,
        narrative_context=narrative_context,   # ← add this
    )
```

- [ ] **Step 9: Update `submit_narrative_task` in `backend/app/workflows/activities.py`**

After fetching `topic`, include `narrative_context` in the task `input_payload`:

```python
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
                "narrative_context": project.narrative_context or [],   # ← add this
            },
            temporal_workflow_id=f"video-production-{project_id}",
            signal_name="narrative_generated",
            max_retries=3,
        )
```

- [ ] **Step 10: Run all updated tests**

```bash
cd backend && /Users/peng/.local/bin/uv run pytest tests/test_narrative_worker.py tests/test_narrative_provider.py tests/test_workflow_activities.py -v
```

Expected: all pass

- [ ] **Step 11: Run full suite**

```bash
cd backend && /Users/peng/.local/bin/uv run pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: all previously-passing tests still pass

- [ ] **Step 12: Commit**

```bash
git add backend/app/engines/ai/base.py backend/app/engines/ai/chat_provider.py \
        backend/app/workers/narrative_worker.py backend/app/workflows/activities.py \
        backend/tests/test_narrative_provider.py backend/tests/test_narrative_worker.py
git commit -m "feat: forward narrative_context through worker and AI provider prompt"
```

---

## Task 3: Frontend — ResearchChat text selection bubble

**Files:**
- Modify: `frontend/src/components/topics/ResearchChat.tsx`

**Interfaces:**
- Consumes: new prop `onSnippetSelect: (text: string) => void`
- Produces: floating bubble rendered near selection; calls `onSnippetSelect` with the selected string on click

- [ ] **Step 1: Add `onSnippetSelect` prop and bubble state to `ResearchChat`**

Replace the `interface Props` block and add bubble state at the top of the function body:

```tsx
interface Props {
  topic: Topic;
  onSnippetSelect: (text: string) => void;
}

export function ResearchChat({ topic, onSnippetSelect }: Props) {
  // ...existing state...
  const [bubble, setBubble] = useState<{ x: number; y: number; text: string } | null>(null);
```

- [ ] **Step 2: Add mouseup handler on the messages container**

Add a `handleMouseUp` function inside the component (before the return):

```tsx
  function handleMouseUp() {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed) {
      setBubble(null);
      return;
    }
    const text = sel.toString().trim();
    if (!text) {
      setBubble(null);
      return;
    }
    const range = sel.getRangeAt(0);
    const rect = range.getBoundingClientRect();
    setBubble({ x: rect.right, y: rect.top + window.scrollY - 4, text });
  }
```

- [ ] **Step 3: Add global mousedown to clear bubble on outside click**

Add inside the component:

```tsx
  useEffect(() => {
    function handleMouseDown(e: MouseEvent) {
      const target = e.target as HTMLElement;
      if (!target.closest("[data-snippet-bubble]")) {
        setBubble(null);
      }
    }
    document.addEventListener("mousedown", handleMouseDown);
    return () => document.removeEventListener("mousedown", handleMouseDown);
  }, []);
```

- [ ] **Step 4: Attach `onMouseUp` to the messages container and render the bubble**

In the `return (...)`, add `onMouseUp={handleMouseUp}` to the scrollable messages div:

```tsx
      <div
        ref={scrollRef}
        className="flex-1 min-w-0 overflow-y-auto space-y-4 pr-1"
        onMouseUp={handleMouseUp}
      >
```

After the closing `</div>` of the messages area (before the `<form>`), add the bubble:

```tsx
      {bubble && (
        <div
          data-snippet-bubble
          style={{ position: "fixed", left: bubble.x + 8, top: bubble.y }}
          className="z-50 bg-foreground text-background text-xs px-2 py-1 rounded shadow-md cursor-pointer whitespace-nowrap"
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => {
            onSnippetSelect(bubble.text);
            window.getSelection()?.removeAllRanges();
            setBubble(null);
          }}
        >
          ＋ 加入上下文
        </div>
      )}
```

- [ ] **Step 5: Verify no TypeScript errors**

```bash
cd frontend && PATH="/Users/peng/.nvm/versions/node/v24.11.0/bin:$PATH" pnpm tsc --noEmit 2>&1 | head -30
```

Expected: no errors related to `ResearchChat`

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/topics/ResearchChat.tsx
git commit -m "feat: add text-selection snippet bubble to ResearchChat"
```

---

## Task 4: Frontend — TopicSheet context snippets state + panel

**Files:**
- Modify: `frontend/src/components/topics/TopicSheet.tsx`

**Interfaces:**
- Consumes: `ResearchChat` prop `onSnippetSelect` (from Task 3)
- Produces: `contextSnippets: string[]` state accessible to `CreateProjectDialog`
- Produces: snippet list rendered in the right panel with per-item delete

- [ ] **Step 1: Add `contextSnippets` state and wire into `ResearchChat`**

At the top of `TopicSheet` function body, add:

```tsx
  const [contextSnippets, setContextSnippets] = useState<string[]>([]);

  function handleSnippetSelect(text: string) {
    setContextSnippets((prev) => [...prev, text]);
  }
```

Update the `<ResearchChat>` call:

```tsx
<ResearchChat topic={displayTopic} onSnippetSelect={handleSnippetSelect} />
```

- [ ] **Step 2: Add the context snippets section in the right panel**

In the right-side scrollable div, add a new `<section>` **above** the scoring section:

```tsx
              {/* Context Snippets */}
              {contextSnippets.length > 0 && (
                <section className="space-y-2">
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                    上下文片段
                  </p>
                  <div className="space-y-1.5">
                    {contextSnippets.map((snippet, i) => (
                      <div
                        key={i}
                        className="flex items-start gap-2 rounded-md bg-muted px-2.5 py-1.5 text-xs"
                      >
                        <span className="flex-1 line-clamp-2 text-muted-foreground">
                          {snippet}
                        </span>
                        <button
                          type="button"
                          onClick={() =>
                            setContextSnippets((prev) => prev.filter((_, idx) => idx !== i))
                          }
                          className="shrink-0 text-muted-foreground hover:text-foreground mt-0.5"
                          aria-label="删除片段"
                        >
                          <X className="size-3" />
                        </button>
                      </div>
                    ))}
                  </div>
                </section>
              )}
```

- [ ] **Step 3: Pass `contextSnippets` to `CreateProjectDialog`**

Update the `<CreateProjectDialog>` component call (near bottom of `TopicSheet`):

```tsx
      {createProjectOpen && (
        <CreateProjectDialog
          topic={displayTopic}
          open={createProjectOpen}
          onClose={() => setCreateProjectOpen(false)}
          contextSnippets={contextSnippets}
          onCreated={() =>
            setDisplayTopic((prev) =>
              prev ? { ...prev, status: "in_production" } : prev
            )
          }
        />
      )}
```

- [ ] **Step 4: Verify no TypeScript errors**

```bash
cd frontend && PATH="/Users/peng/.nvm/versions/node/v24.11.0/bin:$PATH" pnpm tsc --noEmit 2>&1 | head -30
```

Expected: error about `contextSnippets` prop on `CreateProjectDialog` (not yet added) — that's fine, we add it in Task 5.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/topics/TopicSheet.tsx
git commit -m "feat: add contextSnippets state and panel to TopicSheet"
```

---

## Task 5: Frontend — CreateProjectDialog snippet selector + API

**Files:**
- Modify: `frontend/src/components/topics/CreateProjectDialog.tsx`
- Modify: `frontend/src/hooks/useProjects.ts`

**Interfaces:**
- Consumes: `contextSnippets: string[]` prop
- Produces: checkbox list per snippet (default all selected)
- Produces: `useCreateProject` mutation sends `narrative_context: [{text}]` to API

- [ ] **Step 1: Update `useCreateProject` in `frontend/src/hooks/useProjects.ts`**

```tsx
export function useCreateProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      topicId: string;
      renderEngine: string;
      ttsVoice: string;
      aspectRatio: string;
      narrativeContext: { text: string }[];
    }) =>
      api.post<VideoProject>("/api/projects", {
        topic_id: data.topicId,
        render_engine: data.renderEngine,
        tts_voice: data.ttsVoice,
        aspect_ratio: data.aspectRatio,
        narrative_context: data.narrativeContext,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["projects"] });
      qc.invalidateQueries({ queryKey: ["topics"] });
    },
  });
}
```

- [ ] **Step 2: Update `CreateProjectDialog` to accept and use snippets**

Replace the full component:

```tsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { useCreateProject } from "@/hooks/useProjects";
import type { Topic } from "@/types";

interface Props {
  topic: Topic;
  open: boolean;
  onClose: () => void;
  onCreated?: () => void;
  contextSnippets?: string[];
}

const RENDER_ENGINE_LABELS: Record<string, string> = {
  manim: "Manim",
  remotion: "Remotion",
};

const TTS_VOICE_LABELS: Record<string, string> = {
  zizi: "zizi",
  echo: "Echo",
  fable: "Fable",
  onyx: "Onyx",
  nova: "Nova",
};

const ASPECT_RATIO_LABELS: Record<string, string> = {
  landscape: "横屏 16:9",
  portrait: "竖屏 9:16",
};

export function CreateProjectDialog({ topic, open, onClose, onCreated, contextSnippets = [] }: Props) {
  const [renderEngine, setRenderEngine] = useState("manim");
  const [ttsVoice, setTtsVoice] = useState("zizi");
  const [aspectRatio, setAspectRatio] = useState("landscape");
  const [selectedSnippets, setSelectedSnippets] = useState<Set<number>>(
    () => new Set(contextSnippets.map((_, i) => i))
  );
  const createProject = useCreateProject();
  const navigate = useNavigate();

  function toggleSnippet(i: number) {
    setSelectedSnippets((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
  }

  const handleSubmit = () => {
    const narrativeContext = contextSnippets
      .filter((_, i) => selectedSnippets.has(i))
      .map((text) => ({ text }));
    createProject.mutate(
      { topicId: topic.id, renderEngine, ttsVoice, aspectRatio, narrativeContext },
      {
        onSuccess: (_project) => {
          onCreated?.();
          onClose();
          navigate("/projects");
        },
      }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>从选题创建项目</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div className="rounded-md bg-muted px-3 py-2 text-sm text-muted-foreground">
            {topic.title}
          </div>
          <div className="space-y-1.5">
            <Label>渲染引擎</Label>
            <Select value={renderEngine} onValueChange={(v) => v && setRenderEngine(v)}>
              <SelectTrigger><SelectValue>{RENDER_ENGINE_LABELS[renderEngine]}</SelectValue></SelectTrigger>
              <SelectContent>
                <SelectItem value="manim">Manim</SelectItem>
                <SelectItem value="remotion">Remotion</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>TTS 声音</Label>
            <Select value={ttsVoice} onValueChange={(v) => v && setTtsVoice(v)}>
              <SelectTrigger><SelectValue>{TTS_VOICE_LABELS[ttsVoice]}</SelectValue></SelectTrigger>
              <SelectContent>
                <SelectItem value="zizi">zizi</SelectItem>
                <SelectItem value="echo">Echo</SelectItem>
                <SelectItem value="fable">Fable</SelectItem>
                <SelectItem value="onyx">Onyx</SelectItem>
                <SelectItem value="nova">Nova</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>画幅比例</Label>
            <Select value={aspectRatio} onValueChange={(v) => v && setAspectRatio(v)}>
              <SelectTrigger><SelectValue>{ASPECT_RATIO_LABELS[aspectRatio]}</SelectValue></SelectTrigger>
              <SelectContent>
                <SelectItem value="landscape">横屏 16:9</SelectItem>
                <SelectItem value="portrait">竖屏 9:16</SelectItem>
              </SelectContent>
            </Select>
          </div>
          {contextSnippets.length > 0 && (
            <div className="space-y-2">
              <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                研究上下文（选择带入叙事生成）
              </Label>
              <div className="space-y-1.5 max-h-40 overflow-y-auto">
                {contextSnippets.map((snippet, i) => (
                  <div key={i} className="flex items-start gap-2">
                    <Checkbox
                      id={`snippet-${i}`}
                      checked={selectedSnippets.has(i)}
                      onCheckedChange={() => toggleSnippet(i)}
                      className="mt-0.5 shrink-0"
                    />
                    <label
                      htmlFor={`snippet-${i}`}
                      className="text-xs text-muted-foreground line-clamp-2 cursor-pointer"
                    >
                      {snippet}
                    </label>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>取消</Button>
          <Button onClick={handleSubmit} disabled={createProject.isPending}>
            {createProject.isPending ? "创建中..." : "创建项目"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 3: Check if `Checkbox` component exists**

```bash
ls /Users/peng/Me/Ai/ai-video/frontend/src/components/ui/checkbox.tsx 2>/dev/null && echo "exists" || echo "missing"
```

If missing, add it:

```bash
cd frontend && PATH="/Users/peng/.nvm/versions/node/v24.11.0/bin:$PATH" pnpm dlx shadcn@latest add checkbox
```

- [ ] **Step 4: Verify TypeScript compiles cleanly**

```bash
cd frontend && PATH="/Users/peng/.nvm/versions/node/v24.11.0/bin:$PATH" pnpm tsc --noEmit 2>&1 | head -40
```

Expected: no errors

- [ ] **Step 5: Build to verify no bundler errors**

```bash
cd frontend && PATH="/Users/peng/.nvm/versions/node/v24.11.0/bin:$PATH" pnpm build 2>&1 | tail -20
```

Expected: `✓ built in ...`

- [ ] **Step 6: Commit**

```bash
git add frontend/src/hooks/useProjects.ts frontend/src/components/topics/CreateProjectDialog.tsx frontend/src/components/ui/checkbox.tsx
git commit -m "feat: add context snippet selector to CreateProjectDialog and wire to API"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Covered by |
|-----------------|-----------|
| Text selection bubble in ResearchChat | Task 3 |
| Snippets listed in right panel with delete | Task 4 |
| CreateProjectDialog shows checkboxes | Task 5 |
| `narrativeContext` sent to API | Task 5 |
| Stored in `video_projects.narrative_context` | Task 1 |
| Forwarded to `submit_narrative_task` | Task 2 |
| Passed to `generate_narrative` | Task 2 |
| Injected into AI prompt | Task 2 |

**Placeholder scan:** None found — all steps contain actual code.

**Type consistency:**
- `contextSnippets: string[]` flows from `TopicSheet` → `CreateProjectDialog` ✓
- `narrativeContext: { text: string }[]` flows from `useCreateProject` → API ✓
- `narrative_context: list[dict]` flows from `ProjectCreate` → `VideoProject` → `input_payload` → `NarrativeWorker` → `generate_narrative` ✓
- `narrative_context: list[dict] | None` matches between `base.py` and `chat_provider.py` ✓
