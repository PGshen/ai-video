import { useState, useMemo } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Loader2, RefreshCw } from "lucide-react";
import { FactCheckCard } from "@/components/review/FactCheckCard";
import { useSubmitReview } from "@/hooks/useProjects";
import { useRegenerateTts } from "@/hooks/useNarrative";
import type {
  NarrativeVersion, NarrativeScene, NarrativeBeat, RejectionContext, SceneReviewAnnotation,
} from "@/types";

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

interface BatchRetryProgress {
  current: number;
  total: number;
  sceneIndex: number;
}

const normalizeAnnotations = (
  annotations: RejectionContext["scene_annotations"] | SceneReviewAnnotation[] | undefined,
): SceneReviewAnnotation[] => {
  if (!annotations) return [];
  return annotations
    .map((item) => {
      const raw = item as SceneReviewAnnotation & {
        scene_index?: number;
        narrative_issue?: string | null;
        code_issue?: string | null;
      };
      return {
        sceneIndex: raw.sceneIndex ?? raw.scene_index ?? -1,
        narrativeIssue: raw.narrativeIssue ?? raw.narrative_issue ?? null,
        codeIssue: raw.codeIssue ?? raw.code_issue ?? null,
      };
    })
    .filter((item) => item.sceneIndex >= 0 && (item.narrativeIssue || item.codeIssue));
};

