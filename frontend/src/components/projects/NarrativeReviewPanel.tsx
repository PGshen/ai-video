import { useState } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { useSubmitReview } from "@/hooks/useProjects";
import type { NarrativeVersion } from "@/types";

interface Props {
  projectId: string;
  narrative: NarrativeVersion;
}

export function NarrativeReviewPanel({ projectId, narrative }: Props) {
  const submitReview = useSubmitReview();

  const [editedScenes, setEditedScenes] = useState<
    Map<number, { narration: string; description: string }>
  >(
    new Map(
      narrative.scenes.map((s) => [
        s.sceneIndex,
        { narration: s.narration, description: s.description },
      ])
    )
  );

  const [rejectionDetail, setRejectionDetail] = useState("");
  const [showRejectInput, setShowRejectInput] = useState(false);

  const updateScene = (
    idx: number,
    field: "narration" | "description",
    value: string
  ) => {
    setEditedScenes((prev) => {
      const next = new Map(prev);
      next.set(idx, { ...next.get(idx)!, [field]: value });
      return next;
    });
  };

  const buildEditedScenes = () =>
    Array.from(editedScenes.entries()).map(([sceneIndex, vals]) => ({
      sceneIndex,
      ...vals,
    }));

  const handleApprove = () => {
    submitReview.mutate({
      projectId,
      gate: "narrative",
      verdict: "approved",
      editedScenes: buildEditedScenes(),
    });
  };

  const handleReject = () => {
    submitReview.mutate({
      projectId,
      gate: "narrative",
      verdict: "rejected",
      rejectionDetail,
      editedScenes: buildEditedScenes(),
    });
  };

  const handleAbandon = () => {
    submitReview.mutate({
      projectId,
      gate: "narrative",
      verdict: "abandoned",
    });
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex flex-1 overflow-hidden gap-4">
        {/* Left: scene list */}
        <ScrollArea className="flex-1">
          <div className="space-y-4 pr-2">
            {narrative.scenes.map((scene) => {
              const edited = editedScenes.get(scene.sceneIndex)!;
              return (
                <div
                  key={scene.sceneIndex}
                  className="border rounded-lg p-4 space-y-3"
                >
                  <div className="flex items-center gap-2">
                    <Badge variant="outline">镜头 {scene.sceneIndex}</Badge>
                    {scene.estimatedDurationSeconds && (
                      <span className="text-xs text-muted-foreground">
                        {scene.estimatedDurationSeconds}s
                      </span>
                    )}
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-medium text-muted-foreground">
                      旁白
                    </label>
                    <Textarea
                      value={edited.narration}
                      onChange={(e) =>
                        updateScene(scene.sceneIndex, "narration", e.target.value)
                      }
                      rows={3}
                      className="text-sm"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-medium text-muted-foreground">
                      画面描述
                    </label>
                    <Textarea
                      value={edited.description}
                      onChange={(e) =>
                        updateScene(scene.sceneIndex, "description", e.target.value)
                      }
                      rows={4}
                      className="text-sm"
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </ScrollArea>

        {/* Right: fact checks (read-only) */}
        <ScrollArea className="w-72 shrink-0">
          <div className="space-y-3 pr-1">
            <p className="text-xs font-medium text-muted-foreground">
              事实核查（将在代码审核阶段标注）
            </p>
            {narrative.factChecks.map((fc, i) => (
              <div key={i} className="border rounded-lg p-3 space-y-1">
                <p className="text-xs">{fc.claimText}</p>
                <Badge
                  variant={
                    fc.confidence === "high"
                      ? "default"
                      : fc.confidence === "low"
                      ? "destructive"
                      : "secondary"
                  }
                  className="text-xs"
                >
                  {fc.confidence}
                </Badge>
                <p className="text-xs text-muted-foreground">
                  {fc.sourceDescription}
                </p>
              </div>
            ))}
          </div>
        </ScrollArea>
      </div>

      {/* Bottom action bar */}
      <div className="border-t pt-4 mt-4 space-y-3">
        {showRejectInput && (
          <Textarea
            placeholder="请说明驳回原因..."
            value={rejectionDetail}
            onChange={(e) => setRejectionDetail(e.target.value)}
            rows={2}
          />
        )}
        <div className="flex gap-2">
          <Button
            onClick={handleApprove}
            disabled={submitReview.isPending}
            className="flex-1"
          >
            确认通过（进入代码生成）
          </Button>
          <Button
            variant="outline"
            onClick={() => {
              if (showRejectInput) {
                handleReject();
              } else {
                setShowRejectInput(true);
              }
            }}
            disabled={submitReview.isPending}
          >
            驳回重生成
          </Button>
          <Button
            variant="ghost"
            onClick={handleAbandon}
            disabled={submitReview.isPending}
          >
            废弃
          </Button>
        </div>
      </div>
    </div>
  );
}
