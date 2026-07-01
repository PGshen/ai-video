import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
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
  name: string;
  description: string;
  promptText: string;
}

function ComponentCard({
  component,
  onEdit,
}: {
  component: PromptComponent;
  onEdit: (c: PromptComponent) => void;
}) {
  const deleteComp = useDeletePromptComponent();
  const duplicateComp = useDuplicatePromptComponent();

  return (
    <Card className="flex flex-col">
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-sm font-medium">{component.name}</CardTitle>
          {component.isBuiltin && (
            <span className="text-xs text-muted-foreground bg-muted px-1.5 py-0.5 rounded shrink-0">内置</span>
          )}
        </div>
        {component.description && (
          <CardDescription className="text-xs">{component.description}</CardDescription>
        )}
      </CardHeader>
      <CardContent className="flex-1 pb-2">
        <pre className="text-xs text-muted-foreground bg-muted rounded p-2 max-h-24 overflow-y-auto whitespace-pre-wrap font-mono">
          {component.promptText.slice(0, 200)}{component.promptText.length > 200 ? "…" : ""}
        </pre>
      </CardContent>
      <CardFooter className="gap-2 pt-2">
        {component.isBuiltin ? (
          <Button
            size="sm"
            variant="outline"
            className="flex-1"
            onClick={() => duplicateComp.mutate(component.id)}
            disabled={duplicateComp.isPending}
          >
            复制为自定义
          </Button>
        ) : (
          <>
            <Button size="sm" variant="outline" className="flex-1" onClick={() => onEdit(component)}>
              编辑
            </Button>
            <Button
              size="sm"
              variant="destructive"
              onClick={() => {
                if (confirm(`确认删除「${component.name}」？`)) {
                  deleteComp.mutate(component.id);
                }
              }}
              disabled={deleteComp.isPending}
            >
              删除
            </Button>
          </>
        )}
      </CardFooter>
    </Card>
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
    name: editing?.name ?? "",
    description: editing?.description ?? "",
    promptText: editing?.promptText ?? "",
  });
  const createComp = useCreatePromptComponent();
  const updateComp = useUpdatePromptComponent();

  const handleSubmit = () => {
    if (!form.name.trim() || !form.promptText.trim()) return;
    if (editing) {
      updateComp.mutate(
        { id: editing.id, name: form.name, description: form.description, promptText: form.promptText },
        { onSuccess: onClose }
      );
    } else {
      createComp.mutate(
        { category, name: form.name, description: form.description, promptText: form.promptText },
        { onSuccess: onClose }
      );
    }
  };

  const isPending = createComp.isPending || updateComp.isPending;

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{editing ? "编辑组件" : "新建组件"}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div className="space-y-1.5">
            <Label>名称</Label>
            <Input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
          </div>
          <div className="space-y-1.5">
            <Label>说明（可选）</Label>
            <Input
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
            />
          </div>
          <div className="space-y-1.5">
            <Label>提示词内容</Label>
            <Textarea
              value={form.promptText}
              onChange={(e) => setForm((f) => ({ ...f, promptText: e.target.value }))}
              rows={10}
              className="font-mono text-xs"
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>取消</Button>
          <Button onClick={handleSubmit} disabled={isPending || !form.name.trim() || !form.promptText.trim()}>
            {isPending ? "保存中…" : "保存"}
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
  const { data, isLoading } = usePromptComponents(activeCategory);
  const items = data?.items ?? [];

  const openCreate = () => { setEditing(null); setDialogOpen(true); };
  const openEdit = (c: PromptComponent) => { setEditing(c); setDialogOpen(true); };

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">风格库</h1>
        <Button onClick={openCreate}>新建组件</Button>
      </div>

      {/* Category tabs */}
      <div className="flex gap-2 flex-wrap">
        {STYLE_CATEGORIES.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setActiveCategory(key)}
            className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors ${
              activeCategory === key
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground hover:bg-muted/80"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Component cards */}
      {isLoading ? (
        <p className="text-sm text-muted-foreground">加载中…</p>
      ) : items.length === 0 ? (
        <p className="text-sm text-muted-foreground">暂无组件，点击「新建组件」创建</p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map((item) => (
            <ComponentCard key={item.id} component={item} onEdit={openEdit} />
          ))}
        </div>
      )}

      <ComponentFormDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        category={activeCategory}
        editing={editing}
      />
    </div>
  );
}
