import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { useCreateProject } from "@/hooks/useProjects";
import { usePromptComponents } from "@/hooks/usePromptComponents";
import { useStyleTemplates } from "@/hooks/useStyleTemplates";
import { useTTSSettings } from "@/hooks/useTTSSettings";
import type { Topic } from "@/types";
import { STYLE_CATEGORIES } from "@/lib/styleCategories";

const RENDER_ENGINE_LABELS: Record<string, string> = {
  manim: "Manim",
  remotion: "Remotion",
};

const TTS_SPEEDS = [0.9, 1.0, 1.1, 1.2] as const;

const ASPECT_RATIO_LABELS: Record<string, string> = {
  landscape: "横屏 16:9",
  portrait: "竖屏 9:16",
};

interface Props {
  topic: Topic;
  open: boolean;
  onClose: () => void;
  onCreated?: () => void;
  contextSnippets?: string[];
}

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
  const selectedItem = items.find((item) => item.id === value);

  return (
    <div className="space-y-2">
      <Label className="text-xs font-medium">{label}</Label>
      <Select value={value} onValueChange={(v) => onChange(v ?? "")}>
        <SelectTrigger className="w-full bg-background">
          <SelectValue>{selectedItem?.name ?? "系统默认"}</SelectValue>
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
      {selectedItem?.description && (
        <p className="line-clamp-2 text-xs leading-5 text-muted-foreground">
          {selectedItem.description}
        </p>
      )}
    </div>
  );
}

