import { useState, useEffect } from "react";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetFooter } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { useUpdateTopic } from "@/hooks/useTopics";
import { CreateProjectDialog } from "./CreateProjectDialog";
import { TOPIC_STATUS_LABELS } from "@/lib/format";
import type { Topic, TopicScores } from "@/types";

interface Props {
  topic: Topic | null;
  onClose: () => void;
}

const SCORE_DIMENSIONS: { key: keyof TopicScores; label: string; topicKey: keyof Topic }[] = [
  { key: "counterintuitive", label: "反直觉度", topicKey: "scoreCounterintuitive" },
  { key: "defensibility", label: "可论证性", topicKey: "scoreDefensibility" },
  { key: "visual", label: "可视化性", topicKey: "scoreVisual" },
  { key: "freshness", label: "新鲜度", topicKey: "scoreFreshness" },
];

export function TopicSheet({ topic, onClose }: Props) {
  const updateTopic = useUpdateTopic();
  const [scores, setScores] = useState<TopicScores>({});
  const [status, setStatus] = useState("");
  const [tagsInput, setTagsInput] = useState("");
  const [createProjectOpen, setCreateProjectOpen] = useState(false);

  useEffect(() => {
    if (topic) {
      setScores({
        counterintuitive: topic.scoreCounterintuitive ?? undefined,
        defensibility: topic.scoreDefensibility ?? undefined,
        visual: topic.scoreVisual ?? undefined,
        freshness: topic.scoreFreshness ?? undefined,
      });
      setStatus(topic.status);
      setTagsInput(topic.tags.join(", "));
    }
  }, [topic]);

  const handleSave = () => {
    if (!topic) return;
    const tags = tagsInput.split(",").map((t) => t.trim()).filter(Boolean);
    updateTopic.mutate(
      { id: topic.id, scores, status, tags },
      { onSuccess: onClose }
    );
  };

  if (!topic) return null;

  return (
    <>
      <Sheet open={!!topic} onOpenChange={onClose}>
        <SheetContent className="w-[420px] sm:max-w-[420px] flex flex-col">
          <SheetHeader>
            <SheetTitle className="text-base leading-snug pr-6">{topic.title}</SheetTitle>
            {topic.description && (
              <p className="text-sm text-muted-foreground leading-relaxed">{topic.description}</p>
            )}
          </SheetHeader>

          <div className="flex-1 overflow-y-auto space-y-5 py-4">
            <div className="space-y-4">
              {SCORE_DIMENSIONS.map(({ key, label }) => (
                <div key={key} className="space-y-2">
                  <Label className="text-sm font-medium">{label}</Label>
                  <RadioGroup
                    value={String(scores[key] ?? "")}
                    onValueChange={(v) =>
                      setScores((prev) => ({ ...prev, [key]: Number(v) }))
                    }
                    className="flex gap-4"
                  >
                    {[1, 2, 3, 4, 5].map((n) => (
                      <div key={n} className="flex flex-col items-center gap-1">
                        <RadioGroupItem value={String(n)} id={`${key}-${n}`} />
                        <Label htmlFor={`${key}-${n}`} className="text-xs text-muted-foreground cursor-pointer">{n}</Label>
                      </div>
                    ))}
                  </RadioGroup>
                </div>
              ))}
            </div>

            <Separator />

            <div className="space-y-1.5">
              <Label>状态</Label>
              <Select value={status} onValueChange={(v) => v && setStatus(v)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {Object.entries(TOPIC_STATUS_LABELS).map(([val, label]) => (
                    <SelectItem key={val} value={val}>{label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label>标签（逗号分隔）</Label>
              <Input
                value={tagsInput}
                onChange={(e) => setTagsInput(e.target.value)}
                placeholder="科学, 物理"
              />
            </div>
          </div>

          <SheetFooter className="flex-col gap-2 sm:flex-col">
            <Button
              variant="outline"
              className="w-full"
              onClick={() => setCreateProjectOpen(true)}
            >
              从此选题创建项目
            </Button>
            <Button
              className="w-full"
              onClick={handleSave}
              disabled={updateTopic.isPending}
            >
              {updateTopic.isPending ? "保存中..." : "保存"}
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>

      {createProjectOpen && (
        <CreateProjectDialog
          topic={topic}
          open={createProjectOpen}
          onClose={() => setCreateProjectOpen(false)}
        />
      )}
    </>
  );
}
