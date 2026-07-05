import { useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  Bot,
  Check,
  Copy,
  Loader2,
  MessageSquareText,
  Pencil,
  RotateCcw,
  SendHorizontal,
  Sparkles,
  Trash2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  usePromptComponents,
  useCreatePromptComponent,
  useUpdatePromptComponent,
  useDeletePromptComponent,
  useDuplicatePromptComponent,
  useStylePromptAssistant,
} from "@/hooks/usePromptComponents";
import type { PromptComponent, StyleAssistantMessage } from "@/types";
import { STYLE_CATEGORIES } from "@/lib/styleCategories";
import { StyleTemplatesPanel } from "@/components/styles/StyleTemplatesPanel";

interface ComponentFormData {
  category: string;
  name: string;
  description: string;
  promptText: string;
}

interface ChatEntry extends StyleAssistantMessage {
  id: string;
}

const CATEGORY_DESCRIPTIONS: Record<string, string> = {
  narrative_style: "定义表达口吻、讲述视角与语言质感",
  pacing: "控制视频时长、信息密度与讲述速度",
  scene_structure: "规划开场、展开、论证与收束方式",
  color_scheme: "约束色板、字体、构图与视觉层级",
  animation_style: "定义动效节奏、转场与元素运动规则",
};

function categoryLabel(category: string) {
  return STYLE_CATEGORIES.find((item) => item.key === category)?.label ?? category;
}

function stopCardClick(event: React.MouseEvent) {
  event.stopPropagation();
}

function ComponentCard({
  component,
  onView,
  onEdit,
}: {
  component: PromptComponent;
  onView: (c: PromptComponent) => void;
  onEdit: (c: PromptComponent) => void;
}) {
  const deleteComp = useDeletePromptComponent();
  const duplicateComp = useDuplicatePromptComponent();

  const viewComponent = () => onView(component);

  return (
    <Card
      className="group cursor-pointer gap-3 py-4 transition-all hover:-translate-y-0.5 hover:shadow-md hover:ring-foreground/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      role="button"
      tabIndex={0}
      onClick={viewComponent}
      onKeyDown={(event) => {
        if (event.target !== event.currentTarget) return;
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          viewComponent();
        }
      }}
    >
      <CardHeader className="gap-2">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <CardTitle className="line-clamp-1 text-[15px]">{component.name}</CardTitle>
            <p className="mt-1 text-xs text-muted-foreground">{categoryLabel(component.category)}</p>
          </div>
          {component.isBuiltin && (
            <span className="shrink-0 rounded-full bg-muted px-2 py-0.5 text-[11px] font-medium text-muted-foreground">
              内置
            </span>
          )}
        </div>
        {component.description && (
          <CardDescription className="line-clamp-1 text-xs leading-5">
            {component.description}
          </CardDescription>
        )}
      </CardHeader>

      <CardContent className="flex-1">
        <div className="relative rounded-lg border bg-muted/45 px-3 py-2.5">
          <p className="line-clamp-6 min-h-20 whitespace-pre-wrap font-mono text-xs leading-5 text-muted-foreground">
            {component.promptText}
          </p>
          <div className="pointer-events-none absolute inset-x-0 bottom-0 h-8 rounded-b-lg bg-linear-to-t from-muted/90 to-transparent" />
        </div>
      </CardContent>

      <CardFooter className="justify-end border-t bg-transparent px-4 pt-2 pb-2">
        {/* <span className="flex items-center gap-1 text-xs text-muted-foreground transition-colors group-hover:text-foreground">
          <Eye className="size-3.5" />
          查看完整提示词
        </span> */}

        <div className="flex items-center gap-1" onClick={stopCardClick}>
          {component.isBuiltin ? (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => duplicateComp.mutate(component.id)}
              disabled={duplicateComp.isPending}
            >
              <Copy data-icon="inline-start" />
              {duplicateComp.isPending ? "复制中…" : "复制"}
            </Button>
          ) : (
            <>
              <Button
                size="icon-sm"
                variant="ghost"
                aria-label={`编辑「${component.name}」`}
                onClick={() => onEdit(component)}
              >
                <Pencil />
              </Button>
              <Button
                size="icon-sm"
                variant="ghost"
                className="text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                aria-label={`删除「${component.name}」`}
                onClick={() => {
                  if (confirm(`确认删除「${component.name}」？`)) {
                    deleteComp.mutate(component.id);
                  }
                }}
                disabled={deleteComp.isPending}
              >
                <Trash2 />
              </Button>
            </>
          )}
        </div>
      </CardFooter>
    </Card>
  );
}

