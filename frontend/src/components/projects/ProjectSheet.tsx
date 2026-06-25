import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
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
    <Sheet open={!!project} onOpenChange={onClose}>
      <SheetContent className="w-[440px] sm:max-w-[440px] flex flex-col">
        <SheetHeader>
          <SheetTitle className="text-base leading-snug pr-6">{project.topicTitle}</SheetTitle>
          <div className="flex items-center gap-2 mt-1">
            <span className={`px-2 py-0.5 rounded text-xs font-medium ${statusColor}`}>
              {statusLabel}
            </span>
          </div>
        </SheetHeader>

        <div className="py-4 space-y-3 text-sm">
          <div className="grid grid-cols-2 gap-2 text-muted-foreground">
            <span>渲染引擎</span><span className="text-foreground font-medium">{project.renderEngine}</span>
            <span>TTS 声音</span><span className="text-foreground font-medium">{project.ttsVoice}</span>
            <span>画幅比例</span><span className="text-foreground font-medium">{project.aspectRatio === "landscape" ? "横屏 16:9" : "竖屏 9:16"}</span>
            <span>重试次数</span><span className="text-foreground font-medium">{project.retryCount}</span>
            <span>创建时间</span><span className="text-foreground font-medium">{timeAgo(project.createdAt)}</span>
          </div>
        </div>

        <Separator />

        <div className="flex-1 min-h-0 flex flex-col mt-4">
          <p className="text-sm font-medium mb-3">状态时间线</p>
          <ScrollArea className="flex-1">
            {!eventsData?.items.length ? (
              <p className="text-sm text-muted-foreground">暂无事件记录</p>
            ) : (
              <div className="space-y-3">
                {eventsData.items.map((event) => (
                  <div key={event.id} className="flex gap-3">
                    <div className="flex flex-col items-center">
                      <div className="w-2 h-2 rounded-full bg-primary mt-1.5 shrink-0" />
                      <div className="w-px flex-1 bg-border mt-1" />
                    </div>
                    <div className="pb-3 min-w-0">
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
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {timeAgo(event.createdAt)}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </ScrollArea>
        </div>

        <Separator />
        <div className="pt-3 pb-1">
          <p className="text-sm text-muted-foreground text-center">
            脚本和视频功能将在 Sprint 2/3 开放
          </p>
        </div>
      </SheetContent>
    </Sheet>
  );
}
