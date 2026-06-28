import { useState } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { useSubmitReview } from "@/hooks/useProjects";
import { useRegenerateTts } from "@/hooks/useNarrative";
import type { NarrativeVersion, NarrativeScene } from "@/types";

interface SceneState {
  narration: string;
  description: string;
  audioPresignedUrl: string | null;
  durationSeconds: number | null;
  ttsStatus: NarrativeScene["ttsStatus"];
}

interface Props {
  projectId: string;
  narrative: NarrativeVersion;
}

export function NarrativeReviewPanel({ projectId, narrative }: Props) {
  const submitReview = useSubmitReview();
  const regenerateTts = useRegenerateTts(projectId);

  const [sceneStates, setSceneStates] = useState<Map<number, SceneState>>(
    new Map(
      narrative.scenes.map((s) => [
        s.sceneIndex,
        {
          narration: s.narration,
          description: s.description,
          audioPresignedUrl: s.audioPresignedUrl ?? null,
          durationSeconds: s.durationSeconds ?? null,
          ttsStatus: s.ttsStatus ?? null,
        },
      ])
    )
  );

  // 记录哪些镜头的旁白被用户修改但尚未重新 TTS
  const [dirtyTts, setDirtyTts] = useState<Set<number>>(new Set());
  const [regeneratingIdx, setRegeneratingIdx] = useState<number | null>(null);
  const [regenError, setRegenError] = useState<Map<number, string>>(new Map());
  const [rejectionDetail, setRejectionDetail] = useState("");
  const [showRejectInput, setShowRejectInput] = useState(false);

  const updateNarration = (idx: number, value: string) => {
    setSceneStates((prev) => {
      const next = new Map(prev);
      const cur = next.get(idx)!;
      next.set(idx, { ...cur, narration: value });
      return next;
    });
    setDirtyTts((prev) => new Set(prev).add(idx));
    // Clear error when user edits narration
    setRegenError((prev) => {
      const next = new Map(prev);
      next.delete(idx);
      return next;
    });
  };

  const updateDescription = (idx: number, value: string) => {
    setSceneStates((prev) => {
      const next = new Map(prev);
      const cur = next.get(idx)!;
      next.set(idx, { ...cur, description: value });
      return next;
    });
  };

  const handleRegenerateTts = async (idx: number) => {
    const state = sceneStates.get(idx);
    if (!state) return;
    setRegeneratingIdx(idx);
    try {
      const res = await regenerateTts.mutateAsync({
        sceneIndex: idx,
        narration: state.narration,
      });
      setSceneStates((prev) => {
        const next = new Map(prev);
        next.set(idx, {
          ...next.get(idx)!,
          audioPresignedUrl: res.presignedUrl,
          durationSeconds: res.durationSeconds,
          ttsStatus: res.ttsStatus as NarrativeScene["ttsStatus"],
        });
        return next;
      });
      setDirtyTts((prev) => {
        const next = new Set(prev);
        next.delete(idx);
        return next;
      });
      // Clear error on success
      setRegenError((prev) => {
        const next = new Map(prev);
        next.delete(idx);
        return next;
      });
    } catch (err) {
      setRegenError((prev) => {
        const next = new Map(prev);
        next.set(idx, err instanceof Error ? err.message : "生成失败，请重试");
        return next;
      });
    } finally {
      setRegeneratingIdx(null);
    }
  };

  const buildEditedScenes = () =>
    Array.from(sceneStates.entries()).map(([sceneIndex, s]) => ({
      sceneIndex,
      narration: s.narration,
      description: s.description,
    }));

  const hasFailedTts = Array.from(sceneStates.values()).some(
    (s) => s.ttsStatus === "failed"
  );
  const canSubmit = dirtyTts.size === 0 && !hasFailedTts;

  const handleApprove = () => {
    if (!canSubmit) return;
    submitReview.mutate({
      projectId,
      gate: "narrative",
      verdict: "approved",
      editedScenes: buildEditedScenes(),
    });
  };

  const handleReject = () => {
    if (!canSubmit) return;
    submitReview.mutate({
      projectId,
      gate: "narrative",
      verdict: "rejected",
      rejectionDetail,
      editedScenes: buildEditedScenes(),
    });
  };

  const handleAbandon = () => {
    submitReview.mutate({ projectId, gate: "narrative", verdict: "abandoned" });
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex flex-1 overflow-hidden gap-4">
        {/* Left: scene list */}
        <ScrollArea className="flex-1">
          <div className="space-y-4 pr-2">
            {narrative.scenes.map((scene) => {
              const state = sceneStates.get(scene.sceneIndex)!;
              const isDirty = dirtyTts.has(scene.sceneIndex);
              const isRegenerating = regeneratingIdx === scene.sceneIndex;

              return (
                <div
                  key={scene.sceneIndex}
                  className="border rounded-lg p-4 space-y-3"
                >
                  <div className="flex items-center gap-2">
                    <Badge variant="outline">镜头 {scene.sceneIndex}</Badge>
                    {state.durationSeconds != null && (
                      <span className="text-xs text-muted-foreground">
                        旁白时长：{state.durationSeconds.toFixed(1)}s
                      </span>
                    )}
                    {state.ttsStatus === "failed" && (
                      <Badge variant="destructive" className="text-xs">TTS 失败</Badge>
                    )}
                  </div>

                  {/* 音频播放器 */}
                  {state.audioPresignedUrl && !isDirty && (
                    <audio
                      controls
                      src={state.audioPresignedUrl}
                      className="w-full h-10"
                    />
                  )}

                  <div className="space-y-1">
                    <label className="text-xs font-medium text-muted-foreground">旁白</label>
                    <Textarea
                      value={state.narration}
                      onChange={(e) => updateNarration(scene.sceneIndex, e.target.value)}
                      rows={3}
                      className="text-sm"
                    />
                  </div>

                  {isDirty && (
                    <div className="space-y-1">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleRegenerateTts(scene.sceneIndex)}
                        disabled={isRegenerating}
                      >
                        {isRegenerating ? "生成中…" : "重新生成音频"}
                      </Button>
                      {regenError.get(scene.sceneIndex) && (
                        <p className="text-xs text-destructive">{regenError.get(scene.sceneIndex)}</p>
                      )}
                    </div>
                  )}

                  <div className="space-y-1">
                    <label className="text-xs font-medium text-muted-foreground">画面描述</label>
                    <Textarea
                      value={state.description}
                      onChange={(e) => updateDescription(scene.sceneIndex, e.target.value)}
                      rows={4}
                      className="text-sm"
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </ScrollArea>

        {/* Right: fact checks */}
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
                <p className="text-xs text-muted-foreground">{fc.sourceDescription}</p>
              </div>
            ))}
          </div>
        </ScrollArea>
      </div>

      {/* Bottom action bar */}
      <div className="border-t pt-4 mt-4 space-y-3">
        {dirtyTts.size > 0 && (
          <p className="text-sm text-amber-600">
            有 {dirtyTts.size} 个镜头修改了旁白，请先点击「重新生成音频」再提交。
          </p>
        )}
        {hasFailedTts && (
          <p className="text-sm text-amber-600">
            有镜头 TTS 生成失败，请重新生成音频后再提交。
          </p>
        )}
        {showRejectInput && (
          <Textarea
            placeholder="请说明驳回原因..."
            value={rejectionDetail}
            onChange={(e) => setRejectionDetail(e.target.value)}
            rows={2}
          />
        )}
        {submitReview.isSuccess && (
          <p className="text-sm text-muted-foreground text-center animate-pulse">
            已提交，正在切换到代码生成阶段…
          </p>
        )}
        <div className="flex gap-2">
          <Button
            onClick={handleApprove}
            disabled={submitReview.isPending || submitReview.isSuccess || !canSubmit}
            className="flex-1"
          >
            {submitReview.isPending ? "提交中…" : "确认通过（进入代码生成）"}
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
            disabled={submitReview.isPending || submitReview.isSuccess || !canSubmit}
          >
            {submitReview.isPending ? "提交中…" : "驳回重生成"}
          </Button>
          <Button
            variant="ghost"
            onClick={handleAbandon}
            disabled={submitReview.isPending || submitReview.isSuccess}
          >
            废弃
          </Button>
        </div>
      </div>
    </div>
  );
}
