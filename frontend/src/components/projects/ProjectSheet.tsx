import { useState, useMemo, useRef } from "react";
import { toast } from "sonner";
import { SidePanel, SidePanelHeader } from "@/components/ui/side-panel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Textarea } from "@/components/ui/textarea";
import { FactCheckCard } from "@/components/review/FactCheckCard";
import { NarrativeReviewPanel } from "@/components/projects/NarrativeReviewPanel";
import {
  useProject, useProjectEvents, useProjectScript, useSubmitReview,
  useNarrativeVersions, useNarrativeVersion,
  useScriptVersions, useScriptVersion, useVideoUrl,
} from "@/hooks/useProjects";
import { useNarrative } from "@/hooks/useNarrative";
import { PROJECT_STATUS_LABELS, PROJECT_STATUS_COLORS, timeAgo } from "@/lib/format";
import type { VideoProject, ProjectEvent, NarrativeVersion, ScriptVersion } from "@/types";

type Verdict = "approved" | "rejected" | "needs_revision";
interface VerdictState { verdict: Verdict; note: string; }

interface Props {
  project: VideoProject | null;
  onClose: () => void;
}

const EVENT_TYPE_LABELS: Record<string, string> = {
  status_change: "状态变更",
  signal_sent: "信号发送",
};

interface SelectedNode {
  type: "narrative" | "script";
  versionId: string;
  versionNumber: number;
}

