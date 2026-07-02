import { ChevronRight, Palette } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { STYLE_CATEGORIES } from "@/lib/styleCategories";

interface StylePromptComponent {
  key: string;
  label: string;
  name: string;
  promptText: string;
}

function readString(
  value: Record<string, unknown>,
  snakeCaseKey: string,
  camelCaseKey: string,
) {
  const candidate = value[snakeCaseKey] ?? value[camelCaseKey];
  return typeof candidate === "string" ? candidate : null;
}

function parseStyleComponents(
  snapshot: Record<string, unknown> | null,
): StylePromptComponent[] {
  const rawComponents = snapshot?.components;
  if (!rawComponents || typeof rawComponents !== "object" || Array.isArray(rawComponents)) {
    return [];
  }

  const components = rawComponents as Record<string, unknown>;
  return STYLE_CATEGORIES.flatMap(({ key, label }) => {
    const rawComponent = components[key];
    if (!rawComponent || typeof rawComponent !== "object" || Array.isArray(rawComponent)) {
      return [];
    }

    const metadata = rawComponent as Record<string, unknown>;
    const promptText = readString(metadata, "prompt_text", "promptText");
    if (!promptText) return [];

    const rawName = metadata.name;
    const name = typeof rawName === "string" && rawName !== "system-default"
      ? rawName
      : "系统默认";
    return [{ key, label, name, promptText }];
  });
}

export function ProjectStylePrompts({
  promptSnapshot,
}: {
  promptSnapshot: Record<string, unknown> | null;
}) {
  const [open, setOpen] = useState(false);
  const components = parseStyleComponents(promptSnapshot);
  const hasSnapshot = components.length > 0;

  return (
    <>
      <Button
        type="button"
        variant="outline"
        className="h-auto w-full justify-start gap-2.5 px-3 py-2 text-left"
        disabled={!hasSnapshot}
        onClick={() => setOpen(true)}
      >
        <Palette className="size-4 shrink-0 text-muted-foreground" />
        <span className="min-w-0 flex-1">
          <span className="block text-xs font-medium">风格组件提示词</span>
          <span className="block truncate text-[11px] font-normal text-muted-foreground">
            {hasSnapshot ? `${components.length} 个生成快照` : "生成后可查看"}
          </span>
        </span>
        <ChevronRight className="size-3.5 shrink-0 text-muted-foreground" />
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[85vh] grid-rows-[auto_minmax(0,1fr)] sm:max-w-3xl">
          <DialogHeader className="pr-8">
            <DialogTitle>本次生成使用的风格组件</DialogTitle>
            <DialogDescription>
              以下内容来自版本快照，平台中的组件后续修改不会影响这里的记录。
            </DialogDescription>
          </DialogHeader>

          <div className="min-h-0 overflow-y-auto pr-1">
            <div className="grid gap-3 md:grid-cols-2">
              {components.map((component) => (
                <section
                  key={component.key}
                  className="min-w-0 rounded-lg border bg-muted/20 p-3"
                >
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <h3 className="text-sm font-medium">{component.label}</h3>
                    <Badge variant="secondary" className="max-w-40 truncate text-[11px]">
                      {component.name}
                    </Badge>
                  </div>
                  <p className="whitespace-pre-wrap break-words rounded-md bg-background p-2.5 font-mono text-xs leading-5 text-muted-foreground ring-1 ring-foreground/10">
                    {component.promptText}
                  </p>
                </section>
              ))}
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
