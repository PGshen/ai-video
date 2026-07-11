import { useState, useMemo, useRef, useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  ChevronDown, ChevronRight, Code2, FileText, MessageSquareWarning,
  PanelLeftClose, PanelLeftOpen, Play,
} from "lucide-react";
import { toast } from "sonner";
import { SidePanel, SidePanelHeader } from "@/components/ui/side-panel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Textarea } from "@/components/ui/textarea";
import { NarrativeReviewPanel } from "@/components/projects/NarrativeReviewPanel";
import { SceneBeats } from "@/components/projects/SceneBeats";
import { ProjectStylePrompts } from "@/components/projects/ProjectStylePrompts";
import {
  useProject, useProjectEvents, useProjectCode, useSubmitReview,
  useNarrativeVersions, useNarrativeVersion,
  useCodeVersions, useCodeVersion, useVideoUrl, useRepairCode,
  useResetProject,
} from "@/hooks/useProjects";
import { useNarrative } from "@/hooks/useNarrative";
import { PROJECT_STATUS_LABELS, PROJECT_STATUS_COLORS, formatDateTime } from "@/lib/format";
import type {
  VideoProject, ProjectEvent, NarrativeVersion, CodeVersion, CodeRepair,
  Scene, SceneReviewAnnotation, RejectionContext,
} from "@/types";

interface Props {
  project: VideoProject | null;
  onClose: () => void;
}

const EVENT_TYPE_LABELS: Record<string, string> = {
  status_change: "状态变更",
  signal_sent: "信号发送",
  render_failed: "视频生成失败",
};

interface SelectedNode {
  type: "narrative" | "code" | "video";
  versionId: string;
  versionNumber: number;
  eventId: number;
  videoAssetId?: string | null;
}

interface SceneTiming {
  sceneIndex: number;
  start: number;
  end: number;
  duration: number;
}

const clampDuration = (value: number | null | undefined) =>
  typeof value === "number" && Number.isFinite(value) && value > 0 ? value : 0;

const formatSeconds = (seconds: number) => {
  const safe = Number.isFinite(seconds) && seconds > 0 ? seconds : 0;
  const mins = Math.floor(safe / 60);
  const secs = Math.floor(safe % 60);
  return `${mins}:${String(secs).padStart(2, "0")}`;
};

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

const annotationsFromContext = (context: RejectionContext | null | undefined) =>
  normalizeAnnotations(context?.sceneAnnotations ?? context?.scene_annotations);

const rejectionDetailFromContext = (context: RejectionContext | null | undefined) =>
  context?.rejectionDetail ?? context?.rejection_detail ?? null;

const buildAnnotationSummary = (annotations: SceneReviewAnnotation[]) => {
  if (annotations.length === 0) return "";
  return annotations
    .map((item) => {
      const parts = [
        item.narrativeIssue ? `叙事：${item.narrativeIssue}` : "",
        item.codeIssue ? `代码：${item.codeIssue}` : "",
      ].filter(Boolean);
      return `镜头 ${item.sceneIndex}: ${parts.join("；")}`;
    })
    .join("\n");
};

