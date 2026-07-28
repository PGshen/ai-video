import { useEffect, useMemo, useRef, useState } from "react";
import {
  Bot,
  Check,
  Circle,
  LibraryBig,
  Loader2,
  MessageSquareText,
  RotateCcw,
  SendHorizontal,
  Sparkles,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  useCreateStyleLibrary,
  useStyleLibraryAssistant,
  useUpdateStyleLibrary,
} from "@/hooks/useStyleTemplates";
import { STYLE_CATEGORIES } from "@/lib/styleCategories";
import type {
  PromptComponent,
  StyleAssistantMessage,
  StyleLibraryComponentDraft,
  StyleLibraryDraft,
  StyleTemplate,
} from "@/types";

interface ChatEntry extends StyleAssistantMessage {
  id: string;
}

const EMPTY_COMPONENTS = Object.fromEntries(
  STYLE_CATEGORIES.map(({ key }) => [
    key,
    { name: "", description: "", promptText: "" },
  ])
) as Record<string, StyleLibraryComponentDraft>;

function emptyLibrary(): StyleLibraryDraft {
  return {
    name: "",
    description: "",
    components: Object.fromEntries(
      Object.entries(EMPTY_COMPONENTS).map(([key, value]) => [
        key,
        { ...value },
      ])
    ),
  };
}

function draftFromTemplate(
  template: StyleTemplate,
  components: PromptComponent[]
): StyleLibraryDraft {
  const componentsById = new Map(components.map((item) => [item.id, item]));
  return {
    name: template.name,
    description: template.description ?? "",
    components: Object.fromEntries(
      STYLE_CATEGORIES.map(({ key }) => {
        const component = componentsById.get(template.styleConfig[key]);
        return [
          key,
          {
            name: component?.name ?? "",
            description: component?.description ?? "",
            promptText: component?.promptText ?? "",
          },
        ];
      })
    ),
  };
}

function isComponentReady(component: StyleLibraryComponentDraft) {
  return Boolean(component.name.trim() && component.promptText.trim());
}

