import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useCreateProject } from "@/hooks/useProjects";
import type { Topic } from "@/types";

interface Props {
  topic: Topic;
  open: boolean;
  onClose: () => void;
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

export function CreateProjectDialog({ topic, open, onClose }: Props) {
  const [renderEngine, setRenderEngine] = useState("manim");
  const [ttsVoice, setTtsVoice] = useState("alloy");
  const [aspectRatio, setAspectRatio] = useState("landscape");
  const createProject = useCreateProject();
  const navigate = useNavigate();

  const handleSubmit = () => {
    createProject.mutate(
      { topicId: topic.id, renderEngine, ttsVoice, aspectRatio },
      {
        onSuccess: (_project) => {
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
