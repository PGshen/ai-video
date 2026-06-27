import { useState, useMemo } from "react";
import { useParams } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Textarea } from "@/components/ui/textarea";
import { FactCheckCard } from "@/components/review/FactCheckCard";
import { useProject, useProjectScript, useSubmitReview } from "@/hooks/useProjects";
import type { ProjectStatus } from "@/types";

type Verdict = "approved" | "rejected" | "needs_revision";

interface VerdictState {
  verdict: Verdict;
  note: string;
}

const STATUS_LABELS: Record<ProjectStatus, string> = {
  draft: "草稿",
  narrative_generating: "AI 生成叙事脚本中…",
  narrative_review: "待叙事审核",
  narrative_failed: "叙事生成失败",
  code_generating: "AI 生成代码中…",
  code_failed: "代码生成失败",
  script_review: "待审核",
  video_generating: "视频渲染中…",
  video_failed: "视频生成失败",
  video_review: "待视频审核",
  published: "已发布",
  abandoned: "已废弃",
};

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: project, isLoading: projectLoading } = useProject(id!);
  const { data: script, isLoading: scriptLoading } = useProjectScript(id!);
  const submitReview = useSubmitReview();

  const [verdicts, setVerdicts] = useState<Record<number, VerdictState>>({});
  const [rejectionDetail, setRejectionDetail] = useState("");
  const [showRejectInput, setShowRejectInput] = useState(false);

  const allMarked = useMemo(() => {
    if (!script || script.factChecks.length === 0) return true;
    return script.factChecks.every((_, i) => verdicts[i] !== undefined);
  }, [script, verdicts]);

  const handleVerdictChange = (index: number, verdict: Verdict, note: string) => {
    setVerdicts((prev) => ({ ...prev, [index]: { verdict, note } }));
  };

  const buildVerdictList = () =>
    Object.entries(verdicts).map(([i, v]) => ({
      index: Number(i),
      verdict: v.verdict,
      note: v.note || "",
    }));

  const handleApprove = () => {
    submitReview.mutate({
      projectId: id!,
      gate: "script",
      verdict: "approved",
      factCheckVerdicts: buildVerdictList(),
    });
  };

  const handleReject = () => {
    if (!showRejectInput) {
      setShowRejectInput(true);
      return;
    }
    submitReview.mutate({
      projectId: id!,
      gate: "script",
      verdict: "rejected",
      rejectionDetail,
      factCheckVerdicts: buildVerdictList(),
    });
  };

  const handleAbandon = () => {
    if (!window.confirm("确认废弃该项目？此操作不可撤销。")) return;
    submitReview.mutate({
      projectId: id!,
      gate: "script",
      verdict: "abandoned",
    });
  };

  if (projectLoading) {
    return <div className="p-6 text-muted-foreground">加载中…</div>;
  }
  if (!project) {
    return <div className="p-6 text-destructive">项目不存在</div>;
  }

  const isScriptReview = project.status === "script_review";
  const retryCount = project.retryCount;
  const canReject = retryCount < 3;

  return (
    <div className="flex flex-col h-full">
      {/* 顶部状态栏 */}
      <div className="flex items-center gap-3 px-6 py-4 border-b">
        <h1 className="text-lg font-semibold truncate flex-1">项目详情</h1>
        <Badge variant="outline">{STATUS_LABELS[project.status] ?? project.status}</Badge>
        {retryCount > 0 && (
          <span className="text-xs text-muted-foreground">已驳回 {retryCount} 次</span>
        )}
      </div>

      {(project.status === "narrative_generating" || project.status === "code_generating") && (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center space-y-2">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto" />
            <p className="text-muted-foreground">{STATUS_LABELS[project.status]}</p>
          </div>
        </div>
      )}

      {(project.status === "narrative_failed" || project.status === "code_failed") && (
        <div className="flex-1 flex items-center justify-center">
          <p className="text-destructive">{STATUS_LABELS[project.status]}，请联系管理员</p>
        </div>
      )}

      {!["narrative_generating", "narrative_failed", "code_generating", "code_failed", "script_review"].includes(project.status) &&
        project.status !== "draft" && (
          <div className="flex-1 flex items-center justify-center">
            <p className="text-muted-foreground">
              当前状态：{STATUS_LABELS[project.status] ?? project.status}
            </p>
          </div>
        )}

      {/* 脚本审核主区域 */}
      {(isScriptReview || script) && (
          <div className="flex flex-1 overflow-hidden">
            {/* 左：镜头列表 */}
            <div className="w-1/2 border-r flex flex-col">
              <div className="px-4 py-3 border-b text-sm font-medium">
                镜头列表（{script?.scenes.length ?? 0} 个）
              </div>
              <ScrollArea className="flex-1">
                <div className="p-4 space-y-4">
                  {scriptLoading && (
                    <p className="text-sm text-muted-foreground">加载脚本…</p>
                  )}
                  {script?.scenes.map((scene) => (
                    <div key={scene.sceneIndex} className="border rounded-lg p-4 space-y-2">
                      <div className="flex items-center gap-2">
                        <Badge variant="secondary" className="text-xs">
                          镜头 {scene.sceneIndex}
                        </Badge>
                        <span className="text-xs text-muted-foreground">
                          ~{scene.estimatedDurationSeconds}s
                        </span>
                      </div>
                      <p className="text-sm font-medium">{scene.description}</p>
                      <p className="text-sm text-muted-foreground leading-relaxed">
                        {scene.narration}
                      </p>
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
            <div className="w-1/2 flex flex-col">
              <div className="px-4 py-3 border-b text-sm font-medium">
                事实核查（{script?.factChecks.length ?? 0} 条）
              </div>
              <ScrollArea className="flex-1">
                <div className="p-4 space-y-4">
                  {script?.factChecks.map((item, idx) => (
                    <FactCheckCard
                      key={idx}
                      item={item}
                      index={idx}
                      verdict={verdicts[idx]?.verdict ?? null}
                      note={verdicts[idx]?.note ?? ""}
                      onVerdictChange={handleVerdictChange}
                    />
                  ))}
                </div>
              </ScrollArea>

              {/* 底部操作栏 */}
              {isScriptReview && (
                <div className="border-t p-4 space-y-3">
                  {showRejectInput && (
                    <Textarea
                      value={rejectionDetail}
                      onChange={(e) => setRejectionDetail(e.target.value)}
                      placeholder="请说明驳回原因（AI 重新生成时会参考此信息）"
                      className="text-sm min-h-[80px]"
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
                    <Button
                      variant="destructive"
                      onClick={handleAbandon}
                      disabled={submitReview.isPending}
                    >
                      废弃
                    </Button>
                  </div>
                  {!allMarked && script && script.factChecks.length > 0 && (
                    <p className="text-xs text-muted-foreground text-center">
                      请为所有核查条目标注审核结果后再提交
                    </p>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
    </div>
  );
}
