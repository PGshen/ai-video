import { useState, useEffect } from "react";
import { Check, PackagePlus, X } from "lucide-react";
import { SidePanel, SidePanelHeader, SidePanelBody } from "@/components/ui/side-panel";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useUpdateTopic } from "@/hooks/useTopics";
import { CreateProjectDialog } from "./CreateProjectDialog";
import { TOPIC_STATUS_LABELS } from "@/lib/format";
import type { Topic, TopicScores } from "@/types";
import { ResearchChat } from "./ResearchChat";

interface Props {
  topic: Topic | null;
  onClose: () => void;
}

const SCORE_DIMENSIONS: { key: keyof TopicScores; label: string; desc: string }[] = [
  { key: "counterintuitive", label: "反直觉度", desc: "颠覆常识的程度" },
  { key: "defensibility",   label: "可论证性", desc: "能否用数据/逻辑支撑" },
  { key: "visual",          label: "可视化性", desc: "画面表达的可能性" },
  { key: "freshness",       label: "新鲜度",   desc: "话题的时效与独特性" },
];

const SCORE_LABELS: Record<number, string> = { 1: "差", 2: "弱", 3: "中", 4: "好", 5: "优" };

function ScorePicker({
  value,
  onChange,
}: {
  value: number | undefined;
  onChange: (v: number) => void;
}) {
  return (
    <div className="flex gap-1.5">
      {[1, 2, 3, 4, 5].map((n) => {
        const selected = value === n;
        return (
          <button
            key={n}
            type="button"
            onClick={() => onChange(n)}
            className={[
              "flex flex-col items-center justify-center w-10 h-10 rounded-lg text-xs font-medium border transition-all",
              selected
                ? "bg-foreground text-background border-foreground"
                : "bg-background text-muted-foreground border-border hover:border-foreground/40 hover:text-foreground",
            ].join(" ")}
          >
            <span className="text-sm font-semibold leading-none">{n}</span>
            <span className="text-[10px] leading-none mt-0.5 opacity-70">{SCORE_LABELS[n]}</span>
          </button>
        );
      })}
    </div>
  );
}