function ComponentDetailDialog({
  component,
  onClose,
  onEdit,
}: {
  component: PromptComponent | null;
  onClose: () => void;
  onEdit: (c: PromptComponent) => void;
}) {
  if (!component) return null;

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[85vh] grid-rows-[auto_minmax(0,1fr)_auto] overflow-hidden sm:max-w-2xl">
        <DialogHeader className="pr-8">
          <div className="flex flex-wrap items-center gap-2">
            <DialogTitle className="text-lg">{component.name}</DialogTitle>
            {component.isBuiltin && (
              <span className="rounded-full bg-muted px-2 py-0.5 text-[11px] font-medium text-muted-foreground">
                内置
              </span>
            )}
          </div>
          <DialogDescription>
            {categoryLabel(component.category)}
            {component.description ? ` · ${component.description}` : ""}
          </DialogDescription>
        </DialogHeader>

        <div className="min-h-0 overflow-y-auto rounded-lg border bg-muted/40 p-4">
          <pre className="whitespace-pre-wrap break-words font-mono text-xs leading-6 text-foreground">
            {component.promptText}
          </pre>
        </div>

        {!component.isBuiltin && (
          <DialogFooter className="bg-background">
            <Button
              onClick={() => {
                onClose();
                onEdit(component);
              }}
            >
              <Pencil data-icon="inline-start" />
              编辑组件
            </Button>
          </DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  );
}

function ComponentFormDialog({
  open,
  onClose,
  category,
  editing,
}: {
  open: boolean;
  onClose: () => void;
  category: string;
  editing: PromptComponent | null;
}) {
  const [form, setForm] = useState<ComponentFormData>({
    category: "",
    name: "",
    description: "",
    promptText: "",
  });
  const [step, setStep] = useState<"category" | "workspace">("category");
  const [entries, setEntries] = useState<ChatEntry[]>([]);
  const [message, setMessage] = useState("");
  const [beforeAiEdit, setBeforeAiEdit] = useState<ComponentFormData | null>(null);
  const chatScrollRef = useRef<HTMLDivElement>(null);
  const createComp = useCreatePromptComponent();
  const updateComp = useUpdatePromptComponent();
  const assistant = useStylePromptAssistant();

  useEffect(() => {
    if (!open) return;
    const initialForm = {
      category: editing?.category ?? category,
      name: editing?.name ?? "",
      description: editing?.description ?? "",
      promptText: editing?.promptText ?? "",
    };
    setForm(editing ? initialForm : { ...initialForm, category: "" });
    setStep(editing ? "workspace" : "category");
    setEntries(
      editing
        ? [{
            id: "welcome",
            role: "assistant",
            content: `我已经读过「${editing.name}」的提示词了。告诉我你想强化、删减或改成什么感觉，我会直接更新左侧内容。`,
          }]
        : []
    );
    setMessage("");
    setBeforeAiEdit(null);
  }, [open, editing, category]);

  useEffect(() => {
    if (chatScrollRef.current) {
      chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight;
    }
  }, [entries, assistant.isPending]);

  const handleSubmit = () => {
    if (!form.name.trim() || !form.promptText.trim()) return;
    const data = {
      category: form.category,
      name: form.name.trim(),
      description: form.description.trim(),
      promptText: form.promptText.trim(),
    };
    if (editing) {
      updateComp.mutate({ id: editing.id, ...data }, { onSuccess: onClose });
    } else {
      createComp.mutate(data, { onSuccess: onClose });
    }
  };

  const isPending = createComp.isPending || updateComp.isPending;
  const selectedCategoryLabel = categoryLabel(form.category);

  const chooseCategory = (nextCategory: string) => {
    setForm((current) => ({ ...current, category: nextCategory }));
    setStep("workspace");
    setEntries([{
      id: "welcome",
      role: "assistant",
      content: `我们来创建一个${categoryLabel(nextCategory)}组件。先说说你想要的效果、参考风格或必须遵守的规则，我会生成第一版提示词。`,
    }]);
  };

  const sendMessage = async () => {
    const content = message.trim();
    if (!content || assistant.isPending) return;
    const userEntry: ChatEntry = {
      id: `${Date.now()}-user`,
      role: "user",
      content,
    };
    const conversationHistory = entries.map(({ role, content: entryContent }) => ({
      role,
      content: entryContent,
    }));
    setEntries((current) => [...current, userEntry]);
    setMessage("");
    try {
      const result = await assistant.mutateAsync({
        ...form,
        conversationHistory,
        message: content,
      });
      setBeforeAiEdit(form);
      setForm((current) => ({
        ...current,
        name: result.name || current.name,
        description: result.description,
        promptText: result.promptText,
      }));
      setEntries((current) => [
        ...current,
        {
          id: `${Date.now()}-assistant`,
          role: "assistant",
          content: result.reply,
        },
      ]);
    } catch (error) {
      setEntries((current) => [
        ...current,
        {
          id: `${Date.now()}-error`,
          role: "assistant",
          content: error instanceof Error ? error.message : "AI 助手暂时不可用，请稍后再试。",
        },
      ]);
    }
  };

  const handleChatKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void sendMessage();
    }
  };

  return (
    <Dialog open={open} onOpenChange={(nextOpen) => !nextOpen && onClose()}>
      <DialogContent
        className={`overflow-hidden p-0 sm:max-w-6xl ${
          step === "workspace"
            ? "h-[min(88vh,820px)] grid-rows-[auto_minmax(0,1fr)_auto]"
            : "max-h-[88vh] grid-rows-1"
        }`}
      >
        {step === "category" ? (
          <div className="flex min-h-0 flex-col p-6">
            <DialogHeader className="pr-8">
              <div className="mb-2 flex size-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <Sparkles className="size-5" />
              </div>
              <DialogTitle className="text-xl">先选择风格组件</DialogTitle>
              <DialogDescription>
                AI 会根据组件职责生成更聚焦的提示词，之后你可以通过对话继续打磨。
              </DialogDescription>
            </DialogHeader>
            <div className="mt-6 grid gap-3 sm:grid-cols-2">
              {STYLE_CATEGORIES.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => chooseCategory(item.key)}
                  className="group flex items-start gap-4 rounded-xl border p-4 text-left transition-all hover:border-primary/40 hover:bg-primary/[0.03] hover:shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <span className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted font-semibold text-muted-foreground transition-colors group-hover:bg-primary/10 group-hover:text-primary">
                    {item.label.slice(0, 1)}
                  </span>
                  <span>
                    <span className="block font-medium">{item.label}</span>
                    <span className="mt-1 block text-xs leading-5 text-muted-foreground">
                      {CATEGORY_DESCRIPTIONS[item.key]}
                    </span>
                  </span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            <div className="flex min-h-0 flex-col border-b px-5 py-4">
              <DialogHeader className="pr-8">
                <div className="flex flex-wrap items-center gap-2">
                  {!editing && (
                    <Button
                      size="icon-sm"
                      variant="ghost"
                      aria-label="重新选择组件类型"
                      onClick={() => setStep("category")}
                    >
                      <ArrowLeft />
                    </Button>
                  )}
                  <DialogTitle className="text-lg">
                    {editing ? `编辑「${editing.name}」` : `创建${selectedCategoryLabel}组件`}
                  </DialogTitle>
                  <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                    {selectedCategoryLabel}
                  </span>
                </div>
                <DialogDescription>
                  左侧内容可以直接编辑；告诉右侧 AI 你的要求，它会同步修改提示词。
                </DialogDescription>
              </DialogHeader>
            </div>

            <div className="grid min-h-0 flex-1 overflow-y-auto lg:grid-cols-[minmax(0,1.08fr)_minmax(360px,0.92fr)] lg:overflow-hidden">
              <section className="min-h-0 overflow-y-auto p-5">
                <div className="mb-4 flex items-center justify-between gap-3">
                  <div>
                    <h3 className="text-sm font-semibold">组件提示词</h3>
                    <p className="mt-0.5 text-xs text-muted-foreground">保存后会注入对应的视频生成环节</p>
                  </div>
                  {beforeAiEdit && (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => {
                        setForm(beforeAiEdit);
                        setBeforeAiEdit(null);
                      }}
                    >
                      <RotateCcw data-icon="inline-start" />
                      撤销 AI 修改
                    </Button>
                  )}
                </div>

                <div className="space-y-4">
                  <div className="space-y-1.5">
                    <Label htmlFor="component-name">名称</Label>
                    <Input
                      id="component-name"
                      placeholder="例如：克制的科技感"
                      value={form.name}
                      onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="component-description">说明（可选）</Label>
                    <Input
                      id="component-description"
                      placeholder="用一句话说明适用场景"
                      value={form.description}
                      onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between gap-4">
                      <Label htmlFor="component-prompt">提示词内容</Label>
                      <span className="text-xs tabular-nums text-muted-foreground">
                        {form.promptText.length} / 8000
                      </span>
                    </div>
                    <Textarea
                      id="component-prompt"
                      placeholder="直接输入提示词，或在右侧告诉 AI 你想要的风格…"
                      value={form.promptText}
                      onChange={(event) => setForm((current) => ({ ...current, promptText: event.target.value }))}
                      maxLength={8000}
                      className="h-[360px] resize-none overflow-y-auto bg-muted/25 font-mono text-xs leading-6"
                    />
                  </div>
                </div>
              </section>

              <section className="flex min-h-[360px] flex-col border-t bg-muted/20 lg:min-h-0 lg:border-t-0 lg:border-l">
                <div className="flex items-center gap-3 border-b bg-background/70 px-5 py-3">
                  <div className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
                    <Bot className="size-4" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold">风格 AI 助手</h3>
                    <p className="text-[11px] text-muted-foreground">会直接更新左侧内容，你可以随时撤销</p>
                  </div>
                </div>

                <div ref={chatScrollRef} className="min-h-0 flex-1 space-y-4 overflow-y-auto p-5">
                  {entries.map((entry) => (
                    <div
                      key={entry.id}
                      className={entry.role === "user" ? "flex justify-end" : "flex items-start gap-2.5"}
                    >
                      {entry.role === "assistant" && (
                        <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
                          <Sparkles className="size-3.5" />
                        </span>
                      )}
                      <div
                        className={
                          entry.role === "user"
                            ? "max-w-[85%] rounded-2xl rounded-br-sm bg-primary px-3.5 py-2.5 text-sm leading-6 text-primary-foreground"
                            : "max-w-[88%] rounded-2xl rounded-tl-sm border bg-background px-3.5 py-2.5 text-sm leading-6 shadow-xs"
                        }
                      >
                        {entry.content}
                      </div>
                    </div>
                  ))}
                  {assistant.isPending && (
                    <div className="flex items-center gap-2.5 text-sm text-muted-foreground">
                      <span className="flex size-7 items-center justify-center rounded-full bg-primary/10 text-primary">
                        <Loader2 className="size-3.5 animate-spin" />
                      </span>
                      正在整理并改写提示词…
                    </div>
                  )}
                </div>

                <div className="border-t bg-background p-4">
                  {entries.length <= 1 && (
                    <div className="mb-3 flex flex-wrap gap-2">
                      {["帮我生成第一版", "让规则更具体", "检查冲突和遗漏"].map((suggestion) => (
                        <button
                          key={suggestion}
                          type="button"
                          onClick={() => setMessage(suggestion)}
                          className="rounded-full border bg-background px-3 py-1 text-xs text-muted-foreground transition-colors hover:border-primary/30 hover:text-foreground"
                        >
                          {suggestion}
                        </button>
                      ))}
                    </div>
                  )}
                  <div className="rounded-xl border bg-muted/20 p-2 focus-within:ring-2 focus-within:ring-ring/30">
                    <Textarea
                      value={message}
                      onChange={(event) => setMessage(event.target.value)}
                      onKeyDown={handleChatKeyDown}
                      placeholder="描述想要的效果，或提出修改要求…"
                      rows={2}
                      disabled={assistant.isPending}
                      className="max-h-28 min-h-14 resize-none border-0 bg-transparent px-2 py-1 shadow-none focus-visible:ring-0"
                    />
                    <div className="mt-1 flex items-center justify-between px-1">
                      <span className="text-[11px] text-muted-foreground">Enter 发送 · Shift+Enter 换行</span>
                      <Button
                        size="icon-sm"
                        onClick={() => void sendMessage()}
                        disabled={!message.trim() || assistant.isPending}
                        aria-label="发送消息"
                      >
                        <SendHorizontal />
                      </Button>
                    </div>
                  </div>
                </div>
              </section>
            </div>

            <DialogFooter className="m-0 shrink-0 rounded-none bg-background px-5 py-3">
              <div className="mr-auto hidden items-center gap-1.5 text-xs text-muted-foreground sm:flex">
                {form.promptText.trim() ? (
                  <>
                    <Check className="size-3.5 text-emerald-600" />
                    提示词已就绪
                  </>
                ) : (
                  <>
                    <MessageSquareText className="size-3.5" />
                    可以自己填写，也可以请 AI 生成
                  </>
                )}
              </div>
              <Button variant="outline" onClick={onClose}>取消</Button>
              <Button onClick={handleSubmit} disabled={isPending || !form.name.trim() || !form.promptText.trim()}>
                {isPending ? "保存中…" : editing ? "保存修改" : "创建组件"}
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

export function StyleLibraryPage() {
  const [activeCategory, setActiveCategory] = useState(STYLE_CATEGORIES[0].key as string);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<PromptComponent | null>(null);
  const [viewing, setViewing] = useState<PromptComponent | null>(null);
  const { data, isLoading } = usePromptComponents(activeCategory);
  const items = data?.items ?? [];

  const openCreate = () => {
    setEditing(null);
    setDialogOpen(true);
  };
  const openEdit = (component: PromptComponent) => {
    setEditing(component);
    setDialogOpen(true);
  };

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">风格库</h1>
          <p className="mt-1 text-sm text-muted-foreground">管理视频生成工作流中可复用的提示词组件</p>
        </div>
        {activeCategory !== "templates" && (
          <Button onClick={openCreate}>
            <Sparkles data-icon="inline-start" />
            AI 创建组件
          </Button>
        )}
      </div>

      <div className="flex flex-wrap gap-2" aria-label="组件类型">
        <button
          onClick={() => setActiveCategory("templates")}
          className={`rounded-full px-4 py-1.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
            activeCategory === "templates"
              ? "bg-primary text-primary-foreground"
              : "bg-muted text-muted-foreground hover:bg-muted/80 hover:text-foreground"
          }`}
        >
          风格模板
        </button>
        {STYLE_CATEGORIES.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setActiveCategory(key)}
            className={`rounded-full px-4 py-1.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
              activeCategory === key
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground hover:bg-muted/80 hover:text-foreground"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {activeCategory === "templates" ? (
        <StyleTemplatesPanel />
      ) : isLoading ? (
        <p className="text-sm text-muted-foreground">加载中…</p>
      ) : items.length === 0 ? (
        <div className="rounded-xl border border-dashed py-16 text-center">
          <p className="text-sm font-medium">暂无{categoryLabel(activeCategory)}组件</p>
          <p className="mt-1 text-xs text-muted-foreground">创建一个组件，为生成工作流补充风格规则</p>
          <Button className="mt-4" variant="outline" onClick={openCreate}>
            <Sparkles data-icon="inline-start" />
            AI 创建组件
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((item) => (
            <ComponentCard
              key={item.id}
              component={item}
              onView={setViewing}
              onEdit={openEdit}
            />
          ))}
        </div>
      )}

      <ComponentDetailDialog
        component={viewing}
        onClose={() => setViewing(null)}
        onEdit={openEdit}
      />
      <ComponentFormDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        category={activeCategory}
        editing={editing}
      />
    </div>
  );
}
