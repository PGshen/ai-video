import { useEffect, useMemo, useState } from "react";
import {
  LayoutTemplate,
  Pencil,
  Sparkles,
  Trash2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { usePromptComponents } from "@/hooks/usePromptComponents";
import {
  useCreateStyleTemplate,
  useDeleteStyleTemplate,
  useStyleTemplates,
  useUpdateStyleTemplate,
} from "@/hooks/useStyleTemplates";
import { STYLE_CATEGORIES } from "@/lib/styleCategories";
import type { PromptComponent, StyleTemplate } from "@/types";

const EMPTY_COMPONENTS: PromptComponent[] = [];

export function TemplateDialog({
  open,
  editing,
  onClose,
}: {
  open: boolean;
  editing: StyleTemplate | null;
  onClose: () => void;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [styleConfig, setStyleConfig] = useState<Record<string, string>>({});
  const { data: componentData } = usePromptComponents();
  const createTemplate = useCreateStyleTemplate();
  const updateTemplate = useUpdateStyleTemplate();
  const components = componentData?.items ?? EMPTY_COMPONENTS;

  useEffect(() => {
    if (!open) return;
    setName(editing?.name ?? "");
    setDescription(editing?.description ?? "");
    setStyleConfig(editing?.styleConfig ?? {});
  }, [editing, open]);

  const save = () => {
    const data = {
      name: name.trim(),
      description: description.trim(),
      styleConfig,
    };
    if (editing) {
      updateTemplate.mutate({ id: editing.id, ...data }, { onSuccess: onClose });
    } else {
      createTemplate.mutate(data, { onSuccess: onClose });
    }
  };
  const pending = createTemplate.isPending || updateTemplate.isPending;

  return (
    <Dialog open={open} onOpenChange={(nextOpen) => !nextOpen && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{editing ? "编辑风格模板" : "创建风格模板"}</DialogTitle>
          <DialogDescription>
            把常用的风格组件保存为组合，创建项目时即可一键套用。
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-5 py-2">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="template-name">模板名称</Label>
              <Input
                id="template-name"
                value={name}
                maxLength={100}
                placeholder="例如：暖白极简科普"
                onChange={(event) => setName(event.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="template-description">说明（可选）</Label>
              <Input
                id="template-description"
                value={description}
                placeholder="适用主题或整体效果"
                onChange={(event) => setDescription(event.target.value)}
              />
            </div>
          </div>

          <div>
            <div className="mb-3">
              <h3 className="text-sm font-semibold">关联风格组件</h3>
              <p className="mt-0.5 text-xs text-muted-foreground">
                不必选满，未关联的类别会继续使用系统默认值
              </p>
            </div>
            <div className="grid gap-4 rounded-xl border bg-muted/20 p-4 sm:grid-cols-2">
              {STYLE_CATEGORIES.map(({ key, label }) => {
                const options = components.filter((item) => item.category === key);
                const selected = options.find((item) => item.id === styleConfig[key]);
                return (
                  <div key={key} className="space-y-1.5">
                    <Label className="text-xs">{label}</Label>
                    <Select
                      value={styleConfig[key] ?? ""}
                      onValueChange={(value) =>
                        setStyleConfig((current) => {
                          const next = { ...current };
                          if (value) next[key] = value;
                          else delete next[key];
                          return next;
                        })
                      }
                    >
                      <SelectTrigger className="w-full bg-background">
                        <SelectValue>{selected?.name ?? "系统默认"}</SelectValue>
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="">系统默认</SelectItem>
                        {options.map((item) => (
                          <SelectItem key={item.id} value={item.id}>
                            {item.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>取消</Button>
          <Button
            onClick={save}
            disabled={pending || !name.trim() || Object.keys(styleConfig).length === 0}
          >
            {pending ? "保存中…" : "保存模板"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function StyleTemplatesPanel({
  onEditAssociations,
  onEditLibrary,
}: {
  onEditAssociations: (template: StyleTemplate) => void;
  onEditLibrary: (template: StyleTemplate) => void;
}) {
  const { data, isLoading } = useStyleTemplates();
  const { data: componentData } = usePromptComponents();
  const deleteTemplate = useDeleteStyleTemplate();
  const templates = data?.items ?? [];
  const components = componentData?.items ?? EMPTY_COMPONENTS;
  const componentNames = useMemo(
    () => new Map(components.map((item) => [item.id, item.name])),
    [components]
  );

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">加载中…</p>;
  }

  return (
    <>
      {templates.length === 0 ? (
        <div className="rounded-xl border border-dashed py-16 text-center">
          <LayoutTemplate className="mx-auto mb-3 size-8 text-muted-foreground" />
          <p className="text-sm font-medium">暂无风格模板</p>
          <p className="mt-1 text-xs text-muted-foreground">
            把一组风格组件保存下来，创建项目时一键套用
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {templates.map((template) => (
            <Card key={template.id} className="gap-3 py-4">
                <CardHeader>
                  <CardTitle className="text-[15px]">{template.name}</CardTitle>
                  {template.description && (
                    <CardDescription className="line-clamp-2 text-xs leading-5">
                      {template.description}
                    </CardDescription>
                  )}
                </CardHeader>
                <CardContent className="flex-1">
                  <div className="space-y-2 rounded-lg border bg-muted/35 p-3">
                    {STYLE_CATEGORIES.map(({ key, label }) => {
                      const componentId = template.styleConfig[key];
                      if (!componentId) return null;
                      return (
                        <div key={key} className="flex gap-2 text-xs leading-5">
                          <span className="w-16 shrink-0 text-muted-foreground">{label}</span>
                          <span className="line-clamp-1 font-medium">
                            {componentNames.get(componentId) ?? "组件已删除"}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </CardContent>
                <CardFooter className="justify-end border-t px-4 pt-2 pb-2">
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => onEditLibrary(template)}
                    disabled={!componentData}
                  >
                    <Sparkles data-icon="inline-start" />
                    编辑风格库
                  </Button>
                  <Button
                    size="icon-sm"
                    variant="ghost"
                    aria-label={`调整「${template.name}」的组件关联`}
                    title="调整组件关联"
                    onClick={() => onEditAssociations(template)}
                  >
                    <Pencil />
                  </Button>
                  <Button
                    size="icon-sm"
                    variant="ghost"
                    className="text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                    aria-label={`删除「${template.name}」`}
                    disabled={deleteTemplate.isPending}
                    onClick={() => {
                      if (confirm(`确认删除模板「${template.name}」？`)) {
                        deleteTemplate.mutate(template.id);
                      }
                    }}
                  >
                    <Trash2 />
                  </Button>
                </CardFooter>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