export function TopicSheet({ topic, onClose }: Props) {
  const updateTopic = useUpdateTopic();
  const [displayTopic, setDisplayTopic] = useState<Topic | null>(topic);
  const [scores, setScores] = useState<TopicScores>({});
  const [tagsInput, setTagsInput] = useState("");
  const [createProjectOpen, setCreateProjectOpen] = useState(false);

  useEffect(() => {
    if (topic) {
      setDisplayTopic(topic);
      setScores({
        counterintuitive: topic.scoreCounterintuitive ?? undefined,
        defensibility: topic.scoreDefensibility ?? undefined,
        visual: topic.scoreVisual ?? undefined,
        freshness: topic.scoreFreshness ?? undefined,
      });
      setTagsInput(topic.tags.join(", "));
    }
  }, [topic]);

  const buildTopicUpdate = (status: Topic["status"]) => {
    const tags = tagsInput.split(",").map((t) => t.trim()).filter(Boolean);
    return { scores, status, tags };
  };

  const handleStatusAction = (status: Topic["status"]) => {
    if (!displayTopic) return;
    updateTopic.mutate(
      { id: displayTopic.id, ...buildTopicUpdate(status) },
      {
        onSuccess: (updatedTopic) => {
          setDisplayTopic(updatedTopic);
          setScores({
            counterintuitive: updatedTopic.scoreCounterintuitive ?? undefined,
            defensibility: updatedTopic.scoreDefensibility ?? undefined,
            visual: updatedTopic.scoreVisual ?? undefined,
            freshness: updatedTopic.scoreFreshness ?? undefined,
          });
          setTagsInput(updatedTopic.tags.join(", "));
        },
      }
    );
  };

  if (!displayTopic) return null;

  const compositeScore = displayTopic.compositeScore;
  const isStocked = displayTopic.status === "stocked";
  const isInProduction = displayTopic.status === "in_production";
  const isUpdating = updateTopic.isPending;
  const allScoresFilled = SCORE_DIMENSIONS.every(({ key }) => scores[key] !== undefined);

  return (
    <>
      <SidePanel open={!!topic} onClose={onClose} wide>
        {/* Header */}
        <SidePanelHeader>
          <div className="flex items-start justify-between gap-3 pr-7">
            <h2 className="text-base font-semibold leading-snug">{displayTopic.title}</h2>
            {compositeScore !== null && (
              <span className="shrink-0 mt-0.5 text-xs font-medium px-2 py-0.5 rounded-full bg-muted text-muted-foreground">
                综合 {compositeScore?.toFixed(1)}
              </span>
            )}
          </div>
          {displayTopic.description && (
            <p className="text-sm text-muted-foreground leading-relaxed mt-1">{displayTopic.description}</p>
          )}
          {displayTopic.tags.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2">
              {displayTopic.tags.map((tag) => (
                <Badge key={tag} variant="secondary" className="text-xs">{tag}</Badge>
              ))}
            </div>
          )}
        </SidePanelHeader>

        {/* Scrollable body */}
        <SidePanelBody className="p-0 overflow-hidden">
          <div className="grid grid-cols-[minmax(0,1fr)_320px] h-full">
            {/* Left: Research Assistant */}
            <div className="flex flex-col min-h-0 min-w-0 px-5 py-5 border-r">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">
                研究助手
              </p>
              <ResearchChat topic={displayTopic} />
            </div>

            {/* Right: Scoring + Meta */}
            <div className="min-w-0 overflow-y-auto px-5 py-5 space-y-6">
              {/* Scoring */}
              <section className="space-y-4">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">打分</p>
                {SCORE_DIMENSIONS.map(({ key, label, desc }) => (
                  <div key={key} className="space-y-2">
                    <div className="flex items-baseline gap-2">
                      <Label className="text-sm font-medium">{label}</Label>
                      <span className="text-xs text-muted-foreground">{desc}</span>
                    </div>
                    <ScorePicker
                      value={scores[key]}
                      onChange={(v) => setScores((prev) => ({ ...prev, [key]: v }))}
                    />
                  </div>
                ))}
                <div className="border-t pt-4 space-y-3">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">操作</p>
                    <Badge variant="secondary" className="text-xs">
                      {TOPIC_STATUS_LABELS[displayTopic.status] ?? displayTopic.status}
                    </Badge>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => handleStatusAction("stocked")}
                      disabled={isUpdating || isInProduction || !allScoresFilled}
                    >
                      <Check className="size-4" />
                      通过
                    </Button>
                    <Button
                      type="button"
                      variant="destructive"
                      onClick={() => handleStatusAction("abandoned")}
                      disabled={isUpdating || isInProduction || !allScoresFilled}
                    >
                      <X className="size-4" />
                      废弃
                    </Button>
                  </div>
                  <Button
                    type="button"
                    className="w-full"
                    onClick={() => setCreateProjectOpen(true)}
                    disabled={!isStocked || isUpdating}
                  >
                    <PackagePlus className="size-4" />
                    创建项目
                  </Button>
                  {!isStocked && !isInProduction && (
                    <p className="text-xs text-muted-foreground">
                      {allScoresFilled ? "通过后可创建项目。" : "完成全部打分后可通过或废弃。"}
                    </p>
                  )}
                  {isInProduction && (
                    <p className="text-xs text-muted-foreground">项目已创建，选题正在制作中。</p>
                  )}
                </div>
              </section>

              {/* Meta */}
              <section className="space-y-4">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">元数据</p>
                <div className="space-y-1.5">
                  <Label className="text-sm">标签</Label>
                  <Input
                    value={tagsInput}
                    onChange={(e) => setTagsInput(e.target.value)}
                    placeholder="科学, 物理, 认知"
                    className="text-sm"
                  />
                  <p className="text-xs text-muted-foreground">逗号分隔多个标签</p>
                </div>
              </section>
            </div>
          </div>
        </SidePanelBody>
      </SidePanel>

      {createProjectOpen && (
        <CreateProjectDialog
          topic={displayTopic}
          open={createProjectOpen}
          onClose={() => setCreateProjectOpen(false)}
          onCreated={() =>
            setDisplayTopic((prev) =>
              prev ? { ...prev, status: "in_production" } : prev
            )
          }
        />
      )}
    </>
  );
}
