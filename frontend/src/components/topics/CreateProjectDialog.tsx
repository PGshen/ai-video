import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { useCreateProject } from "@/hooks/useProjects";
import { usePromptComponents } from "@/hooks/usePromptComponents";
import type { Topic } from "@/types";

interface Props {
  topic: Topic;
  open: boolean;
  onClose: () => void;
  onCreated?: () => void;
  contextSnippets?: string[];
}

const STYLE_CATEGORIES = [
  { key: "narrative_style", label: "叙事风格" },
  { key: "pacing", label: "叙事节奏" },
  { key: "scene_structure", label: "镜头结构" },
  { key: "color_scheme", label: "配色系统" },
  { key: "animation_style", label: "动画风格" },
] as const;

function StyleSelect({
  category,
  label,
  value,
  onChange,
}: {
  category: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  const { data } = usePromptComponents(category);
  const items = data?.items ?? [];

  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      <Select value={value} onValueChange={(v) => onChange(v ?? "")}>
        <SelectTrigger>
          <SelectValue placeholder="系统默认" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="">系统默认</SelectItem>
          {items.map((item) => (
            <SelectItem key={item.id} value={item.id}>
              <span>{item.name}</span>
              {item.isBuiltin && (
                <span className="ml-1 text-xs text-muted-foreground">内置</span>
              )}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {value && items.find((i) => i.id === value)?.description && (
        <p className="text-xs text-muted-foreground">
          {items.find((i) => i.id === value)?.description}
        </p>
      )}
    </div>
  );
}

export function CreateProjectDialog({ topic, open, onClose, onCreated, contextSnippets = [] }: Props) {
  const [renderEngine, setRenderEngine] = useState("manim");
  const [ttsVoice, setTtsVoice] = useState("alloy");
  const [aspectRatio, setAspectRatio] = useState("landscape");
  const [styleConfig, setStyleConfig] = useState<Record<string, string>>({});
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

  function setStyleCategory(category: string, value: string) {
    setStyleConfig((prev) => {
      if (!value) {
        const next = { ...prev };
        delete next[category];
        return next;
      }
      return { ...prev, [category]: value };
    });
  }

  const handleSubmit = () => {
    const narrativeContext = contextSnippets
      .filter((_, i) => selectedSnippets.has(i))
      .map((text) => ({ text }));
    createProject.mutate(
      { topicId: topic.id, renderEngine, ttsVoice, aspectRatio, narrativeContext, styleConfig },
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
      <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>从选题创建项目</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div className="rounded-md bg-muted px-3 py-2 text-sm text-muted-foreground">
            {topic.title}
          </div>

          {/* 基础配置 */}
          <div className="space-y-1.5">
            <Label>渲染引擎</Label>
            <Select value={renderEngine} onValueChange={(v) => v && setRenderEngine(v)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="manim">Manim</SelectItem>
                <SelectItem value="remotion">Remotion</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>TTS 声音</Label>
            <Select value={ttsVoice} onValueChange={(v) => v && setTtsVoice(v)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="alloy">Alloy</SelectItem>
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
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="landscape">横屏 16:9</SelectItem>
                <SelectItem value="portrait">竖屏 9:16</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* 风格配置 */}
          <div className="space-y-3 pt-1">
            <Label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              视频风格
            </Label>
            {STYLE_CATEGORIES.map(({ key, label }) => (
              <StyleSelect
                key={key}
                category={key}
                label={label}
                value={styleConfig[key] ?? ""}
                onChange={(v) => setStyleCategory(key, v)}
              />
            ))}
          </div>

          {/* 研究上下文 */}
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