export function ProjectSheet({ project, onClose }: Props) {
  // Keep the last non-null project so SidePanel's exit animation has content to render
  const lastProjectRef = useRef<VideoProject | null>(null);
  if (project) lastProjectRef.current = project;
  const displayProject = project ?? lastProjectRef.current;

  // Fetch full project detail (includes currentVideoAsset); list endpoint omits it
  const { data: projectDetail } = useProject(displayProject?.id ?? "");

  const { data: eventsData } = useProjectEvents(displayProject?.id ?? "");
  const { data: script, isLoading: scriptLoading } = useProjectScript(displayProject?.id ?? "");
  const { data: narrative } = useNarrative(displayProject?.id ?? "");
  const { data: narrativeVersions = [] } = useNarrativeVersions(displayProject?.id ?? "");
  const { data: scriptVersions = [] } = useScriptVersions(displayProject?.id ?? "");
  const { data: videoUrlData } = useVideoUrl(
    displayProject?.id ?? "",
    projectDetail?.currentVideoAsset?.id ?? null,
  );
  const submitReview = useSubmitReview();

  const [selectedNode, setSelectedNode] = useState<SelectedNode | null>(null);
  const [verdicts, setVerdicts] = useState<Record<number, VerdictState>>({});
  const [rejectionDetail, setRejectionDetail] = useState("");
  const [showRejectInput, setShowRejectInput] = useState(false);
  const [targetStage, setTargetStage] = useState<"narrative" | "code">("narrative");
  const [submitted, setSubmitted] = useState(false);

  // Fetch selected historical version on demand
  const { data: selectedNarrativeVersion } = useNarrativeVersion(
    displayProject?.id ?? "",
    selectedNode?.type === "narrative" ? selectedNode.versionId : null,
  );
  const { data: selectedScriptVersion } = useScriptVersion(
    displayProject?.id ?? "",
    selectedNode?.type === "script" ? selectedNode.versionId : null,
  );

  const isScriptReview = project?.status === "script_review";
  const hasScript = !!script;

  const allMarked = useMemo(() => {
    if (!script || script.factChecks.length === 0) return true;
    return script.factChecks.every((_, i) => verdicts[i] !== undefined);
  }, [script, verdicts]);

  const buildVerdictList = () =>
    Object.entries(verdicts).map(([i, v]) => ({
      index: Number(i),
      verdict: v.verdict,
      note: v.note || "",
    }));

  const handleApprove = () => {
    if (!project) return;
    submitReview.mutate(
      { projectId: project.id, gate: "script", verdict: "approved", factCheckVerdicts: buildVerdictList() },
      {
        onSuccess: () => { setSubmitted(true); toast.success("审核已通过，AI 正在生成代码…"); },
        onError: () => toast.error("提交失败，请重试"),
      },
    );
  };

  const handleReject = () => {
    if (!project) return;
    if (!showRejectInput) { setShowRejectInput(true); return; }
    submitReview.mutate(
      { projectId: project.id, gate: "script", verdict: "rejected", rejectionDetail, targetStage, factCheckVerdicts: buildVerdictList() },
      {
        onSuccess: () => { setSubmitted(true); toast.success("已驳回，AI 将重新生成"); },
        onError: () => toast.error("提交失败，请重试"),
      },
    );
  };

  const handleAbandon = () => {
    if (!project) return;
    if (!window.confirm("确认废弃该项目？此操作不可撤销。")) return;
    submitReview.mutate(
      { projectId: project.id, gate: "script", verdict: "abandoned" },
      {
        onSuccess: () => { setSubmitted(true); toast.info("项目已废弃"); },
        onError: () => toast.error("操作失败，请重试"),
      },
    );
  };

  const handleVideoApprove = () => {
    if (!project) return;
    submitReview.mutate(
      { projectId: project.id, gate: "video", verdict: "approved" },
      {
        onSuccess: () => { setSubmitted(true); toast.success("视频已通过审核，准备发布"); },
        onError: () => toast.error("提交失败，请重试"),
      },
    );
  };

  const handleVideoRetry = () => {
    if (!project) return;
    submitReview.mutate(
      { projectId: project.id, gate: "video", verdict: "retry" },
      {
        onSuccess: () => { setSubmitted(false); toast.info("已触发重新生成视频"); },
        onError: () => toast.error("操作失败，请重试"),
      },
    );
  };

  const handleVideoAbandon = () => {
    if (!project) return;
    if (!window.confirm("确认废弃该项目？此操作不可撤销。")) return;
    submitReview.mutate(
      { projectId: project.id, gate: "video", verdict: "abandoned" },
      {
        onSuccess: () => { setSubmitted(true); toast.info("项目已废弃"); },
        onError: () => toast.error("操作失败，请重试"),
      },
    );
  };

  if (!displayProject) return null;

  const statusColor = PROJECT_STATUS_COLORS[displayProject.status] ?? "bg-gray-100 text-gray-600";
  const statusLabel = PROJECT_STATUS_LABELS[displayProject.status] ?? displayProject.status;
  const canReject = displayProject.retryCount < 3;

  return (
    <SidePanel open={!!project} onClose={onClose} widthClass="w-[90vw] max-w-[95vw]">
      <SidePanelHeader>
        <div className="pr-7 flex items-start justify-between">
          <div>
            <h2 className="text-base font-semibold leading-snug">{displayProject.topicTitle}</h2>
            <div className="flex items-center gap-2 mt-2">
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${statusColor}`}>
                {statusLabel}
              </span>
              {displayProject.retryCount > 0 && (
                <span className="text-xs text-muted-foreground">已驳回 {displayProject.retryCount} 次</span>
              )}
            </div>
          </div>
        </div>
      </SidePanelHeader>

      {/* 主体：左栏固定 + 右栏弹性 */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* 左栏：元数据 + 时间线 */}
        <div className="w-72 shrink-0 border-r flex min-h-0 flex-col overflow-hidden p-5">
          <MetaSection project={displayProject} />
          <EventsSection
            eventsData={eventsData}
            narrativeVersions={narrativeVersions}
            scriptVersions={scriptVersions}
            selectedNode={selectedNode}
            onSelectNode={setSelectedNode}
          />
        </div>

        {/* 右栏：历史视图 or 当前审核视图 */}
        <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
          {selectedNode ? (
            <HistoricalView
              node={selectedNode}
              narrativeVersion={selectedNarrativeVersion ?? null}
              scriptVersion={selectedScriptVersion ?? null}
              onClose={() => setSelectedNode(null)}
            />
          ) : (
            <RightPanel
              project={displayProject}
              script={script ?? null}
              scriptLoading={scriptLoading}
              narrative={narrative ?? null}
              isScriptReview={isScriptReview}
              hasScript={hasScript}
              verdicts={verdicts}
              setVerdicts={setVerdicts}
              allMarked={allMarked}
              canReject={canReject}
              showRejectInput={showRejectInput}
              rejectionDetail={rejectionDetail}
              setRejectionDetail={setRejectionDetail}
              targetStage={targetStage}
              setTargetStage={setTargetStage}
              submitPending={submitReview.isPending || submitted}
              onApprove={handleApprove}
              onReject={handleReject}
              onAbandon={handleAbandon}
              currentVideoAsset={projectDetail?.currentVideoAsset ?? null}
              videoUrl={videoUrlData?.url ?? null}
              onVideoApprove={handleVideoApprove}
              onVideoRetry={handleVideoRetry}
              onVideoAbandon={handleVideoAbandon}
            />
          )}
        </div>
      </div>
    </SidePanel>
  );
}

interface RightPanelProps {
  project: VideoProject;
  script: Awaited<ReturnType<typeof useProjectScript>>["data"] | null;
  scriptLoading: boolean;
  narrative: Awaited<ReturnType<typeof useNarrative>>["data"] | null;
  isScriptReview: boolean;
  hasScript: boolean;
  verdicts: Record<number, VerdictState>;
  setVerdicts: React.Dispatch<React.SetStateAction<Record<number, VerdictState>>>;
  allMarked: boolean;
  canReject: boolean;
  showRejectInput: boolean;
  rejectionDetail: string;
  setRejectionDetail: (v: string) => void;
  targetStage: "narrative" | "code";
  setTargetStage: (v: "narrative" | "code") => void;
  submitPending: boolean;
  onApprove: () => void;
  onReject: () => void;
  onAbandon: () => void;
  currentVideoAsset: import("@/types").VideoAsset | null;
  videoUrl: string | null;
  onVideoApprove: () => void;
  onVideoRetry: () => void;
  onVideoAbandon: () => void;
}

function RightPanel({
  project, script, scriptLoading, narrative, isScriptReview, hasScript,
  verdicts, setVerdicts, allMarked, canReject,
  showRejectInput, rejectionDetail, setRejectionDetail,
  targetStage, setTargetStage,
  submitPending, onApprove, onReject, onAbandon,
  currentVideoAsset, videoUrl, onVideoApprove, onVideoRetry, onVideoAbandon,
}: RightPanelProps) {
  if (project.status === "video_generating") {
    return (
      <div className="flex flex-col items-center justify-center flex-1 gap-3">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
        <p className="text-muted-foreground text-sm">AI 正在生成视频…</p>
      </div>
    );
  }

  if (project.status === "video_failed") {
    const asset = currentVideoAsset;
    return (
      <div className="flex flex-col items-center justify-center flex-1 gap-4 px-8">
        <p className="text-destructive font-medium">视频生成失败</p>
        {asset?.errorMessage && (
          <p className="text-sm text-muted-foreground text-center max-w-sm">{asset.errorMessage}</p>
        )}
        <div className="flex gap-2">
          <Button onClick={onVideoRetry} disabled={submitPending}>重试视频生成</Button>
          <Button variant="destructive" onClick={onVideoAbandon} disabled={submitPending}>废弃</Button>
        </div>
      </div>
    );
  }

  if (project.status === "video_review") {
    return (
      <div className="flex flex-col flex-1 min-h-0 overflow-hidden">
        <div className="flex-1 min-h-0 p-5">
          {videoUrl ? (
            <video
              src={videoUrl}
              controls
              className="w-full h-full max-h-[60vh] rounded-lg bg-black"
            />
          ) : (
            <div className="flex items-center justify-center h-40 text-muted-foreground text-sm">
              视频加载中…
            </div>
          )}
        </div>
        <div className="px-5 py-4 border-t flex gap-2">
          <Button onClick={onVideoApprove} disabled={submitPending} className="flex-1">
            通过发布
          </Button>
          <Button variant="destructive" onClick={onVideoAbandon} disabled={submitPending}>
            废弃
          </Button>
        </div>
      </div>
    );
  }

  if (project.status === "narrative_generating") {
    return (
      <div className="flex flex-col items-center justify-center flex-1 gap-3">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
        <p className="text-muted-foreground text-sm">AI 正在生成叙事脚本…</p>
      </div>
    );
  }

  if (project.status === "narrative_review" && narrative) {
    return (
      <div className="flex-1 min-h-0 overflow-hidden p-5">
        <NarrativeReviewPanel projectId={project.id} narrative={narrative} />
      </div>
    );
  }

  if (project.status === "code_generating") {
    return (
      <div className="flex flex-col items-center justify-center flex-1 gap-3">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
        <p className="text-muted-foreground text-sm">AI 正在生成动画代码…</p>
      </div>
    );
  }

  if (project.status === "narrative_failed" || project.status === "code_failed") {
    return (
      <div className="flex items-center justify-center flex-1">
        <p className="text-destructive text-sm">
          {project.status === "narrative_failed" ? "叙事脚本生成失败" : "代码生成失败"}，请联系管理员
        </p>
      </div>
    );
  }

  if (!isScriptReview && !hasScript) {
    return (
      <div className="flex items-center justify-center flex-1">
        <p className="text-muted-foreground text-sm">暂无审核内容</p>
      </div>
    );
  }

  return (
    <>
      {/* 两列内容区 */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* 镜头列表 */}
        <div className="w-1/2 border-r flex min-h-0 flex-col overflow-hidden">
          <div className="px-4 py-2.5 border-b text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            镜头列表（{script?.scenes.length ?? 0} 个）
          </div>
          <ScrollArea className="flex-1 min-h-0">
            <div className="p-4 space-y-3">
              {scriptLoading && <p className="text-sm text-muted-foreground">加载脚本…</p>}
              {script?.scenes.map((scene) => (
                <div key={scene.sceneIndex} className="border rounded-lg p-3 space-y-2">
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary" className="text-xs">镜头 {scene.sceneIndex}</Badge>
                    <span className="text-xs text-muted-foreground">~{scene.estimatedDurationSeconds}s</span>
                  </div>
                  <p className="text-sm font-medium">{scene.description}</p>
                  <p className="text-xs text-muted-foreground leading-relaxed">{scene.narration}</p>
                  <details className="text-xs">
                    <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
                      查看代码
                    </summary>
                    <pre className="mt-2 p-2 bg-muted rounded overflow-x-auto text-xs leading-relaxed">
                      {scene.code}
                    </pre>
                  </details>
                </div>
              ))}
            </div>
          </ScrollArea>
        </div>

        {/* 事实核查 */}
        <div className="w-1/2 flex min-h-0 flex-col overflow-hidden">
          <div className="px-4 py-2.5 border-b text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            事实核查（{script?.factChecks.length ?? 0} 条）
          </div>
          <ScrollArea className="flex-1 min-h-0">
            <div className="p-4 space-y-3">
              {script?.factChecks.map((item, idx) => (
                <FactCheckCard
                  key={idx}
                  item={item}
                  index={idx}
                  verdict={verdicts[idx]?.verdict ?? null}
                  note={verdicts[idx]?.note ?? ""}
                  onVerdictChange={(i, v, n) =>
                    setVerdicts((prev) => ({ ...prev, [i]: { verdict: v, note: n } }))
                  }
                />
              ))}
            </div>
          </ScrollArea>
        </div>
      </div>

      {/* 右栏底部操作区（仅 script_review） */}
      {isScriptReview && (
        <div className="px-5 py-4 border-t space-y-2">
          {showRejectInput && (
            <div className="space-y-2">
              <Textarea
                value={rejectionDetail}
                onChange={(e) => setRejectionDetail(e.target.value)}
                placeholder="请说明驳回原因（AI 重新生成时会参考此信息）"
                className="text-sm min-h-[72px]"
              />
              <div className="flex gap-4 text-sm">
                <label className="flex items-center gap-1 cursor-pointer">
                  <input
                    type="radio"
                    name="targetStage"
                    value="narrative"
                    checked={targetStage === "narrative"}
                    onChange={() => setTargetStage("narrative")}
                  />
                  重写叙事脚本
                </label>
                <label className="flex items-center gap-1 cursor-pointer">
                  <input
                    type="radio"
                    name="targetStage"
                    value="code"
                    checked={targetStage === "code"}
                    onChange={() => setTargetStage("code")}
                  />
                  仅重新生成代码
                </label>
              </div>
            </div>
          )}
          <div className="flex gap-2">
            <Button onClick={onApprove} disabled={!allMarked || submitPending} className="flex-1">
              通过
            </Button>
            {canReject && (
              <Button variant="outline" onClick={onReject} disabled={submitPending} className="flex-1">
                {showRejectInput ? "确认驳回" : "驳回重生成"}
              </Button>
            )}
            <Button variant="destructive" onClick={onAbandon} disabled={submitPending}>
              废弃
            </Button>
          </div>
          {!allMarked && script && script.factChecks.length > 0 && (
            <p className="text-xs text-muted-foreground text-center">请为所有核查条目标注审核结果后再提交</p>
          )}
        </div>
      )}
    </>
  );
}

function MetaSection({ project }: { project: VideoProject }) {
  return (
    <section className="shrink-0 space-y-3 pb-6">
      <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">项目配置</p>
      <div className="grid grid-cols-2 gap-y-2 gap-x-4 text-sm">
        <span className="text-muted-foreground">渲染引擎</span>
        <span className="font-medium">{project.renderEngine}</span>
        <span className="text-muted-foreground">TTS 声音</span>
        <span className="font-medium">{project.ttsVoice}</span>
        <span className="text-muted-foreground">画幅比例</span>
        <span className="font-medium">{project.aspectRatio === "landscape" ? "横屏 16:9" : "竖屏 9:16"}</span>
        <span className="text-muted-foreground">重试次数</span>
        <span className="font-medium">{project.retryCount}</span>
        <span className="text-muted-foreground">创建时间</span>
        <span className="font-medium">{timeAgo(project.createdAt)}</span>
      </div>
    </section>
  );
}

// Statuses whose entry event is clickable and has associated content
const CONTENT_STATUS_MAP: Record<string, "narrative" | "script"> = {
  narrative_review: "narrative",
  script_review: "script",
};

interface EventsSectionProps {
  eventsData: { items: ProjectEvent[] } | undefined;
  narrativeVersions: NarrativeVersion[];
  scriptVersions: ScriptVersion[];
  selectedNode: SelectedNode | null;
  onSelectNode: (node: SelectedNode | null) => void;
}

function EventsSection({
  eventsData, narrativeVersions, scriptVersions, selectedNode, onSelectNode,
}: EventsSectionProps) {
  // Correlate each status-change event to a version by counting occurrences per type
  // Build a map: status → list of verdict events (in order) for that gate
  const verdictsByGate = useMemo(() => {
    const map: Record<string, Array<{ verdict: string; rejection_detail?: string; target_stage?: string }>> = {};
    for (const event of eventsData?.items ?? []) {
      if (event.eventType === "review_verdict" && event.payload) {
        const gate = event.payload["gate"] as string;
        if (!map[gate]) map[gate] = [];
        map[gate].push(event.payload as { verdict: string; rejection_detail?: string; target_stage?: string });
      }
    }
    return map;
  }, [eventsData]);

  const annotated = useMemo(() => {
    let narrativeCount = 0;
    let scriptCount = 0;
    const verdictConsumed: Record<string, number> = {};
    return (eventsData?.items ?? [])
      .filter((e) => e.eventType === "status_change") // show only status changes in the timeline
      .map((event) => {
        const contentType = event.toStatus ? CONTENT_STATUS_MAP[event.toStatus] : undefined;
        let versionId: string | null = null;
        let versionNumber: number | null = null;
        let verdict: { verdict: string; rejection_detail?: string; target_stage?: string } | null = null;

        if (contentType === "narrative") {
          narrativeCount++;
          const v = narrativeVersions[narrativeCount - 1];
          if (v) { versionId = v.id; versionNumber = v.versionNumber; }
          // Attach the corresponding verdict (nth narrative_review → nth narrative verdict)
          const used = verdictConsumed["narrative"] ?? 0;
          const vd = (verdictsByGate["narrative"] ?? [])[used];
          if (vd) { verdict = vd; verdictConsumed["narrative"] = used + 1; }
        } else if (contentType === "script") {
          scriptCount++;
          const v = scriptVersions[scriptCount - 1];
          if (v) { versionId = v.id; versionNumber = v.versionNumber; }
          const used = verdictConsumed["script"] ?? 0;
          const vd = (verdictsByGate["script"] ?? [])[used];
          if (vd) { verdict = vd; verdictConsumed["script"] = used + 1; }
        }
        return { event, contentType, versionId, versionNumber, verdict };
      });
  }, [eventsData, narrativeVersions, scriptVersions, verdictsByGate]);

  return (
    <section className="flex min-h-0 flex-1 flex-col gap-3">
      <p className="shrink-0 text-xs font-semibold text-muted-foreground uppercase tracking-wide">
        状态时间线
      </p>
      <ScrollArea className="min-h-0 flex-1">
        {!annotated.length ? (
          <p className="text-sm text-muted-foreground">暂无事件记录</p>
        ) : (
          <div className="space-y-0 pr-3">
            {annotated.map(({ event, contentType, versionId, versionNumber, verdict }, i) => {
              const isClickable = !!(contentType && versionId);
              const isSelected =
                selectedNode?.versionId === versionId && selectedNode?.type === contentType;
              const isLast = i === annotated.length - 1;

              const verdictLabel = verdict?.verdict === "approved"
                ? { text: "通过", color: "text-green-600" }
                : verdict?.verdict === "rejected"
                ? { text: "驳回", color: "text-destructive" }
                : verdict?.verdict === "abandoned"
                ? { text: "废弃", color: "text-muted-foreground" }
                : null;

              const handleClick = () => {
                if (!isClickable) return;
                onSelectNode(isSelected ? null : { type: contentType!, versionId: versionId!, versionNumber: versionNumber! });
              };

              return (
                <div key={event.id} className="flex gap-3">
                  <div className="flex flex-col items-center">
                    <div
                      className={`w-2.5 h-2.5 rounded-full mt-1.5 shrink-0 border-2 transition-colors ${
                        isSelected
                          ? "bg-primary border-primary"
                          : isClickable
                          ? "bg-background border-primary cursor-pointer hover:bg-primary/20"
                          : isLast
                          ? "bg-primary border-primary"
                          : "bg-muted-foreground/40 border-muted-foreground/40"
                      }`}
                      onClick={handleClick}
                    />
                    {i < annotated.length - 1 && (
                      <div className="w-px flex-1 bg-border mt-1" />
                    )}
                  </div>
                  <div
                    className={`pb-4 min-w-0 flex-1 ${isClickable ? "cursor-pointer" : ""}`}
                    onClick={handleClick}
                  >
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <p className={`text-sm font-medium leading-snug ${isSelected ? "text-primary" : ""}`}>
                        {event.toStatus
                          ? (PROJECT_STATUS_LABELS[event.toStatus] ?? event.toStatus)
                          : (EVENT_TYPE_LABELS[event.eventType] ?? event.eventType)}
                      </p>
                      {isClickable && (
                        <span className="text-xs text-muted-foreground">v{versionNumber}</span>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {timeAgo(event.createdAt)}
                    </p>
                    {/* Verdict badge + rejection detail */}
                    {verdictLabel && (
                      <div className="mt-1 space-y-0.5">
                        <span className={`text-xs font-medium ${verdictLabel.color}`}>
                          {verdictLabel.text}
                        </span>
                        {verdict?.rejection_detail && (
                          <p className="text-xs text-muted-foreground leading-relaxed break-words">
                            {verdict.rejection_detail}
                          </p>
                        )}
                        {verdict?.target_stage && verdict.verdict === "rejected" && (
                          <p className="text-xs text-muted-foreground">
                            回退至：{verdict.target_stage === "code" ? "重新生成代码" : "重写叙事脚本"}
                          </p>
                        )}
                      </div>
                    )}
                    {isClickable && (
                      <p className="text-xs text-primary/70 mt-0.5">
                        {isSelected ? "收起 ↑" : "查看内容 →"}
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </ScrollArea>
    </section>
  );
}

// ── Historical read-only view ──────────────────────────────────────────────

interface HistoricalViewProps {
  node: SelectedNode;
  narrativeVersion: NarrativeVersion | null;
  scriptVersion: ScriptVersion | null;
  onClose: () => void;
}

function HistoricalView({ node, narrativeVersion, scriptVersion, onClose }: HistoricalViewProps) {
  const version = node.type === "narrative" ? narrativeVersion : scriptVersion;

  return (
    <div className="flex flex-col flex-1 min-h-0 overflow-hidden">
      {/* Banner */}
      <div className="flex items-center justify-between px-5 py-2.5 border-b bg-muted/40 shrink-0">
        <span className="text-xs text-muted-foreground">
          正在查看历史版本 — {node.type === "narrative" ? "叙事脚本" : "完整脚本"} v{node.versionNumber}（只读）
        </span>
        <Button variant="ghost" size="sm" className="h-6 text-xs" onClick={onClose}>
          返回当前
        </Button>
      </div>

      {!version ? (
        <div className="flex items-center justify-center flex-1">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary" />
        </div>
      ) : node.type === "narrative" ? (
        <HistoricalNarrativeView version={narrativeVersion!} />
      ) : (
        <HistoricalScriptView version={scriptVersion!} />
      )}
    </div>
  );
}

function HistoricalNarrativeView({ version }: { version: NarrativeVersion }) {
  return (
    <div className="flex flex-1 min-h-0 overflow-hidden">
      <ScrollArea className="flex-[3] min-w-0 p-5">
        <div className="space-y-4">
          {version.scenes.map((scene) => (
            <div key={scene.sceneIndex} className="border rounded-lg p-4 space-y-2">
              <div className="flex items-center gap-2">
                <Badge variant="outline">镜头 {scene.sceneIndex}</Badge>
                {scene.estimatedDurationSeconds && (
                  <span className="text-xs text-muted-foreground">{scene.estimatedDurationSeconds}s</span>
                )}
              </div>
              <p className="text-xs font-medium text-muted-foreground">旁白</p>
              <p className="text-sm leading-relaxed">{scene.narration}</p>
              <p className="text-xs font-medium text-muted-foreground">画面描述</p>
              <p className="text-sm leading-relaxed text-muted-foreground">{scene.description}</p>
            </div>
          ))}
        </div>
      </ScrollArea>
      <div className="flex-[2] min-w-0 border-l flex flex-col">
        <div className="px-4 py-2.5 border-b text-xs font-semibold text-muted-foreground uppercase tracking-wide shrink-0">
          事实核查（{version.factChecks.length} 条）
        </div>
        <ScrollArea className="flex-1 p-3">
          <div className="space-y-3">
            {version.factChecks.map((fc, i) => (
              <HistoricalFactCheckCard key={i} fc={fc} />
            ))}
          </div>
        </ScrollArea>
      </div>
    </div>
  );
}

function HistoricalScriptView({ version }: { version: ScriptVersion }) {
  return (
    <div className="flex flex-1 min-h-0 overflow-hidden">
      <ScrollArea className="flex-[3] min-w-0 p-5">
        <div className="space-y-3">
          {version.scenes?.map((scene) => (
            <div key={scene.sceneIndex} className="border rounded-lg p-3 space-y-2">
              <div className="flex items-center gap-2">
                <Badge variant="secondary" className="text-xs">镜头 {scene.sceneIndex}</Badge>
                <span className="text-xs text-muted-foreground">~{scene.estimatedDurationSeconds}s</span>
              </div>
              <p className="text-sm font-medium">{scene.description}</p>
              <p className="text-xs text-muted-foreground leading-relaxed">{scene.narration}</p>
              <details className="text-xs">
                <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
                  查看代码
                </summary>
                <pre className="mt-2 p-2 bg-muted rounded overflow-x-auto text-xs leading-relaxed">
                  {scene.code}
                </pre>
              </details>
            </div>
          ))}
        </div>
      </ScrollArea>
      <div className="flex-[2] min-w-0 border-l flex flex-col">
        <div className="px-4 py-2.5 border-b text-xs font-semibold text-muted-foreground uppercase tracking-wide shrink-0">
          事实核查（{version.factChecks?.length ?? 0} 条）
        </div>
        <ScrollArea className="flex-1 p-3">
          <div className="space-y-3">
            {version.factChecks?.map((fc, i) => (
              <HistoricalFactCheckCard key={i} fc={fc} />
            ))}
          </div>
        </ScrollArea>
      </div>
    </div>
  );
}

// ── Shared fact-check card for historical views ────────────────────────────

const CONFIDENCE_LABEL: Record<string, string> = { high: "高", medium: "中", low: "低" };
const CONFIDENCE_VARIANT: Record<string, "default" | "secondary" | "destructive"> = {
  high: "default", medium: "secondary", low: "destructive",
};
const VERDICT_LABEL: Record<string, string> = {
  approved: "通过", rejected: "驳回", needs_revision: "待修改",
};
const VERDICT_VARIANT: Record<string, "default" | "secondary" | "destructive"> = {
  approved: "default", needs_revision: "secondary", rejected: "destructive",
};

function HistoricalFactCheckCard({ fc }: { fc: import("@/types").FactCheckItem }) {
  return (
    <div className="border rounded-lg p-3 space-y-2 text-xs">
      {/* Claim */}
      <p className="font-medium leading-relaxed">{fc.claimText}</p>

      {/* Badges row */}
      <div className="flex gap-1.5 flex-wrap">
        <Badge variant={CONFIDENCE_VARIANT[fc.confidence] ?? "secondary"} className="text-xs">
          可信度：{CONFIDENCE_LABEL[fc.confidence] ?? fc.confidence}
        </Badge>
        {fc.isHypothesis && (
          <Badge variant="outline" className="text-xs">假设</Badge>
        )}
        {fc.reviewerVerdict && (
          <Badge variant={VERDICT_VARIANT[fc.reviewerVerdict] ?? "secondary"} className="text-xs">
            {VERDICT_LABEL[fc.reviewerVerdict] ?? fc.reviewerVerdict}
          </Badge>
        )}
      </div>

      {/* Source */}
      {fc.sourceDescription && (
        <div className="space-y-0.5">
          <p className="text-muted-foreground font-medium">来源</p>
          <p className="text-muted-foreground leading-relaxed">{fc.sourceDescription}</p>
          {fc.sourceUrl && (
            <a
              href={fc.sourceUrl}
              target="_blank"
              rel="noreferrer"
              className="text-primary underline break-all"
            >
              {fc.sourceUrl}
            </a>
          )}
        </div>
      )}

      {/* Assumptions */}
      {fc.assumptions && (
        <div className="space-y-0.5">
          <p className="text-muted-foreground font-medium">前提假设</p>
          <p className="text-muted-foreground leading-relaxed">{fc.assumptions}</p>
        </div>
      )}

      {/* Controversy */}
      {fc.controversy && (
        <div className="space-y-0.5">
          <p className="text-amber-600 font-medium">争议点</p>
          <p className="text-amber-600/80 leading-relaxed">{fc.controversy}</p>
        </div>
      )}

      {/* Reviewer note */}
      {fc.reviewerNote && (
        <div className="space-y-0.5">
          <p className="text-muted-foreground font-medium">审核备注</p>
          <p className="text-muted-foreground leading-relaxed">{fc.reviewerNote}</p>
        </div>
      )}
    </div>
  );
}