export function ProjectSheet({ project, onClose }: Props) {
  // Keep the last non-null project so SidePanel's exit animation has content to render
  const lastProjectRef = useRef<VideoProject | null>(null);
  if (project) lastProjectRef.current = project;
  const displayProject = project ?? lastProjectRef.current;

  // Fetch full project detail (includes currentVideoAsset); list endpoint omits it
  const qc = useQueryClient();
  const { data: projectDetail, refetch: refetchProjectDetail } = useProject(displayProject?.id ?? "");

  // 侧栏打开或项目状态变化时，强制刷新所有关联数据
  useEffect(() => {
    if (!displayProject?.id) return;
    refetchProjectDetail();
    qc.invalidateQueries({ queryKey: ["projects", displayProject.id, "events"] });
    qc.invalidateQueries({ queryKey: ["projects", displayProject.id, "code"] });
    qc.invalidateQueries({ queryKey: ["narrative", displayProject.id] });
    qc.invalidateQueries({ queryKey: ["projects", displayProject.id, "narrative-versions"] });
    qc.invalidateQueries({ queryKey: ["projects", displayProject.id, "code-versions"] });
  }, [displayProject?.id, displayProject?.status, qc, refetchProjectDetail]);

  const { data: eventsData } = useProjectEvents(displayProject?.id ?? "");
  const { data: codeVersion, isLoading: codeLoading } = useProjectCode(displayProject?.id ?? "");
  const { data: narrative } = useNarrative(displayProject?.id ?? "");
  const { data: narrativeVersions = [] } = useNarrativeVersions(displayProject?.id ?? "");
  const { data: codeVersions = [] } = useCodeVersions(displayProject?.id ?? "");
  const { data: videoUrlData } = useVideoUrl(
    displayProject?.id ?? "",
    projectDetail?.currentVideoAsset?.id ?? null,
  );
  const submitReview = useSubmitReview();
  const repairCode = useRepairCode();
  const resetProject = useResetProject();

  const [selectedNode, setSelectedNode] = useState<SelectedNode | null>(null);
  const [rejectionDetail, setRejectionDetail] = useState("");
  const [showRejectInput, setShowRejectInput] = useState(false);
  const [targetStage, setTargetStage] = useState<"narrative" | "code">("narrative");
  const [showVideoRejectInput, setShowVideoRejectInput] = useState(false);
  const [videoRejectionDetail, setVideoRejectionDetail] = useState("");
  const [videoTargetStage, setVideoTargetStage] = useState<"narrative" | "code">("code");
  const [submitted, setSubmitted] = useState(false);
  const [metaCollapsed, setMetaCollapsed] = useState(false);
  const [timelineCollapsed, setTimelineCollapsed] = useState(false);
  const [leftRailCollapsed, setLeftRailCollapsed] = useState(false);
  const [sceneAnnotations, setSceneAnnotations] = useState<Map<number, SceneReviewAnnotation>>(new Map());

  useEffect(() => {
    setSubmitted(false);
  }, [displayProject?.id, displayProject?.status]);

  useEffect(() => {
    setShowVideoRejectInput(false);
    setVideoRejectionDetail("");
    setVideoTargetStage("code");
    setSceneAnnotations(new Map());
  }, [displayProject?.id]);

  // Fetch selected historical version on demand
  const { data: selectedNarrativeVersion } = useNarrativeVersion(
    displayProject?.id ?? "",
    selectedNode?.type === "narrative" ? selectedNode.versionId : null,
  );
  const { data: selectedCodeVersion } = useCodeVersion(
    displayProject?.id ?? "",
    selectedNode?.type === "code" ? selectedNode.versionId : null,
  );
  const visiblePromptSnapshot = selectedNode?.type === "narrative"
    ? selectedNarrativeVersion?.promptSnapshot ?? null
    : selectedNode?.type === "code"
      ? selectedCodeVersion?.promptSnapshot ?? null
      : codeVersion?.promptSnapshot ?? narrative?.promptSnapshot ?? null;
  // For historical video node view: use the asset ID stored in the event payload if available,
  // otherwise fall back to current asset (covers published projects with a single asset).
  const selectedVideoAssetId =
    selectedNode?.type === "video"
      ? (selectedNode.videoAssetId ?? projectDetail?.currentVideoAsset?.id ?? null)
      : null;
  const { data: selectedVideoUrlData } = useVideoUrl(
    displayProject?.id ?? "",
    selectedVideoAssetId,
  );

  const isCodeReview = project?.status === "code_review";
  const hasCode = !!codeVersion;
  // 事件记录是失败原因的权威来源；VideoAsset 用于兼容旧数据。
  const renderFailureError = useMemo(() => {
    if (!isCodeReview) return null;
    const retreatEvent = [...(eventsData?.items ?? [])].reverse().find(
      (event) =>
        event.eventType === "status_change" &&
        event.toStatus === "code_review" &&
        (event.payload?.["trigger"] === "video_failed" || event.payload?.["render_error"]),
    );
    const eventError =
      retreatEvent?.payload?.["error_message"] ?? retreatEvent?.payload?.["render_error"];
    if (typeof eventError === "string") return eventError;
    return projectDetail?.currentVideoAsset?.status === "failed"
      ? projectDetail.currentVideoAsset.errorMessage
      : null;
  }, [eventsData, isCodeReview, projectDetail?.currentVideoAsset]);
  const isRenderFailed =
    !!renderFailureError ||
    (isCodeReview && projectDetail?.currentVideoAsset?.status === "failed");

  // 代码编辑状态（渲染失败时允许修改）
  const [editedCode, setEditedCode] = useState<Map<number, string>>(new Map());
  const [codeRepairs, setCodeRepairs] = useState<Map<number, CodeRepair>>(new Map());
  const [appliedRepairs, setAppliedRepairs] = useState<Set<number>>(new Set());

  useEffect(() => {
    setEditedCode(new Map());
    setCodeRepairs(new Map());
    setAppliedRepairs(new Set());
  }, [displayProject?.id, codeVersion?.id]);

  const buildEditedCodeScenes = () =>
    Array.from(editedCode.entries()).map(([sceneIndex, code]) => ({ sceneIndex, code }));

  const handleAiRepair = () => {
    if (!project || !codeVersion || !renderFailureError) return;
    const scenes = codeVersion.scenes.map((scene) => ({
      ...scene,
      code: editedCode.get(scene.sceneIndex) ?? scene.code ?? "",
    }));
    repairCode.mutate(
      {
        projectId: project.id,
        errorMessage: renderFailureError,
        scenes,
      },
      {
        onSuccess: ({ repairs }) => {
          setCodeRepairs(new Map(repairs.map((repair) => [repair.sceneIndex, repair])));
          setAppliedRepairs(new Set());
          if (repairs.length === 0) {
            toast.info("AI 未发现需要修改的镜头");
          } else {
            toast.success(`AI 已给出 ${repairs.length} 个镜头的修复建议`);
          }
        },
        onError: () => toast.error("AI 修复失败，请重试"),
      },
    );
  };

  const handleApplyRepair = (repair: CodeRepair) => {
    setEditedCode((prev) => {
      const next = new Map(prev);
      next.set(repair.sceneIndex, repair.code);
      return next;
    });
    setAppliedRepairs((prev) => new Set(prev).add(repair.sceneIndex));
    toast.success(`已将 AI 修复应用到镜头 ${repair.sceneIndex}`);
  };

  const handleApprove = () => {
    if (!project) return;
    const editedCodeScenes = buildEditedCodeScenes();
    submitReview.mutate(
      {
        projectId: project.id,
        gate: "code",
        verdict: "approved",
        ...(editedCodeScenes.length > 0 ? { editedCodeScenes } : {}),
      },
      {
        onSuccess: () => {
          setSubmitted(true);
          toast.success(isRenderFailed ? "已提交，重新生成视频…" : "审核已通过，AI 正在生成视频…");
        },
        onError: () => toast.error("提交失败，请重试"),
      },
    );
  };

  const handleReject = () => {
    if (!project) return;
    if (!showRejectInput) { setShowRejectInput(true); return; }
    const inheritedAnnotations = annotationsFromContext(codeVersion?.rejectionContext);
    const inheritedDetail = rejectionDetailFromContext(codeVersion?.rejectionContext);
    const detail = rejectionDetail.trim() || inheritedDetail || buildAnnotationSummary(inheritedAnnotations);
    submitReview.mutate(
      {
        projectId: project.id,
        gate: "code",
        verdict: "rejected",
        rejectionDetail: detail,
        targetStage,
        ...(inheritedAnnotations.length > 0 ? { sceneAnnotations: inheritedAnnotations } : {}),
      },
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
      { projectId: project.id, gate: "code", verdict: "abandoned" },
      {
        onSuccess: () => { setSubmitted(true); toast.info("项目已废弃"); },
        onError: () => toast.error("操作失败，请重试"),
      },
    );
  };

  const handleCodeRetry = () => {
    if (!project) return;
    resetProject.mutate(project.id, {
      onSuccess: () => toast.success("已重新排队生成代码"),
      onError: (error) => toast.error(error.message || "重试失败，请稍后再试"),
    });
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

  const updateSceneAnnotation = (
    sceneIndex: number,
    field: "narrativeIssue" | "codeIssue",
    value: string,
  ) => {
    setSceneAnnotations((prev) => {
      const next = new Map(prev);
      const current = next.get(sceneIndex) ?? { sceneIndex };
      const updated = { ...current, [field]: value };
      if (!updated.narrativeIssue?.trim() && !updated.codeIssue?.trim()) {
        next.delete(sceneIndex);
      } else {
        next.set(sceneIndex, updated);
      }
      return next;
    });
  };

  const buildSceneAnnotations = () =>
    Array.from(sceneAnnotations.values())
      .map((item) => ({
        sceneIndex: item.sceneIndex,
        narrativeIssue: item.narrativeIssue?.trim() || undefined,
        codeIssue: item.codeIssue?.trim() || undefined,
      }))
      .filter((item) => item.narrativeIssue || item.codeIssue);

  const handleVideoReject = () => {
    if (!project) return;
    if (!showVideoRejectInput) {
      setShowVideoRejectInput(true);
      return;
    }
    const annotations = buildSceneAnnotations();
    const detail = videoRejectionDetail.trim() || buildAnnotationSummary(annotations);
    if (!detail && annotations.length === 0) {
      toast.error("请填写驳回原因或标注至少一个镜头问题");
      return;
    }
    submitReview.mutate(
      {
        projectId: project.id,
        gate: "video",
        verdict: "rejected",
        rejectionDetail: detail,
        targetStage: videoTargetStage,
        ...(annotations.length > 0 ? { sceneAnnotations: annotations } : {}),
      },
      {
        onSuccess: () => {
          setSubmitted(true);
          toast.success(videoTargetStage === "narrative" ? "已驳回到叙事审核" : "已驳回到代码审核");
        },
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
          <div className="flex items-center gap-2">
            <h2 className="text-base font-semibold leading-snug">{displayProject.topicTitle}</h2>
            <span className={`px-2 py-0.5 rounded text-xs font-medium shrink-0 ${statusColor}`}>
              {statusLabel}
            </span>
            {displayProject.retryCount > 0 && (
              <span className="text-xs text-muted-foreground shrink-0">已驳回 {displayProject.retryCount} 次</span>
            )}
          </div>
        </div>
      </SidePanelHeader>

      <div className="flex flex-1 min-h-0 overflow-hidden">
        <div className={`${leftRailCollapsed ? "w-12" : "w-72"} shrink-0 border-r flex min-h-0 flex-col overflow-hidden transition-[width]`}>
          <div className="flex items-center justify-between border-b px-3 py-2">
            {!leftRailCollapsed && (
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                项目信息
              </span>
            )}
            <Button
              type="button"
              variant="ghost"
              size="icon-xs"
              onClick={() => setLeftRailCollapsed((value) => !value)}
              title={leftRailCollapsed ? "展开侧栏" : "收起侧栏"}
              className={leftRailCollapsed ? "mx-auto" : ""}
            >
              {leftRailCollapsed ? <PanelLeftOpen className="size-3.5" /> : <PanelLeftClose className="size-3.5" />}
            </Button>
          </div>
          {!leftRailCollapsed && (
            <div className="flex min-h-0 flex-1 flex-col overflow-hidden p-5">
              <MetaSection
                project={displayProject}
                promptSnapshot={visiblePromptSnapshot}
                collapsed={metaCollapsed}
                onToggle={() => setMetaCollapsed((value) => !value)}
              />
              <EventsSection
                eventsData={eventsData}
                narrativeVersions={narrativeVersions}
                codeVersions={codeVersions}
                selectedNode={selectedNode}
                onSelectNode={setSelectedNode}
                collapsed={timelineCollapsed}
                onToggle={() => setTimelineCollapsed((value) => !value)}
              />
            </div>
          )}
        </div>

        {/* 右栏：历史视图 or 当前审核视图 */}
        <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
          {selectedNode ? (
            <HistoricalView
              node={selectedNode}
              narrativeVersion={selectedNarrativeVersion ?? null}
              codeVersion={selectedCodeVersion ?? null}
              videoUrl={selectedVideoUrlData?.url ?? null}
              onClose={() => setSelectedNode(null)}
            />
          ) : (
            <RightPanel
              project={displayProject}
              codeVersion={codeVersion ?? null}
              codeLoading={codeLoading}
              narrative={narrative ?? null}
              isCodeReview={isCodeReview}
              isRenderFailed={isRenderFailed}
              renderFailureError={renderFailureError}
              hasCode={hasCode}

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
              onCodeRetry={handleCodeRetry}
              codeRetryPending={resetProject.isPending}
              currentVideoAsset={projectDetail?.currentVideoAsset ?? null}
              videoUrl={videoUrlData?.url ?? null}
              onVideoApprove={handleVideoApprove}
              showVideoRejectInput={showVideoRejectInput}
              videoRejectionDetail={videoRejectionDetail}
              setVideoRejectionDetail={setVideoRejectionDetail}
              videoTargetStage={videoTargetStage}
              setVideoTargetStage={setVideoTargetStage}
              sceneAnnotations={sceneAnnotations}
              onSceneAnnotationChange={updateSceneAnnotation}
              onVideoReject={handleVideoReject}
              onVideoRetry={handleVideoRetry}
              onVideoAbandon={handleVideoAbandon}
              editedCode={editedCode}
              setEditedCode={setEditedCode}
              codeRepairs={codeRepairs}
              appliedRepairs={appliedRepairs}
              repairPending={repairCode.isPending}
              onAiRepair={handleAiRepair}
              onApplyRepair={handleApplyRepair}
            />
          )}
        </div>
      </div>
    </SidePanel>
  );
}

interface RightPanelProps {
  project: VideoProject;
  codeVersion: Awaited<ReturnType<typeof useProjectCode>>["data"] | null;
  codeLoading: boolean;
  narrative: Awaited<ReturnType<typeof useNarrative>>["data"] | null;
  isCodeReview: boolean;
  isRenderFailed: boolean;
  renderFailureError: string | null;
  hasCode: boolean;
  editedCode: Map<number, string>;
  setEditedCode: React.Dispatch<React.SetStateAction<Map<number, string>>>;
  codeRepairs: Map<number, CodeRepair>;
  appliedRepairs: Set<number>;
  repairPending: boolean;
  onAiRepair: () => void;
  onApplyRepair: (repair: CodeRepair) => void;
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
  onCodeRetry: () => void;
  codeRetryPending: boolean;
  currentVideoAsset: import("@/types").VideoAsset | null;
  videoUrl: string | null;
  onVideoApprove: () => void;
  showVideoRejectInput: boolean;
  videoRejectionDetail: string;
  setVideoRejectionDetail: (value: string) => void;
  videoTargetStage: "narrative" | "code";
  setVideoTargetStage: (value: "narrative" | "code") => void;
  sceneAnnotations: Map<number, SceneReviewAnnotation>;
  onSceneAnnotationChange: (
    sceneIndex: number,
    field: "narrativeIssue" | "codeIssue",
    value: string,
  ) => void;
  onVideoReject: () => void;
  onVideoRetry: () => void;
  onVideoAbandon: () => void;
}

function RightPanel({
  project, codeVersion, codeLoading, narrative, isCodeReview, isRenderFailed, renderFailureError, hasCode,
  canReject,
  showRejectInput, rejectionDetail, setRejectionDetail,
  targetStage, setTargetStage,
  submitPending, onApprove, onReject, onAbandon, onCodeRetry, codeRetryPending,
  currentVideoAsset, videoUrl, onVideoApprove,
  showVideoRejectInput, videoRejectionDetail, setVideoRejectionDetail,
  videoTargetStage, setVideoTargetStage, sceneAnnotations, onSceneAnnotationChange, onVideoReject,
  onVideoRetry, onVideoAbandon,
  editedCode, setEditedCode,
  codeRepairs, appliedRepairs, repairPending, onAiRepair, onApplyRepair,
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
          <pre className="text-xs text-muted-foreground whitespace-pre-wrap break-all leading-relaxed max-h-64 overflow-y-auto w-full border rounded p-2 bg-muted/30">{asset.errorMessage}</pre>
        )}
        <div className="flex gap-2">
          <Button onClick={onVideoRetry} disabled={submitPending}>重试视频生成</Button>
          <Button variant="destructive" onClick={onVideoAbandon} disabled={submitPending}>废弃</Button>
        </div>
      </div>
    );
  }

  if (project.status === "video_review" || project.status === "published") {
    return (
      <div className="flex flex-col flex-1 min-h-0 overflow-hidden">
        <VideoReviewWorkspace
          videoUrl={videoUrl}
          scenes={codeVersion?.scenes ?? []}
          readOnly={project.status === "published"}
          annotations={sceneAnnotations}
          onAnnotationChange={onSceneAnnotationChange}
        />
        {project.status === "video_review" && (
          <div className="px-5 py-4 border-t space-y-3">
            {showVideoRejectInput && (
              <div className="space-y-2">
                <Textarea
                  value={videoRejectionDetail}
                  onChange={(event) => setVideoRejectionDetail(event.target.value)}
                  placeholder="请说明整体驳回原因；也可以直接在右侧按镜头标注问题"
                  className="text-sm min-h-[72px]"
                />
                <div className="flex gap-5 text-sm">
                  <label className="flex items-center gap-1.5 cursor-pointer">
                    <input
                      type="radio"
                      name="videoTargetStage"
                      checked={videoTargetStage === "narrative"}
                      onChange={() => setVideoTargetStage("narrative")}
                    />
                    驳回到叙事审核
                  </label>
                  <label className="flex items-center gap-1.5 cursor-pointer">
                    <input
                      type="radio"
                      name="videoTargetStage"
                      checked={videoTargetStage === "code"}
                      onChange={() => setVideoTargetStage("code")}
                    />
                    驳回到代码审核
                  </label>
                </div>
              </div>
            )}
            <div className="flex gap-2">
              <Button onClick={onVideoApprove} disabled={submitPending} className="flex-1">
                通过发布
              </Button>
              <Button variant="outline" onClick={onVideoReject} disabled={submitPending} className="flex-1">
                {showVideoRejectInput ? "确认驳回" : "驳回"}
              </Button>
              <Button variant="destructive" onClick={onVideoAbandon} disabled={submitPending}>
                废弃
              </Button>
            </div>
          </div>
        )}
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
      <div className="flex flex-col items-center justify-center flex-1 gap-3 px-6 text-center">
        <p className="text-destructive text-sm">
          {project.status === "narrative_failed" ? "叙事脚本生成失败，请联系管理员" : "代码生成失败"}
        </p>
        {project.status === "code_failed" && (
          <Button onClick={onCodeRetry} disabled={codeRetryPending}>
            重试代码生成
          </Button>
        )}
      </div>
    );
  }

  if (!isCodeReview && !hasCode) {
    return (
      <div className="flex items-center justify-center flex-1">
        <p className="text-muted-foreground text-sm">暂无审核内容</p>
      </div>
    );
  }

  return (
    <>
      {codeVersion?.rejectionContext && (
        <RejectionContextNotice
          context={codeVersion.rejectionContext}
          preferredIssue="code"
        />
      )}
      {/* 渲染失败错误提示 */}
      {isRenderFailed && (renderFailureError || currentVideoAsset?.errorMessage) && (
        <div className="mx-4 mt-3 p-3 rounded-lg border border-destructive/40 bg-destructive/5">
          <div className="mb-1 flex items-center justify-between gap-3">
            <p className="text-xs font-semibold text-destructive">
              视频生成失败 — 请修改代码后重新提交
            </p>
            <Button
              size="sm"
              variant="outline"
              className="h-7 shrink-0 border-destructive/40 text-xs"
              onClick={onAiRepair}
              disabled={repairPending || !codeVersion}
            >
              {repairPending ? "AI 修复中…" : "AI 修复"}
            </Button>
          </div>
          <pre className="text-xs text-destructive/80 whitespace-pre-wrap break-all leading-relaxed max-h-32 overflow-y-auto">
            {renderFailureError || currentVideoAsset?.errorMessage}
          </pre>
        </div>
      )}

      {/* 镜头列表（全宽，代码可编辑） */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        <div className="flex-1 flex min-h-0 flex-col overflow-hidden">
          <div className="px-4 py-2.5 border-b text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            镜头列表（{codeVersion?.scenes.length ?? 0} 个）
          </div>
          <ScrollArea className="flex-1 min-h-0">
            <div className="p-4 space-y-3">
              {codeLoading && <p className="text-sm text-muted-foreground">加载代码…</p>}
              {codeVersion?.scenes.map((scene) => {
                const repair = codeRepairs.get(scene.sceneIndex);
                const repairApplied = appliedRepairs.has(scene.sceneIndex);
                return (
                  <div key={scene.sceneIndex} className="border rounded-lg p-3 space-y-2">
                    <div className="flex items-center gap-2">
                      <Badge variant="secondary" className="text-xs">镜头 {scene.sceneIndex}</Badge>
                      <span className="text-xs text-muted-foreground">~{scene.estimatedDurationSeconds}s</span>
                    </div>
                    <p className="text-sm font-medium">{scene.description}</p>
                    <p className="text-xs text-muted-foreground leading-relaxed">{scene.narration}</p>
                    <SceneBeats beats={scene.beats} />
                    <details className="text-xs" open>
                      <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
                        编辑代码
                      </summary>
                      <Textarea
                        className="mt-2 font-mono text-xs leading-relaxed min-h-[120px]"
                        value={editedCode.get(scene.sceneIndex) ?? scene.code ?? ""}
                        onChange={(e) => {
                          const val = e.target.value;
                          setEditedCode((prev) => {
                            const next = new Map(prev);
                            next.set(scene.sceneIndex, val);
                            return next;
                          });
                        }}
                      />
                    </details>
                    {repair && (
                      <div className="rounded-md border border-primary/30 bg-primary/5 p-3 space-y-2">
                        <div className="flex items-center justify-between gap-3">
                          <div>
                            <p className="text-xs font-semibold text-primary">AI 修复结果</p>
                            <p className="mt-1 text-xs text-muted-foreground">{repair.explanation}</p>
                          </div>
                          <Button
                            size="sm"
                            variant={repairApplied ? "secondary" : "default"}
                            className="h-7 shrink-0 text-xs"
                            onClick={() => onApplyRepair(repair)}
                            disabled={repairApplied}
                          >
                            {repairApplied ? "已使用" : "使用修复"}
                          </Button>
                        </div>
                        <pre className="max-h-48 overflow-auto whitespace-pre-wrap rounded bg-muted/60 p-2 font-mono text-xs leading-relaxed">
                          {repair.code}
                        </pre>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </ScrollArea>
        </div>
      </div>

      {/* 右栏底部操作区（仅 code_review） */}
      {isCodeReview && (
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
            <Button onClick={onApprove} disabled={submitPending} className="flex-1">
              {isRenderFailed ? "修复完成，重新生成视频" : "通过"}
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
        </div>
      )}
    </>
  );
}

function RejectionContextNotice({
  context,
  preferredIssue,
}: {
  context: RejectionContext;
  preferredIssue: "narrative" | "code";
}) {
  const annotations = annotationsFromContext(context).filter((annotation) =>
    preferredIssue === "narrative"
      ? annotation.narrativeIssue
      : annotation.codeIssue || annotation.narrativeIssue,
  );
  const detail = rejectionDetailFromContext(context);
  if (!detail && annotations.length === 0) return null;

  return (
    <div className="mx-4 mt-3 rounded-lg border border-amber-300/60 bg-amber-50 p-3">
      <div className="flex items-center gap-2">
        <MessageSquareWarning className="size-4 text-amber-700" />
        <p className="text-xs font-semibold text-amber-800">
          来自上次视频审核的标注
        </p>
      </div>
      {detail && (
        <p className="mt-2 text-xs leading-relaxed text-amber-900">{detail}</p>
      )}
      {annotations.length > 0 && (
        <div className="mt-2 grid gap-2 md:grid-cols-2">
          {annotations.map((annotation) => (
            <div key={annotation.sceneIndex} className="rounded-md border border-amber-200 bg-background/70 p-2 text-xs">
              <p className="font-medium text-foreground">镜头 {annotation.sceneIndex}</p>
              {annotation.narrativeIssue && (
                <p className="mt-1 text-muted-foreground">叙事：{annotation.narrativeIssue}</p>
              )}
              {annotation.codeIssue && (
                <p className="mt-1 text-muted-foreground">代码：{annotation.codeIssue}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function VideoReviewWorkspace({
  videoUrl,
  scenes,
  readOnly,
  annotations,
  onAnnotationChange,
}: {
  videoUrl: string | null;
  scenes: Scene[];
  readOnly: boolean;
  annotations: Map<number, SceneReviewAnnotation>;
  onAnnotationChange: (
    sceneIndex: number,
    field: "narrativeIssue" | "codeIssue",
    value: string,
  ) => void;
}) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const sceneRefs = useRef<Map<number, HTMLDivElement>>(new Map());
  const [currentTime, setCurrentTime] = useState(0);
  const [videoDuration, setVideoDuration] = useState(0);

  const timings = useMemo<SceneTiming[]>(() => {
    if (scenes.length === 0) return [];
    const explicitDurations = scenes.map((scene) =>
      clampDuration(scene.durationSeconds ?? scene.estimatedDurationSeconds),
    );
    const hasAnyDuration = explicitDurations.some((duration) => duration > 0);
    const fallbackDuration =
      videoDuration > 0 && !hasAnyDuration ? videoDuration / scenes.length : 6;
    let cursor = 0;
    const ranges = scenes.map((scene, index) => {
      const duration = explicitDurations[index] || fallbackDuration;
      const start = cursor;
      const end = cursor + duration;
      cursor = end;
      return { sceneIndex: scene.sceneIndex, start, end, duration };
    });
    if (videoDuration > 0 && ranges.length > 0) {
      ranges[ranges.length - 1] = {
        ...ranges[ranges.length - 1],
        end: Math.max(videoDuration, ranges[ranges.length - 1].end),
      };
    }
    return ranges;
  }, [scenes, videoDuration]);

  const currentSceneIndex = useMemo(() => {
    const current = timings.find(
      (timing, index) =>
        currentTime >= timing.start &&
        (currentTime < timing.end || index === timings.length - 1),
    );
    return current?.sceneIndex ?? scenes[0]?.sceneIndex ?? null;
  }, [currentTime, scenes, timings]);

  useEffect(() => {
    if (currentSceneIndex == null) return;
    sceneRefs.current.get(currentSceneIndex)?.scrollIntoView({
      block: "nearest",
      behavior: "smooth",
    });
  }, [currentSceneIndex]);

  const seekToScene = (sceneIndex: number) => {
    const timing = timings.find((item) => item.sceneIndex === sceneIndex);
    if (!timing || !videoRef.current) return;
    videoRef.current.currentTime = timing.start;
    setCurrentTime(timing.start);
    void videoRef.current.play().catch(() => undefined);
  };

  return (
    <div className="flex flex-1 min-h-0 overflow-hidden">
      <div className="flex min-w-0 flex-1 flex-col p-5">
        {videoUrl ? (
          <video
            ref={videoRef}
            src={videoUrl}
            controls
            className="h-full max-h-[68vh] w-full rounded-lg bg-black object-contain"
            onLoadedMetadata={(event) => setVideoDuration(event.currentTarget.duration || 0)}
            onTimeUpdate={(event) => setCurrentTime(event.currentTarget.currentTime)}
          />
        ) : (
          <div className="flex flex-1 items-center justify-center rounded-lg border bg-muted/20 text-sm text-muted-foreground">
            视频加载中…
          </div>
        )}
      </div>
      <div className="flex w-[380px] shrink-0 flex-col border-l min-h-0">
        <div className="flex items-center justify-between border-b px-4 py-2.5">
          <div>
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              镜头审核
            </p>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {annotations.size} 个镜头已标注
            </p>
          </div>
          {currentSceneIndex != null && (
            <Badge variant="secondary" className="text-xs">
              当前 镜头 {currentSceneIndex}
            </Badge>
          )}
        </div>
        <ScrollArea className="min-h-0 flex-1">
          <div className="space-y-3 p-4">
            {scenes.length === 0 && (
              <p className="text-sm text-muted-foreground">暂无镜头信息</p>
            )}
            {scenes.map((scene) => {
              const timing = timings.find((item) => item.sceneIndex === scene.sceneIndex);
              const annotation = annotations.get(scene.sceneIndex);
              const active = currentSceneIndex === scene.sceneIndex;
              return (
                <div
                  key={scene.sceneIndex}
                  ref={(node) => {
                    if (node) sceneRefs.current.set(scene.sceneIndex, node);
                    else sceneRefs.current.delete(scene.sceneIndex);
                  }}
                  className={`rounded-lg border p-3 transition-colors ${
                    active ? "border-primary bg-primary/5" : "bg-background"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <button
                      type="button"
                      className="inline-flex min-w-0 items-center gap-2 text-left"
                      onClick={() => seekToScene(scene.sceneIndex)}
                    >
                      <span className={`inline-flex size-6 shrink-0 items-center justify-center rounded-md ${
                        active ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
                      }`}>
                        {active ? <Play className="size-3" /> : scene.sceneIndex}
                      </span>
                      <span className="truncate text-sm font-medium">
                        镜头 {scene.sceneIndex}
                      </span>
                    </button>
                    {timing && (
                      <span className="shrink-0 text-xs text-muted-foreground">
                        {formatSeconds(timing.start)} - {formatSeconds(timing.end)}
                      </span>
                    )}
                  </div>
                  <p className="mt-2 line-clamp-2 text-sm text-foreground">
                    {scene.description}
                  </p>
                  <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-muted-foreground">
                    {scene.narration}
                  </p>
                  <div className="mt-3 space-y-2">
                    <label className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                      <FileText className="size-3" />
                      叙事问题
                    </label>
                    <Textarea
                      value={annotation?.narrativeIssue ?? ""}
                      onChange={(event) =>
                        onAnnotationChange(scene.sceneIndex, "narrativeIssue", event.target.value)
                      }
                      readOnly={readOnly}
                      rows={2}
                      placeholder="旁白、结构、事实、节奏等问题"
                      className="text-xs"
                    />
                    <label className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                      <Code2 className="size-3" />
                      代码问题
                    </label>
                    <Textarea
                      value={annotation?.codeIssue ?? ""}
                      onChange={(event) =>
                        onAnnotationChange(scene.sceneIndex, "codeIssue", event.target.value)
                      }
                      readOnly={readOnly}
                      rows={2}
                      placeholder="动画实现、画面同步、渲染效果等问题"
                      className="text-xs"
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </ScrollArea>
      </div>
    </div>
  );
}

function MetaSection({
  project,
  promptSnapshot,
  collapsed,
  onToggle,
}: {
  project: VideoProject;
  promptSnapshot: Record<string, unknown> | null;
  collapsed: boolean;
  onToggle: () => void;
}) {
  return (
    <section className="shrink-0 space-y-3 pb-4">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center justify-between text-left"
      >
        <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">项目配置</span>
        {collapsed ? <ChevronRight className="size-3.5 text-muted-foreground" /> : <ChevronDown className="size-3.5 text-muted-foreground" />}
      </button>
      {!collapsed && (
        <>
          <div className="grid grid-cols-2 gap-y-2 gap-x-4 text-sm">
            <span className="text-muted-foreground">渲染引擎</span>
            <span className="font-medium">{project.renderEngine}</span>
            <span className="text-muted-foreground">TTS 引擎</span>
            <span className="font-medium">{project.ttsEngine === "doubao_1.0" ? "豆包 1.0" : "豆包 2.0"}</span>
            <span className="text-muted-foreground">TTS 音色</span>
            <span className="font-medium">{project.ttsVoice}</span>
            <span className="text-muted-foreground">TTS 语速</span>
            <span className="font-medium">{project.ttsSpeed.toFixed(1)} 倍速</span>
            <span className="text-muted-foreground">画幅比例</span>
            <span className="font-medium">{project.aspectRatio === "landscape" ? "横屏 16:9" : "竖屏 9:16"}</span>
            <span className="text-muted-foreground">重试次数</span>
            <span className="font-medium">{project.retryCount}</span>
            <span className="text-muted-foreground">创建时间</span>
            <span className="font-medium">{formatDateTime(project.createdAt)}</span>
          </div>
          <ProjectStylePrompts promptSnapshot={promptSnapshot} />
        </>
      )}
    </section>
  );
}

// Statuses whose entry event is clickable and has associated content
const FAILURE_STATUSES = new Set(["narrative_failed", "code_failed", "video_failed"]);

const CONTENT_STATUS_MAP: Record<string, "narrative" | "code" | "video"> = {
  narrative_review: "narrative",
  code_review: "code",
  video_review: "video",
  published: "video",
};

interface EventsSectionProps {
  eventsData: { items: ProjectEvent[] } | undefined;
  narrativeVersions: NarrativeVersion[];
  codeVersions: CodeVersion[];
  selectedNode: SelectedNode | null;
  onSelectNode: (node: SelectedNode | null) => void;
  collapsed: boolean;
  onToggle: () => void;
}

function EventsSection({
  eventsData, narrativeVersions, codeVersions, selectedNode, onSelectNode, collapsed, onToggle,
}: EventsSectionProps) {
  const annotated = useMemo(() => {
    const allEvents = eventsData?.items ?? [];
    const statusEvents = allEvents.filter((event) => event.eventType === "status_change");

    return statusEvents.map((event, statusIndex) => {
        const contentType = event.toStatus ? CONTENT_STATUS_MAP[event.toStatus] : undefined;
        const nextSameGateStatus = contentType
          ? statusEvents.slice(statusIndex + 1).find(
              (candidate) =>
                candidate.toStatus &&
                CONTENT_STATUS_MAP[candidate.toStatus] === contentType,
            )
          : undefined;
        const verdictEvent = contentType
          ? allEvents.find(
              (candidate) =>
                candidate.eventType === "review_verdict" &&
                candidate.id > event.id &&
                (!nextSameGateStatus || candidate.id < nextSameGateStatus.id) &&
                candidate.payload?.["gate"] === contentType,
            )
          : undefined;
        const verdict = verdictEvent?.payload as {
          verdict: string;
          rejection_detail?: string;
          target_stage?: string;
          content_version_id?: string;
          content_version_number?: number;
          scene_annotations?: RejectionContext["scene_annotations"];
        } | undefined;

        // For video nodes, versionId/number come from the event directly; no "version" entity exists.
        const videoAssetId = contentType === "video"
          ? ((event.payload?.["video_asset_id"] as string | undefined) ?? null)
          : undefined;
        const isVideoNode = contentType === "video";

        const versions = contentType === "narrative" ? narrativeVersions : codeVersions;
        const fallbackVersion = contentType && !isVideoNode
          ? [...versions]
              .filter((version) => new Date(version.createdAt) <= new Date(event.createdAt))
              .sort((a, b) => b.versionNumber - a.versionNumber)[0]
          : undefined;
        const versionId = isVideoNode
          ? String(event.id)  // sentinel — video nodes use event id as key
          : ((event.payload?.["content_version_id"] as string | undefined) ??
             verdict?.content_version_id ??
             fallbackVersion?.id ??
             null);
        // video_review / published: count how many times video review was entered (1-based)
        const videoReviewIndex = isVideoNode
          ? statusEvents.slice(0, statusIndex + 1).filter(
              (e) => e.toStatus === "video_review" || e.toStatus === "published",
            ).length
          : null;
        const versionNumber = isVideoNode
          ? videoReviewIndex
          : ((event.payload?.["content_version_number"] as number | undefined) ??
             verdict?.content_version_number ??
             fallbackVersion?.versionNumber ??
             null);

        const rawError =
          event.payload?.["error_message"] ?? event.payload?.["render_error"];
        const isFailureNode = FAILURE_STATUSES.has(event.toStatus ?? "");
        const renderError =
          isFailureNode ||
          (event.payload?.["render_error"] && event.payload?.["trigger"] !== "video_failed")
            ? (typeof rawError === "string" ? rawError : null)
            : null;

        return { event, contentType, versionId, versionNumber, verdict: verdict ?? null, renderError, videoAssetId };
      });
  }, [eventsData, narrativeVersions, codeVersions]);

  return (
    <section className="flex min-h-0 flex-1 flex-col gap-3">
      <button
        type="button"
        onClick={onToggle}
        className="flex shrink-0 items-center justify-between text-left"
      >
        <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
          状态时间线
        </span>
        {collapsed ? <ChevronRight className="size-3.5 text-muted-foreground" /> : <ChevronDown className="size-3.5 text-muted-foreground" />}
      </button>
      {collapsed ? (
        <p className="text-xs text-muted-foreground">已收起</p>
      ) : (
      <ScrollArea className="min-h-0 flex-1">
        {!annotated.length ? (
          <p className="text-sm text-muted-foreground">暂无事件记录</p>
        ) : (
          <div className="space-y-0 pr-3">
            {annotated.map(({ event, contentType, versionId, versionNumber, verdict, renderError, videoAssetId }, i) => {
              const isClickable = !!(contentType && versionId);
              const isSelected = selectedNode?.eventId === event.id;
              const isLast = i === annotated.length - 1;
              const isRenderFailedNode = FAILURE_STATUSES.has(event.toStatus ?? "") || !!renderError;

              const verdictLabel = verdict?.verdict === "approved"
                ? { text: "通过", color: "text-green-600" }
                : verdict?.verdict === "rejected"
                ? { text: "驳回", color: "text-destructive" }
                : verdict?.verdict === "abandoned"
                ? { text: "废弃", color: "text-muted-foreground" }
                : verdict?.verdict === "retry"
                ? { text: "重试", color: "text-amber-600" }
                : null;

              const handleClick = () => {
                if (!isClickable) return;
                onSelectNode(isSelected ? null : {
                  type: contentType!,
                  versionId: versionId!,
                  versionNumber: versionNumber!,
                  eventId: event.id,
                  ...(contentType === "video" ? { videoAssetId } : {}),
                });
              };

              return (
                <div key={event.id} className="flex gap-3">
                  <div className="flex flex-col items-center">
                    <div
                      className={`w-2.5 h-2.5 rounded-full mt-1.5 shrink-0 border-2 transition-colors ${
                        isRenderFailedNode
                          ? "bg-destructive border-destructive"
                          : isSelected
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
                      <p className={`text-sm font-medium leading-snug ${isRenderFailedNode ? "text-destructive" : isSelected ? "text-primary" : ""}`}>
                        {event.toStatus
                          ? (PROJECT_STATUS_LABELS[event.toStatus] ?? event.toStatus)
                          : (EVENT_TYPE_LABELS[event.eventType] ?? event.eventType)}
                      </p>
                      {isClickable && (
                        <span className="text-xs text-muted-foreground">v{versionNumber}</span>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {formatDateTime(event.createdAt)}
                    </p>
                    {/* Render failure error message */}
                    {renderError && (
                      <details className="mt-1" onClick={(clickEvent) => clickEvent.stopPropagation()}>
                        <summary className="text-xs text-destructive cursor-pointer">查看失败原因</summary>
                        <pre className="mt-1 text-xs text-destructive/80 whitespace-pre-wrap break-all leading-relaxed max-h-28 overflow-y-auto bg-destructive/5 rounded p-1.5">
                          {renderError}
                        </pre>
                      </details>
                    )}
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
                        {verdict?.scene_annotations && verdict.scene_annotations.length > 0 && (
                          <details className="mt-1" onClick={(clickEvent) => clickEvent.stopPropagation()}>
                            <summary className="cursor-pointer text-xs text-primary/80">
                              {normalizeAnnotations(verdict.scene_annotations).length} 个镜头标注
                            </summary>
                            <div className="mt-1 space-y-1">
                              {normalizeAnnotations(verdict.scene_annotations).map((annotation) => (
                                <div key={annotation.sceneIndex} className="rounded bg-muted/40 p-1.5 text-xs text-muted-foreground">
                                  <p className="font-medium text-foreground">镜头 {annotation.sceneIndex}</p>
                                  {annotation.narrativeIssue && <p>叙事：{annotation.narrativeIssue}</p>}
                                  {annotation.codeIssue && <p>代码：{annotation.codeIssue}</p>}
                                </div>
                              ))}
                            </div>
                          </details>
                        )}
                        {verdict?.target_stage && verdict.verdict === "rejected" && (
                          <p className="text-xs text-muted-foreground">
                            回退至：{verdict.target_stage === "code"
                              ? "重新生成代码"
                              : "叙事审核"}
                          </p>
                        )}
                      </div>
                    )}
                    {isClickable && (
                      <p className="text-xs text-primary/70 mt-0.5">
                        {isSelected ? "收起 ↑" : contentType === "video" ? "查看视频 →" : "查看内容 →"}
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </ScrollArea>
      )}
    </section>
  );
}

// ── Historical read-only view ──────────────────────────────────────────────

interface HistoricalViewProps {
  node: SelectedNode;
  narrativeVersion: NarrativeVersion | null;
  codeVersion: CodeVersion | null;
  videoUrl: string | null;
  onClose: () => void;
}

function HistoricalView({ node, narrativeVersion, codeVersion, videoUrl, onClose }: HistoricalViewProps) {
  const version = node.type === "narrative" ? narrativeVersion : node.type === "code" ? codeVersion : null;
  const typeLabel = node.type === "narrative" ? "叙事脚本" : node.type === "code" ? "渲染代码" : "视频";

  return (
    <div className="flex flex-col flex-1 min-h-0 overflow-hidden">
      {/* Banner */}
      <div className="flex items-center justify-between px-5 py-2.5 border-b bg-muted/40 shrink-0">
        <span className="text-xs text-muted-foreground">
          正在查看历史版本 — {typeLabel} v{node.versionNumber}（只读）
        </span>
        <Button variant="ghost" size="sm" className="h-6 text-xs" onClick={onClose}>
          返回当前
        </Button>
      </div>

      {node.type === "video" ? (
        <div className="flex-1 min-h-0 p-5">
          {videoUrl ? (
            <video src={videoUrl} controls className="w-full h-full max-h-[60vh] rounded-lg bg-black" />
          ) : (
            <div className="flex items-center justify-center h-40 text-muted-foreground text-sm">
              视频加载中…
            </div>
          )}
        </div>
      ) : !version ? (
        <div className="flex items-center justify-center flex-1">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary" />
        </div>
      ) : node.type === "narrative" ? (
        <HistoricalNarrativeView version={narrativeVersion!} />
      ) : (
        <HistoricalCodeView version={codeVersion!} />
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
              <SceneBeats beats={scene.beats} defaultOpen={false} />
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

function HistoricalCodeView({ version }: { version: CodeVersion }) {
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
              <SceneBeats beats={scene.beats} defaultOpen={false} />
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