export function CreateProjectDialog({ topic, open, onClose, onCreated, contextSnippets = [] }: Props) {
  const [renderEngine, setRenderEngine] = useState("manim");
  const [ttsVoice, setTtsVoice] = useState("春日部小姐姐");
  const [ttsEngine, setTtsEngine] = useState("doubao_2.0");
  const [ttsSpeed, setTtsSpeed] = useState<(typeof TTS_SPEEDS)[number]>(1.0);
  const [aspectRatio, setAspectRatio] = useState("landscape");
  const [styleConfig, setStyleConfig] = useState<Record<string, string>>({});
  const [selectedTemplateId, setSelectedTemplateId] = useState("");
  const [selectedSnippets, setSelectedSnippets] = useState<Set<number>>(
    () => new Set(contextSnippets.map((_, i) => i))
  );
  const createProject = useCreateProject();
  const navigate = useNavigate();
  const { data: templateData } = useStyleTemplates();
  const { data: ttsSettings, isLoading: ttsLoading } = useTTSSettings(true);
  const templates = templateData?.items ?? [];
  const ttsEngines = useMemo(() => ttsSettings?.engines ?? [], [ttsSettings]);
  const ttsVoices = (ttsSettings?.voices ?? []).filter((voice) => {
    const engine = ttsEngines.find((item) => item.id === voice.engineId);
    return engine?.code === ttsEngine;
  });
  const selectedTtsEngine = ttsEngines.find((engine) => engine.code === ttsEngine);
  const selectedTtsVoice = ttsVoices.find((voice) => voice.name === ttsVoice);
  const selectedTemplate = templates.find((item) => item.id === selectedTemplateId);

  function toggleSnippet(i: number) {
    setSelectedSnippets((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
  }

  function setStyleCategory(category: string, value: string) {
    setSelectedTemplateId("");
    setStyleConfig((prev) => {
      if (!value) {
        const next = { ...prev };
        delete next[category];
        return next;
      }
      return { ...prev, [category]: value };
    });
  }

  function applyTemplate(templateId: string) {
    setSelectedTemplateId(templateId);
    const template = templates.find((item) => item.id === templateId);
    setStyleConfig(template ? { ...template.styleConfig } : {});
  }

  useEffect(() => {
    if (!ttsEngines.length) return;
    setTtsEngine((currentEngine) => {
      const engine = ttsEngines.find((item) => item.code === currentEngine) ?? ttsEngines[0];
      const voices = (ttsSettings?.voices ?? []).filter((voice) => voice.engineId === engine.id);
      setTtsVoice((currentVoice) =>
        voices.some((voice) => voice.name === currentVoice)
          ? currentVoice
          : voices[0]?.name ?? ""
      );
      return engine.code;
    });
  }, [ttsSettings, ttsEngines]);

  function setTtsEngineAndVoice(engine: string) {
    setTtsEngine(engine);
    const config = ttsEngines.find((item) => item.code === engine);
    const voices = (ttsSettings?.voices ?? []).filter((voice) => voice.engineId === config?.id);
    setTtsVoice(voices[0]?.name ?? "");
  }

  const handleSubmit = () => {
    if (!ttsEngine || !ttsVoice) return;
    const narrativeContext = contextSnippets
      .filter((_, i) => selectedSnippets.has(i))
      .map((text) => ({ text }));
    createProject.mutate(
      { topicId: topic.id, renderEngine, ttsVoice, ttsEngine, ttsSpeed, aspectRatio, narrativeContext, styleConfig },
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
    <Dialog open={open} onOpenChange={(nextOpen) => !nextOpen && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto p-5 sm:max-w-3xl">
        <DialogHeader className="pr-8">
          <DialogTitle className="text-lg">从选题创建项目</DialogTitle>
          <DialogDescription>
            配置视频生成参数和风格组件，未选择的风格将使用系统默认值。
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-5 py-1">
          <div className="flex items-start gap-3 rounded-lg border bg-muted/40 px-4 py-3">
            <span className="mt-0.5 shrink-0 rounded-md bg-background px-2 py-0.5 text-xs font-medium text-muted-foreground ring-1 ring-foreground/10">
              选题
            </span>
            <p className="font-medium leading-5">{topic.title}</p>
          </div>

          <section className="space-y-3">
            <div>
              <h3 className="text-sm font-semibold">基础配置</h3>
              <p className="mt-0.5 text-xs text-muted-foreground">设置视频的生成方式与输出规格</p>
            </div>
            <div className="grid gap-4 rounded-xl border p-4 sm:grid-cols-3">
              <div className="space-y-2">
                <Label className="text-xs font-medium">渲染引擎</Label>
                <Select value={renderEngine} onValueChange={(v) => v && setRenderEngine(v)}>
                  <SelectTrigger className="w-full">
                    <SelectValue>{RENDER_ENGINE_LABELS[renderEngine]}</SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(RENDER_ENGINE_LABELS).map(([value, label]) => (
                      <SelectItem key={value} value={value}>{label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label className="text-xs font-medium">TTS 引擎</Label>
                <Select value={ttsEngine} onValueChange={(v) => v && setTtsEngineAndVoice(v)} disabled={ttsLoading || !ttsEngines.length}>
                  <SelectTrigger className="w-full">
                    <SelectValue>{selectedTtsEngine?.name ?? (ttsLoading ? "加载中…" : "暂无可用引擎")}</SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {ttsEngines.map((engine) => <SelectItem key={engine.id} value={engine.code}>{engine.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label className="text-xs font-medium">TTS 音色</Label>
                <Select value={ttsVoice} onValueChange={(v) => v && setTtsVoice(v)} disabled={!ttsVoices.length}>
                  <SelectTrigger className="w-full">
                    <SelectValue>{selectedTtsVoice?.name ?? "暂无可用音色"}</SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {ttsVoices.map((voice) => <SelectItem key={voice.id} value={voice.name}>{voice.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label className="text-xs font-medium">TTS 语速</Label>
                <Select value={String(ttsSpeed)} onValueChange={(v) => setTtsSpeed(Number(v) as (typeof TTS_SPEEDS)[number])}>
                  <SelectTrigger className="w-full">
                    <SelectValue>{ttsSpeed.toFixed(1) + " 倍速"}</SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {TTS_SPEEDS.map((speed) => (
                      <SelectItem key={speed} value={String(speed)}>{speed.toFixed(1)} 倍速</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label className="text-xs font-medium">画幅比例</Label>
                <Select value={aspectRatio} onValueChange={(v) => v && setAspectRatio(v)}>
                  <SelectTrigger className="w-full">
                    <SelectValue>{ASPECT_RATIO_LABELS[aspectRatio]}</SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(ASPECT_RATIO_LABELS).map(([value, label]) => (
                      <SelectItem key={value} value={value}>{label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </section>

          <section className="space-y-3">
            <div>
              <h3 className="text-sm font-semibold">风格组件</h3>
              <p className="mt-0.5 text-xs text-muted-foreground">
                先套用模板快速组合，也可以继续逐项调整
              </p>
            </div>
            <div className="space-y-4 rounded-xl border bg-muted/20 p-4">
              <div className="space-y-2 border-b pb-4">
                <div className="flex items-center justify-between gap-3">
                  <Label className="text-xs font-medium">风格模板</Label>
                  {selectedTemplate && (
                    <span className="text-xs text-muted-foreground">
                      已关联 {Object.keys(selectedTemplate.styleConfig).length} 个组件
                    </span>
                  )}
                </div>
                <Select
                  value={selectedTemplateId}
                  onValueChange={(value) => applyTemplate(value ?? "")}
                >
                  <SelectTrigger className="w-full bg-background">
                    <SelectValue>{selectedTemplate?.name ?? "不使用模板，逐项选择"}</SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="">不使用模板，逐项选择</SelectItem>
                    {templates.map((template) => (
                      <SelectItem key={template.id} value={template.id}>
                        {template.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {selectedTemplate?.description && (
                  <p className="text-xs leading-5 text-muted-foreground">
                    {selectedTemplate.description}
                  </p>
                )}
              </div>

              <div className="grid gap-x-4 gap-y-4 sm:grid-cols-3">
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
            </div>
          </section>

          {contextSnippets.length > 0 && (
            <section className="space-y-3">
              <div>
                <h3 className="text-sm font-semibold">研究上下文</h3>
                <p className="mt-0.5 text-xs text-muted-foreground">选择需要带入叙事生成的内容</p>
              </div>
              <div className="max-h-40 space-y-1 overflow-y-auto rounded-xl border p-3">
                {contextSnippets.map((snippet, i) => (
                  <div key={i} className="flex items-start gap-2 rounded-md px-2 py-1.5 hover:bg-muted/60">
                    <Checkbox
                      id={`snippet-${i}`}
                      checked={selectedSnippets.has(i)}
                      onCheckedChange={() => toggleSnippet(i)}
                      className="mt-0.5 shrink-0"
                    />
                    <label
                      htmlFor={`snippet-${i}`}
                      className="line-clamp-2 cursor-pointer text-xs leading-5 text-muted-foreground"
                    >
                      {snippet}
                    </label>
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>

        <DialogFooter className="bg-background">
          <Button variant="outline" onClick={onClose}>取消</Button>
          <Button onClick={handleSubmit} disabled={createProject.isPending || !ttsEngine || !ttsVoice}>
            {createProject.isPending ? "创建中..." : "创建项目"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