export function StyleLibraryDialog({
  open,
  editing,
  availableComponents,
  onClose,
}: {
  open: boolean;
  editing: StyleTemplate | null;
  availableComponents: PromptComponent[];
  onClose: () => void;
}) {
  const [form, setForm] = useState<StyleLibraryDraft>(emptyLibrary);
  const [activeCategory, setActiveCategory] = useState(
    STYLE_CATEGORIES[0].key as string
  );
  const [entries, setEntries] = useState<ChatEntry[]>([]);
  const [message, setMessage] = useState("");
  const [beforeAiEdit, setBeforeAiEdit] = useState<StyleLibraryDraft | null>(null);
  const chatScrollRef = useRef<HTMLDivElement>(null);
  const createLibrary = useCreateStyleLibrary();
  const updateLibrary = useUpdateStyleLibrary();
  const assistant = useStyleLibraryAssistant();

  useEffect(() => {
    if (!open) return;
    setForm(
      editing
        ? draftFromTemplate(editing, availableComponents)
        : emptyLibrary()
    );
    setActiveCategory(STYLE_CATEGORIES[0].key);
    setEntries([
      {
        id: "welcome",
        role: "assistant",
        content: editing
          ? `我已经读过「${editing.name}」及其四个组件。告诉我你想调整的整体感觉或具体系统，我会统一检查并更新。`
          : "描述你想要的视频气质、受众、参考风格和禁忌。我会一次生成叙事蓝图、视觉系统、动画系统与金样本。",
      },
    ]);
    setMessage("");
    setBeforeAiEdit(null);
  }, [open, editing]);

  useEffect(() => {
    if (chatScrollRef.current) {
      chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight;
    }
  }, [entries, assistant.isPending]);

  const selectedCategory =
    STYLE_CATEGORIES.find((item) => item.key === activeCategory)
    ?? STYLE_CATEGORIES[0];
  const selectedComponent =
    form.components[activeCategory] ?? EMPTY_COMPONENTS[activeCategory];
  const completedCount = useMemo(
    () =>
      STYLE_CATEGORIES.filter(({ key }) =>
        isComponentReady(form.components[key] ?? EMPTY_COMPONENTS[key])
      ).length,
    [form.components]
  );
  const canSave =
    Boolean(form.name.trim()) && completedCount === STYLE_CATEGORIES.length;
  const isPending = createLibrary.isPending || updateLibrary.isPending;
  const saveError = createLibrary.error ?? updateLibrary.error;

  const updateSelectedComponent = (
    patch: Partial<StyleLibraryComponentDraft>
  ) => {
    setForm((current) => ({
      ...current,
      components: {
        ...current.components,
        [activeCategory]: {
          ...(current.components[activeCategory] ?? EMPTY_COMPONENTS[activeCategory]),
          ...patch,
        },
      },
    }));
  };

  const save = () => {
    if (!canSave || isPending) return;
    const payload: StyleLibraryDraft = {
      name: form.name.trim(),
      description: form.description.trim(),
      components: Object.fromEntries(
        STYLE_CATEGORIES.map(({ key }) => {
          const component = form.components[key];
          return [
            key,
            {
              name: component.name.trim(),
              description: component.description.trim(),
              promptText: component.promptText.trim(),
            },
          ];
        })
      ),
    };
    if (editing) {
      updateLibrary.mutate(
        { id: editing.id, ...payload },
        { onSuccess: onClose }
      );
    } else {
      createLibrary.mutate(payload, { onSuccess: onClose });
    }
  };

  const sendMessage = async () => {
    const content = message.trim();
    if (!content || assistant.isPending) return;
    const userEntry: ChatEntry = {
      id: `${Date.now()}-user`,
      role: "user",
      content,
    };
    const conversationHistory = entries.map(
      ({ role, content: entryContent }) => ({
        role,
        content: entryContent,
      })
    );
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
        name: result.name || current.name,
        description: result.description,
        components: Object.fromEntries(
          STYLE_CATEGORIES.map(({ key }) => [
            key,
            result.components[key] ?? current.components[key],
          ])
        ),
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
          content:
            error instanceof Error
              ? error.message
              : "AI 助手暂时不可用，请稍后再试。",
        },
      ]);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(nextOpen) => !nextOpen && onClose()}>
      <DialogContent className="h-[min(92vh,900px)] grid-rows-[auto_minmax(0,1fr)_auto] gap-0 overflow-hidden p-0 sm:max-w-[min(96vw,1280px)]">
        <div className="border-b px-5 py-4">
          <DialogHeader className="pr-8">
            <div className="flex flex-wrap items-center gap-2.5">
              <span className="flex size-9 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <LibraryBig className="size-4.5" />
              </span>
              <div>
                <DialogTitle className="text-lg">
                  {editing ? `编辑风格库「${editing.name}」` : "AI 创建完整风格库"}
                </DialogTitle>
                <DialogDescription className="mt-1">
                  统一编辑四个组件；右侧 AI 会从整套风格的一致性出发同步调整。
                </DialogDescription>
              </div>
              <span className="ml-auto mr-8 rounded-full bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground">
                {completedCount} / {STYLE_CATEGORIES.length} 已就绪
              </span>
            </div>
          </DialogHeader>
        </div>

        <div className="grid min-h-0 overflow-y-auto lg:grid-cols-[minmax(0,1.35fr)_minmax(350px,0.65fr)] lg:overflow-hidden">
          <section className="min-h-0 overflow-y-auto p-5">
            <div className="grid gap-3 rounded-xl border bg-muted/20 p-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="library-name">风格库名称</Label>
                <Input
                  id="library-name"
                  value={form.name}
                  maxLength={100}
                  placeholder="例如：冷静科技纪录片"
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      name: event.target.value,
                    }))
                  }
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="library-description">整体说明（可选）</Label>
                <Input
                  id="library-description"
                  value={form.description}
                  placeholder="适用主题、受众或整体气质"
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      description: event.target.value,
                    }))
                  }
                />
              </div>
            </div>

            <div className="mt-5 flex items-end justify-between gap-3">
              <div>
                <h3 className="text-sm font-semibold">风格组件</h3>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  四项都会保存为独立组件，并组合成当前风格模板
                </p>
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

            <div
              className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4"
              role="tablist"
              aria-label="风格组件"
            >
              {STYLE_CATEGORIES.map(({ key, label }) => {
                const ready = isComponentReady(
                  form.components[key] ?? EMPTY_COMPONENTS[key]
                );
                return (
                  <button
                    key={key}
                    type="button"
                    role="tab"
                    aria-selected={activeCategory === key}
                    onClick={() => setActiveCategory(key)}
                    className={`flex items-center justify-center gap-1.5 rounded-lg border px-3 py-2 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                      activeCategory === key
                        ? "border-primary/40 bg-primary/10 text-primary"
                        : "bg-background text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {ready ? (
                      <Check className="size-3.5 text-emerald-600" />
                    ) : (
                      <Circle className="size-3.5" />
                    )}
                    {label}
                  </button>
                );
              })}
            </div>

            <div className="mt-3 rounded-xl border p-4">
              <div className="mb-4 flex items-center justify-between gap-4">
                <div>
                  <h4 className="font-medium">{selectedCategory.label}</h4>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    直接编辑当前组件，切换组件不会丢失内容
                  </p>
                </div>
                <span className="text-xs tabular-nums text-muted-foreground">
                  {selectedComponent.promptText.length} / 8000
                </span>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label htmlFor="library-component-name">组件名称</Label>
                  <Input
                    id="library-component-name"
                    value={selectedComponent.name}
                    maxLength={100}
                    placeholder={`${form.name || "当前风格"} · ${selectedCategory.label}`}
                    onChange={(event) =>
                      updateSelectedComponent({ name: event.target.value })
                    }
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="library-component-description">
                    组件说明（可选）
                  </Label>
                  <Input
                    id="library-component-description"
                    value={selectedComponent.description}
                    placeholder={`说明${selectedCategory.label}的设计目标`}
                    onChange={(event) =>
                      updateSelectedComponent({ description: event.target.value })
                    }
                  />
                </div>
              </div>
              <div className="mt-3 space-y-1.5">
                <Label htmlFor="library-component-prompt">提示词内容</Label>
                <Textarea
                  id="library-component-prompt"
                  value={selectedComponent.promptText}
                  maxLength={8000}
                  placeholder={`直接输入${selectedCategory.label}提示词，或让右侧 AI 生成整套内容…`}
                  onChange={(event) =>
                    updateSelectedComponent({ promptText: event.target.value })
                  }
                  className="h-[300px] resize-none overflow-y-auto bg-muted/25 font-mono text-xs leading-6"
                />
              </div>
            </div>
          </section>

          <section className="flex min-h-[420px] flex-col border-t bg-muted/20 lg:min-h-0 lg:border-t-0 lg:border-l">
            <div className="flex items-center gap-3 border-b bg-background/70 px-5 py-3">
              <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
                <Bot className="size-4" />
              </span>
              <div>
                <h3 className="text-sm font-semibold">风格库 AI 助手</h3>
                <p className="text-[11px] text-muted-foreground">
                  同时理解四个组件，保持规则协调一致
                </p>
              </div>
            </div>

            <div
              ref={chatScrollRef}
              className="min-h-0 flex-1 space-y-4 overflow-y-auto p-5"
            >
              {entries.map((entry) => (
                <div
                  key={entry.id}
                  className={
                    entry.role === "user"
                      ? "flex justify-end"
                      : "flex items-start gap-2.5"
                  }
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
                  正在统筹并生成四个组件…
                </div>
              )}
            </div>

            <div className="border-t bg-background p-4">
              {entries.length <= 1 && (
                <div className="mb-3 flex flex-wrap gap-2">
                  {[
                    "帮我生成完整第一版",
                    "做成克制的科技纪录片风格",
                    "检查四个组件的冲突和遗漏",
                  ].map((suggestion) => (
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
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault();
                      void sendMessage();
                    }
                  }}
                  placeholder="描述整体风格，或指定要修改的组件…"
                  rows={2}
                  disabled={assistant.isPending}
                  className="max-h-28 min-h-14 resize-none border-0 bg-transparent px-2 py-1 shadow-none focus-visible:ring-0"
                />
                <div className="mt-1 flex items-center justify-between px-1">
                  <span className="text-[11px] text-muted-foreground">
                    Enter 发送 · Shift+Enter 换行
                  </span>
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
            {saveError ? (
              <span className="text-destructive">
                {saveError instanceof Error ? saveError.message : "保存失败"}
              </span>
            ) : canSave ? (
              <>
                <Check className="size-3.5 text-emerald-600" />
                整套风格库已就绪
              </>
            ) : (
              <>
                <MessageSquareText className="size-3.5" />
                可手动填写，也可让 AI 一次生成四项
              </>
            )}
          </div>
          <Button variant="outline" onClick={onClose}>
            取消
          </Button>
          <Button onClick={save} disabled={!canSave || isPending}>
            {isPending
              ? "保存中…"
              : editing
                ? "保存风格库"
                : "创建风格库"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
