import { useState, useMemo } from "react";
import { SidePanel, SidePanelHeader, SidePanelBody, SidePanelFooter } from "@/components/ui/side-panel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Textarea } from "@/components/ui/textarea";
import { FactCheckCard } from "@/components/review/FactCheckCard";
import { useProjectEvents, useProjectScript, useSubmitReview } from "@/hooks/useProjects";
import { PROJECT_STATUS_LABELS, PROJECT_STATUS_COLORS, timeAgo } from "@/lib/format";
import type { VideoProject } from "@/types";

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

const SCRIPT_STATES = ["script_review", "script_generating", "script_failed",
  "video_generating", "video_failed", "video_review", "published"];

export function ProjectSheet({ project, onClose }: Props) {
  const { data: eventsData } = useProjectEvents(project?.id ?? "");
  const { data: script, isLoading: scriptLoading } = useProjectScript(project?.id ?? "");
  const submitReview = useSubmitReview();

  const [verdicts, setVerdicts] = useState<Record<number, VerdictState>>({});
  const [rejectionDetail, setRejectionDetail] = useState("");
  const [showRejectInput, setShowRejectInput] = useState(false);

  const isScriptReview = project?.status === "script_review";
  const hasScript = !!script;
  const showScriptPanel = project != null && SCRIPT_STATES.includes(project.status);
  const wide = showScriptPanel;

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
    submitReview.mutate({
      projectId: project.id,
      gate: "script",
      verdict: "approved",
      factCheckVerdicts: buildVerdictList(),
    });
  };

  const handleReject = () => {
    if (!project) return;
    if (!showRejectInput) { setShowRejectInput(true); return; }
    submitReview.mutate({
      projectId: project.id,
      gate: "script",
      verdict: "rejected",
      rejectionDetail,
      factCheckVerdicts: buildVerdictList(),
    });
  };

  const handleAbandon = () => {
    if (!project) return;
    if (!window.confirm("确认废弃该项目？此操作不可撤销。")) return;
    submitReview.mutate({ projectId: project.id, gate: "script", verdict: "abandoned" });
  };

  if (!project) return null;

  const statusColor = PROJECT_STATUS_COLORS[project.status] ?? "bg-gray-100 text-gray-600";
  const statusLabel = PROJECT_STATUS_LABELS[project.status] ?? project.status;
  const canReject = project.retryCount < 3;

  return (
    <SidePanel open={!!project} onClose={onClose} wide={wide}>
      <SidePanelHeader>
        <div className="pr-7 flex items-start justify-between">
          <div>
            <h2 className="text-base font-semibold leading-snug">{project.topicTitle}</h2>
            <div className="flex items-center gap-2 mt-2">
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${statusColor}`}>
                {statusLabel}
              </span>
              {project.retryCount > 0 && (
                <span className="text-xs text-muted-foreground">已驳回 {project.retryCount} 次</span>
              )}
            </div>
          </div>
        </div>
      </SidePanelHeader>

      {/* 非脚本状态：普通详情视图 */}
      {!showScriptPanel && (
        <SidePanelBody className="space-y-6">
          <MetaSection project={project} />
          <EventsSection eventsData={eventsData} />
        </SidePanelBody>
      )}

      {/* 脚本状态：两列审核视图 */}
      {showScriptPanel && (
        <>
          {project.status === "script_generating" && (
            <SidePanelBody>
              <div className="flex flex-col items-center justify-center h-full gap-3 py-20">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
                <p className="text-muted-foreground text-sm">AI 正在生成脚本，请稍候…</p>
              </div>
            </SidePanelBody>
          )}

          {project.status === "script_failed" && (
            <SidePanelBody>
              <p className="text-destructive text-sm pt-4">脚本生成失败，请联系管理员</p>
            </SidePanelBody>
          )}

          {(isScriptReview || hasScript) &&
            !["script_generating", "script_failed"].includes(project.status) && (
              <div className="flex flex-1 overflow-hidden">
                {/* 左：镜头列表 */}
                <div className="w-1/2 border-r flex flex-col overflow-hidden">
                  <div className="px-4 py-2.5 border-b text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                    镜头列表（{script?.scenes.length ?? 0} 个）
                  </div>
                  <ScrollArea className="flex-1">
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

                {/* 右：事实核查表 */}
                <div className="w-1/2 flex flex-col overflow-hidden">
                  <div className="px-4 py-2.5 border-b text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                    事实核查（{script?.factChecks.length ?? 0} 条）
                  </div>
                  <ScrollArea className="flex-1">
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
            )}

          {/* 底部操作栏 */}
          {isScriptReview && (
            <SidePanelFooter className="space-y-2">
              {showRejectInput && (
                <Textarea
                  value={rejectionDetail}
                  onChange={(e) => setRejectionDetail(e.target.value)}
                  placeholder="请说明驳回原因（AI 重新生成时会参考此信息）"
                  className="text-sm min-h-[72px]"
                />
              )}
              <div className="flex gap-2">
                <Button
                  onClick={handleApprove}
                  disabled={!allMarked || submitReview.isPending}
                  className="flex-1"
                >
                  通过
                </Button>
                {canReject && (
                  <Button
                    variant="outline"
                    onClick={handleReject}
                    disabled={submitReview.isPending}
                    className="flex-1"
                  >
                    {showRejectInput ? "确认驳回" : "驳回重生成"}
                  </Button>
                )}
                <Button variant="destructive" onClick={handleAbandon} disabled={submitReview.isPending}>
                  废弃
                </Button>
              </div>
              {!allMarked && script && script.factChecks.length > 0 && (
                <p className="text-xs text-muted-foreground text-center">请为所有核查条目标注审核结果后再提交</p>
              )}
            </SidePanelFooter>
          )}
        </>
      )}
    </SidePanel>
  );
}

function MetaSection({ project }: { project: VideoProject }) {
  return (
    <section className="space-y-3">
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

function EventsSection({ eventsData }: { eventsData: { items: import("@/types").ProjectEvent[] } | undefined }) {
  return (
    <section className="space-y-3">
      <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">状态时间线</p>
      {!eventsData?.items.length ? (
        <p className="text-sm text-muted-foreground">暂无事件记录</p>
      ) : (
        <div className="space-y-0">
          {eventsData.items.map((event, i) => (
            <div key={event.id} className="flex gap-3">
              <div className="flex flex-col items-center">
                <div className="w-2 h-2 rounded-full bg-primary mt-1.5 shrink-0" />
                {i < eventsData.items.length - 1 && <div className="w-px flex-1 bg-border mt-1" />}
              </div>
              <div className="pb-4 min-w-0">
                <p className="text-sm font-medium">
                  {EVENT_TYPE_LABELS[event.eventType] ?? event.eventType}
                </p>
                {event.fromStatus && event.toStatus && (
                  <p className="text-xs text-muted-foreground">
                    {PROJECT_STATUS_LABELS[event.fromStatus] ?? event.fromStatus}
                    {" → "}
                    {PROJECT_STATUS_LABELS[event.toStatus] ?? event.toStatus}
                  </p>
                )}
                <p className="text-xs text-muted-foreground mt-0.5">{timeAgo(event.createdAt)}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
