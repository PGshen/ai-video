import { useEffect, useState } from "react";
import { Copy, Pencil, Plus, Trash2 } from "lucide-react";
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  usePromptComponents,
  useCreatePromptComponent,
  useUpdatePromptComponent,
  useDeletePromptComponent,
  useDuplicatePromptComponent,
} from "@/hooks/usePromptComponents";
import type { PromptComponent } from "@/types";
import { STYLE_CATEGORIES } from "@/lib/styleCategories";

interface ComponentFormData {
  category: string;
  name: string;
  description: string;
  promptText: string;
}

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
      <DialogContent className="max-h-[85vh] overflow-hidden sm:max-w-2xl">
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
    category,
    name: "",
    description: "",
    promptText: "",
  });
  const createComp = useCreatePromptComponent();
  const updateComp = useUpdatePromptComponent();

  useEffect(() => {
    if (!open) return;
    setForm({
      category: editing?.category ?? category,
      name: editing?.name ?? "",
      description: editing?.description ?? "",
      promptText: editing?.promptText ?? "",
    });
  }, [open, editing, category]);

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

  return (
    <Dialog open={open} onOpenChange={(nextOpen) => !nextOpen && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto p-5 sm:max-w-3xl">
        <DialogHeader className="pr-8">
          <DialogTitle className="text-lg">{editing ? "编辑组件" : "新建组件"}</DialogTitle>
          <DialogDescription>
            组件会作为生成提示词的一部分注入工作流，请保持内容清晰、可复用。
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-5 py-1">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="component-name">名称</Label>
              <Input
                id="component-name"
                placeholder="例如：简洁大气"
                value={form.name}
                onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="component-category">组件类型</Label>
              <Select
                value={form.category}
                onValueChange={(value) => value && setForm((current) => ({ ...current, category: value }))}
              >
                <SelectTrigger id="component-category" className="w-full">
                  <SelectValue>{selectedCategoryLabel}</SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {STYLE_CATEGORIES.map((item) => (
                    <SelectItem key={item.key} value={item.key}>
                      {item.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="component-description">说明（可选）</Label>
            <Input
              id="component-description"
              placeholder="用一句话说明这个组件适合什么场景"
              value={form.description}
              onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))}
            />
          </div>

          <div className="space-y-1.5">
            <div className="flex items-center justify-between gap-4">
              <Label htmlFor="component-prompt">提示词内容</Label>
              <span className="text-xs tabular-nums text-muted-foreground">{form.promptText.length} / 8000</span>
            </div>
            <Textarea
              id="component-prompt"
              placeholder="输入完整提示词内容…"
              value={form.promptText}
              onChange={(event) => setForm((current) => ({ ...current, promptText: event.target.value }))}
              maxLength={8000}
              className="h-72 resize-none overflow-y-auto font-mono text-xs leading-5"
            />
          </div>
        </div>

        <DialogFooter className="bg-background">
          <Button variant="outline" onClick={onClose}>取消</Button>
          <Button onClick={handleSubmit} disabled={isPending || !form.name.trim() || !form.promptText.trim()}>
            {isPending ? "保存中…" : "保存组件"}
          </Button>
        </DialogFooter>
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
        <Button onClick={openCreate}>
          <Plus data-icon="inline-start" />
          新建组件
        </Button>
      </div>

      <div className="flex flex-wrap gap-2" aria-label="组件类型">
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

      {isLoading ? (
        <p className="text-sm text-muted-foreground">加载中…</p>
      ) : items.length === 0 ? (
        <div className="rounded-xl border border-dashed py-16 text-center">
          <p className="text-sm font-medium">暂无{categoryLabel(activeCategory)}组件</p>
          <p className="mt-1 text-xs text-muted-foreground">创建一个组件，为生成工作流补充风格规则</p>
          <Button className="mt-4" variant="outline" onClick={openCreate}>
            <Plus data-icon="inline-start" />
            新建组件
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