function NarrativeRejectionContext({ context }: { context: RejectionContext | null }) {
  const annotations = normalizeAnnotations(context?.sceneAnnotations ?? context?.scene_annotations)
    .filter((annotation) => annotation.narrativeIssue);
  const detail = context?.rejectionDetail ?? context?.rejection_detail ?? null;
  if (!detail && annotations.length === 0) return null;

  return (
    <div className="mb-3 rounded-lg border border-amber-300/60 bg-amber-50 p-3">
      <p className="text-xs font-semibold text-amber-800">来自上次视频审核的叙事标注</p>
      {detail && <p className="mt-2 text-xs leading-relaxed text-amber-900">{detail}</p>}
      {annotations.length > 0 && (
        <div className="mt-2 grid gap-2 md:grid-cols-2">
          {annotations.map((annotation) => (
            <div key={annotation.sceneIndex} className="rounded-md border border-amber-200 bg-background/70 p-2 text-xs">
              <p className="font-medium text-foreground">镜头 {annotation.sceneIndex}</p>
              <p className="mt-1 text-muted-foreground">{annotation.narrativeIssue}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
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
  const [batchRetryProgress, setBatchRetryProgress] = useState<BatchRetryProgress | null>(null);
  const [batchRetryResult, setBatchRetryResult] = useState<string>("");
  const [regenError, setRegenError] = useState<Map<number, string>>(new Map());
  const [rejectionDetail, setRejectionDetail] = useState("");
  const [showRejectInput, setShowRejectInput] = useState(false);
  const [rejectionError, setRejectionError] = useState("");
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

  const handleRegenerateTts = async (idx: number): Promise<boolean> => {
    const state = sceneStates.get(idx);
    if (!state) return false;
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
      return true;
    } catch (err) {
      setRegenError((prev) => {
        const next = new Map(prev);
        next.set(idx, err instanceof Error ? err.message : "生成失败，请重试");
        return next;
      });
      return false;
    } finally {
      setRegeneratingIdx(null);
    }
  };

  const failedTtsIndices = useMemo(
    () =>
      Array.from(sceneStates.entries())
        .filter(([, state]) => state.ttsStatus === "failed")
        .map(([sceneIndex]) => sceneIndex)
        .sort((left, right) => left - right),
    [sceneStates]
  );

  const handleBatchRetryFailedTts = async () => {
    const indices = [...failedTtsIndices];
    if (indices.length === 0 || batchRetryProgress) return;

    setBatchRetryResult("");
    let succeeded = 0;
    for (let position = 0; position < indices.length; position += 1) {
      const sceneIndex = indices[position];
      setBatchRetryProgress({
        current: position + 1,
        total: indices.length,
        sceneIndex,
      });
      // 必须等待当前镜头完成后再处理下一个，避免并发请求 TTS。
      if (await handleRegenerateTts(sceneIndex)) succeeded += 1;
    }

    const failed = indices.length - succeeded;
    setBatchRetryProgress(null);
    setBatchRetryResult(
      failed === 0
        ? `已按顺序完成 ${succeeded} 个失败镜头的音频重试。`
        : `批量重试完成：${succeeded} 个成功，${failed} 个仍然失败。`
    );
  };

  const buildEditedScenes = () =>
    Array.from(sceneStates.entries()).map(([sceneIndex, s]) => ({
      sceneIndex,
      narration: s.narration,
      description: s.description,
      beats: s.beats,
    }));

  const hasFailedTts = failedTtsIndices.length > 0;
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
    const detail = rejectionDetail.trim();
    if (!detail) {
      setRejectionError("请填写内容驳回原因，AI 重新生成时会参考此信息。");
      return;
    }
    const inheritedAnnotations = normalizeAnnotations(
      narrative.rejectionContext?.sceneAnnotations ?? narrative.rejectionContext?.scene_annotations,
    );
    submitReview.mutate({
      projectId,
      gate: "narrative",
      verdict: "rejected",
      rejectionType: "content",
      rejectionDetail: detail,
      ...(inheritedAnnotations.length > 0 ? { sceneAnnotations: inheritedAnnotations } : {}),
    });
  };

  const handleAbandon = () => {
    submitReview.mutate({ projectId, gate: "narrative", verdict: "abandoned" });
  };

  return (
    <div className="flex flex-col h-full">
      <NarrativeRejectionContext context={narrative.rejectionContext} />
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
                        disabled={isRegenerating || batchRetryProgress !== null}
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
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-amber-300/60 bg-amber-50 px-3 py-2">
            <p className="text-sm text-amber-700">
              有 {failedTtsIndices.length} 个镜头 TTS 生成失败，请重新生成音频后再提交。
            </p>
            <Button
              size="sm"
              variant="outline"
              onClick={() => void handleBatchRetryFailedTts()}
              disabled={batchRetryProgress !== null}
            >
              {batchRetryProgress ? (
                <>
                  <Loader2 className="animate-spin" />
                  正在重试镜头 {batchRetryProgress.sceneIndex}（{batchRetryProgress.current}/{batchRetryProgress.total}）
                </>
              ) : (
                <>
                  <RefreshCw />
                  批量重试失败音频
                </>
              )}
            </Button>
          </div>
        )}
        {batchRetryResult && (
          <p className={`text-sm ${hasFailedTts ? "text-amber-600" : "text-emerald-600"}`}>
            {batchRetryResult}
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
          <div className="space-y-1">
            <Textarea
              placeholder="请说明对叙事内容不满意的地方，AI 重新生成时会参考此信息"
              value={rejectionDetail}
              onChange={(e) => {
                setRejectionDetail(e.target.value);
                if (e.target.value.trim()) setRejectionError("");
              }}
              rows={2}
              aria-label="内容驳回原因"
            />
            {rejectionError && (
              <p className="text-sm text-destructive">{rejectionError}</p>
            )}
          </div>
        )}
        {submitReview.isSuccess && (
          <p className="text-sm text-muted-foreground text-center animate-pulse">
            已提交，正在更新项目状态…
          </p>
        )}
        <div className="flex gap-2">
          <Button
            onClick={handleApprove}
            disabled={submitReview.isPending || submitReview.isSuccess || batchRetryProgress !== null || !canSubmit}
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
                setRejectionError("");
              }
            }}
            disabled={submitReview.isPending || submitReview.isSuccess || batchRetryProgress !== null}
          >
            {submitReview.isPending
              ? "提交中…"
              : showRejectInput
                ? "确认内容驳回"
                : "内容驳回"}
          </Button>
          <Button
            variant="ghost"
            onClick={handleAbandon}
            disabled={submitReview.isPending || submitReview.isSuccess || batchRetryProgress !== null}
          >
            废弃
          </Button>
        </div>
      </div>
    </div>
  );
}
