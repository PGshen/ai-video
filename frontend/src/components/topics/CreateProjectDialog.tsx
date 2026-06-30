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
  alloy: "Alloy",
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
  const [ttsVoice, setTtsVoice] = useState("alloy");
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
