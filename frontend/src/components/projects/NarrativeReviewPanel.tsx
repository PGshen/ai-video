import { useState, useMemo } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { FactCheckCard } from "@/components/review/FactCheckCard";
import { useSubmitReview } from "@/hooks/useProjects";
import { useRegenerateTts } from "@/hooks/useNarrative";
import type { NarrativeVersion, NarrativeScene, NarrativeBeat } from "@/types";

type Verdict = "approved" | "rejected" | "needs_revision";
interface VerdictState { verdict: Verdict; note: string; }

interface SceneState {
  narration: string;
  description: string;
  beats: NarrativeBeat[];
  audioPresignedUrl: string | null;
  durationSeconds: number | null;
  ttsStatus: NarrativeScene["ttsStatus"];
  alignmentCoverage: number | null;
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
          beats: s.beats,
          audioPresignedUrl: s.audioPresignedUrl ?? null,
          durationSeconds: s.durationSeconds ?? null,
          ttsStatus: s.ttsStatus ?? null,
          alignmentCoverage: s.alignmentCoverage ?? null,
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
  const [factVerdicts, setFactVerdicts] = useState<Record<number, VerdictState>>({});

  const updateBeat = (
    sceneIndex: number,
    beatIndex: number,
    patch: Partial<Pick<NarrativeBeat, "cueText" | "visualAction" | "emphasis" | "transition">>
  ) => {
    setSceneStates((prev) => {
      const next = new Map(prev);
      const cur = next.get(sceneIndex)!;
      const beats = cur.beats.map((beat) =>
        beat.beatIndex === beatIndex ? { ...beat, ...patch } : beat
      );
      const narration = beats.map((beat) => beat.cueText).join("");
      next.set(sceneIndex, { ...cur, beats, narration });
      return next;
    });
    if (patch.cueText !== undefined) {
      setDirtyTts((prev) => new Set(prev).add(sceneIndex));
      setRegenError((prev) => {
        const next = new Map(prev);
        next.delete(sceneIndex);
        return next;
      });
    }
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
        beats: state.beats,
      });
      setSceneStates((prev) => {
        const next = new Map(prev);
        next.set(idx, {
          ...next.get(idx)!,
          audioPresignedUrl: res.presignedUrl,
          durationSeconds: res.durationSeconds,
          ttsStatus: res.ttsStatus as NarrativeScene["ttsStatus"],
          beats: res.beats,
          alignmentCoverage: res.alignmentCoverage,
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
      beats: s.beats,
    }));

  const hasFailedTts = Array.from(sceneStates.values()).some(
    (s) => s.ttsStatus === "failed"
  );
  const hasFailedAlignment = Array.from(sceneStates.values()).some(
    (scene) =>
      scene.alignmentCoverage == null ||
      scene.beats.some(
        (beat) =>
          beat.alignmentStatus === "failed" ||
          beat.alignmentStatus === "pending"
      )
  );

  const allFactsMarked = useMemo(() => {
    if (narrative.factChecks.length === 0) return true;
    return narrative.factChecks.every((_, i) => factVerdicts[i] !== undefined);
  }, [narrative.factChecks, factVerdicts]);

  const buildFactVerdictList = () =>
    Object.entries(factVerdicts).map(([i, v]) => ({
      index: Number(i),
      verdict: v.verdict,
      note: v.note || "",
    }));

  const canSubmit =
    dirtyTts.size === 0 &&
    !hasFailedTts &&
    !hasFailedAlignment &&
    allFactsMarked;

  const handleApprove = () => {
    if (!canSubmit) return;
    submitReview.mutate({
      projectId,
      gate: "narrative",
      verdict: "approved",
      editedScenes: buildEditedScenes(),
      factCheckVerdicts: buildFactVerdictList(),
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
      factCheckVerdicts: buildFactVerdictList(),
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
                    {state.alignmentCoverage != null && (
                      <Badge variant="secondary" className="text-xs">
                        对齐 {(state.alignmentCoverage * 100).toFixed(0)}%
                      </Badge>
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
                      rows={3}
                      className="text-sm bg-muted/40"
                      readOnly
                    />
                    <p className="text-xs text-muted-foreground">
                      完整旁白由下方节拍文本自动拼接。
                    </p>
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

                  <div className="space-y-2">
                    <label className="text-xs font-medium text-muted-foreground">
                      语义节拍
                    </label>
                    {state.beats.map((beat) => (
                      <div key={beat.beatIndex} className="rounded-md border bg-muted/20 p-3 space-y-2">
                        <div className="flex items-center gap-2">
                          <Badge variant="outline">Beat {beat.beatIndex + 1}</Badge>
                          <Badge variant="secondary">{beat.alignmentStatus}</Badge>
                          {beat.speechStartSeconds != null && beat.speechEndSeconds != null && (
                            <span className="text-xs text-muted-foreground">
                              {beat.speechStartSeconds.toFixed(2)}s–{beat.speechEndSeconds.toFixed(2)}s
                            </span>
                          )}
                        </div>
                        <Textarea
                          value={beat.cueText}
                          onChange={(e) =>
                            updateBeat(scene.sceneIndex, beat.beatIndex, { cueText: e.target.value })
                          }
                          rows={2}
                          className="text-sm"
                          aria-label={`镜头 ${scene.sceneIndex} Beat ${beat.beatIndex + 1} 旁白`}
                        />
                        <Textarea
                          value={beat.visualAction}
                          onChange={(e) =>
                            updateBeat(scene.sceneIndex, beat.beatIndex, {
                              visualAction: e.target.value,
                            })
                          }
                          rows={2}
                          className="text-sm"
                          aria-label={`镜头 ${scene.sceneIndex} Beat ${beat.beatIndex + 1} 视觉动作`}
                        />
                        <div className="grid grid-cols-2 gap-2">
                          <input
                            value={beat.emphasis ?? ""}
                            onChange={(e) =>
                              updateBeat(scene.sceneIndex, beat.beatIndex, {
                                emphasis: e.target.value || null,
                              })
                            }
                            placeholder="强调对象（可选）"
                            className="h-9 rounded-md border bg-background px-3 text-sm"
                          />
                          <select
                            value={beat.transition}
                            onChange={(e) =>
                              updateBeat(scene.sceneIndex, beat.beatIndex, {
                                transition: e.target.value as NarrativeBeat["transition"],
                              })
                            }
                            className="h-9 rounded-md border bg-background px-3 text-sm"
                          >
                            <option value="continue">延续</option>
                            <option value="transform">变形</option>
                            <option value="reveal">揭示</option>
                            <option value="replace">替换</option>
                            <option value="exit">退场</option>
                          </select>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </ScrollArea>

        {/* Right: fact checks (interactive) */}
        <div className="w-80 shrink-0 border-l flex flex-col min-h-0 overflow-hidden">
          <div className="px-3 py-2.5 border-b text-xs font-semibold text-muted-foreground uppercase tracking-wide shrink-0">
            事实核查（{narrative.factChecks.length} 条）
          </div>
          <ScrollArea className="flex-1 min-h-0">
            <div className="p-3 space-y-3">
              {narrative.factChecks.length === 0 && (
                <p className="text-xs text-muted-foreground">暂无事实核查条目</p>
              )}
              {narrative.factChecks.map((fc, i) => (
                <FactCheckCard
                  key={i}
                  item={fc}
                  index={i}
                  verdict={factVerdicts[i]?.verdict ?? null}
                  note={factVerdicts[i]?.note ?? ""}
                  onVerdictChange={(idx, v, n) =>
                    setFactVerdicts((prev) => ({ ...prev, [idx]: { verdict: v, note: n } }))
                  }
                />
              ))}
            </div>
          </ScrollArea>
        </div>
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
        {hasFailedAlignment && (
          <p className="text-sm text-amber-600">
            有镜头尚未完成音画对齐，请重新生成音频后再提交。
          </p>
        )}
        {!allFactsMarked && narrative.factChecks.length > 0 && (
          <p className="text-sm text-amber-600">
            请为所有事实核查条目标注审核结果后再提交。
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
