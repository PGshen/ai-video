import { SidePanel, SidePanelHeader, SidePanelBody } from "@/components/ui/side-panel";
import { useProjectEvents } from "@/hooks/useProjects";
import { PROJECT_STATUS_LABELS, PROJECT_STATUS_COLORS, timeAgo } from "@/lib/format";
import type { VideoProject } from "@/types";

interface Props {
  project: VideoProject | null;
  onClose: () => void;
}

const EVENT_TYPE_LABELS: Record<string, string> = {
  status_change: "状态变更",
  signal_sent: "信号发送",
};

export function ProjectSheet({ project, onClose }: Props) {
  const { data: eventsData } = useProjectEvents(project?.id ?? "");

  if (!project) return null;

  const statusColor = PROJECT_STATUS_COLORS[project.status] ?? "bg-gray-100 text-gray-600";
  const statusLabel = PROJECT_STATUS_LABELS[project.status] ?? project.status;

  return (
    <SidePanel open={!!project} onClose={onClose}>
      <SidePanelHeader>
        <div className="pr-7">
          <h2 className="text-base font-semibold leading-snug">{project.topicTitle}</h2>
          <div className="flex items-center gap-2 mt-2">
            <span className={`px-2 py-0.5 rounded text-xs font-medium ${statusColor}`}>
              {statusLabel}
            </span>
          </div>
        </div>
      </SidePanelHeader>

      <SidePanelBody className="space-y-6">
        {/* Project meta */}
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

        {/* Timeline */}
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
                    {i < eventsData.items.length - 1 && (
                      <div className="w-px flex-1 bg-border mt-1" />
                    )}
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

        <p className="text-xs text-muted-foreground text-center pt-2">
          脚本和视频功能将在 Sprint 2/3 开放
        </p>
      </SidePanelBody>
    </SidePanel>
  );
}
