import { useEffect, useState } from "react";
import { RotateCcw, Search, Trash2, X } from "lucide-react";
import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useDeleteProject, useProjects, useResetProject } from "@/hooks/useProjects";
import { ProjectSheet } from "@/components/projects/ProjectSheet";
import { ListPagination } from "@/components/ListPagination";
import {
  formatDateTime,
  PROJECT_STATUS_LABELS,
  PROJECT_STATUS_COLORS,
} from "@/lib/format";
import type { VideoProject } from "@/types";

const PAGE_SIZE = 10;

const RESETTABLE_STATUSES = new Set([
  "narrative_generating",
  "code_generating",
  "code_failed",
  "video_generating",
]);

export default function ProjectsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [statusFilter, setStatusFilter] = useState("all");
  const [titleFilter, setTitleFilter] = useState("");
  const [debouncedTitleFilter, setDebouncedTitleFilter] = useState("");
  const [renderEngineFilter, setRenderEngineFilter] = useState("all");
  const [aspectRatioFilter, setAspectRatioFilter] = useState("all");
  const [page, setPage] = useState(1);
  const [selectedProject, setSelectedProject] = useState<VideoProject | null>(null);
  const topicId = searchParams.get("topicId") ?? undefined;
  const topicTitle = searchParams.get("topicTitle");

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedTitleFilter(titleFilter.trim());
    }, 300);

    return () => window.clearTimeout(timer);
  }, [titleFilter]);

  const { data, isLoading } = useProjects({
    status: statusFilter === "all" ? undefined : statusFilter,
    topicId,
    topicTitle: debouncedTitleFilter || undefined,
    renderEngine: renderEngineFilter === "all" ? undefined : renderEngineFilter,
    aspectRatio: aspectRatioFilter === "all" ? undefined : aspectRatioFilter,
    page,
    pageSize: PAGE_SIZE,
  });
  const deleteProject = useDeleteProject();
  const resetProject = useResetProject();
  const totalPages = Math.max(1, Math.ceil((data?.total ?? 0) / PAGE_SIZE));

  useEffect(() => {
    setPage(1);
  }, [
    statusFilter,
    debouncedTitleFilter,
    renderEngineFilter,
    aspectRatioFilter,
    topicId,
  ]);

  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  const handleDelete = (project: VideoProject) => {
    const title = project.topicTitle || "未命名项目";
    if (!window.confirm(`确认删除项目「${title}」？此操作不可撤销。`)) return;
    deleteProject.mutate(project.id, {
      onSuccess: () => {
        if (selectedProject?.id === project.id) setSelectedProject(null);
        toast.success("项目已删除");
      },
      onError: (error) => toast.error(error.message || "删除失败，请重试"),
    });
  };

  const handleReset = (project: VideoProject) => {
    const title = project.topicTitle || "未命名项目";
    const isCodeRetry = project.status === "code_failed";
    const message = isCodeRetry
      ? `确认重试项目「${title}」的代码生成？`
      : `确认重置项目「${title}」当前阶段？请先确认该阶段确已卡死。`;
    if (!window.confirm(message)) return;
    resetProject.mutate(project.id, {
      onSuccess: () => toast.success(isCodeRetry ? "已重新排队生成代码" : "已重置，任务重新排队"),
      onError: (error) => toast.error(error.message || "重置失败，请重试"),
    });
  };

  return (
    <div className="p-6 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-semibold">视频项目</h1>
          {topicId && (
            <div className="flex items-center gap-1 rounded-md bg-muted px-2.5 py-1 text-sm">
              <span>选题：{topicTitle || topicId}</span>
              <Button
                variant="ghost"
                size="icon-sm"
                aria-label="清除选题筛选"
                title="清除选题筛选"
                onClick={() => {
                  const next = new URLSearchParams(searchParams);
                  next.delete("topicId");
                  next.delete("topicTitle");
                  setSearchParams(next);
                }}
              >
                <X />
              </Button>
            </div>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={titleFilter}
              onChange={(event) => setTitleFilter(event.target.value)}
              placeholder="搜索选题标题"
              aria-label="搜索选题标题"
              className="w-52 pl-9"
            />
          </div>
          <Select value={renderEngineFilter} onValueChange={(v) => setRenderEngineFilter(v ?? "all")}>
            <SelectTrigger className="w-36">
              <SelectValue>
                {renderEngineFilter === "all" ? "全部引擎" : renderEngineFilter === "manim" ? "Manim" : "Remotion"}
              </SelectValue>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部引擎</SelectItem>
              <SelectItem value="manim">Manim</SelectItem>
              <SelectItem value="remotion">Remotion</SelectItem>
            </SelectContent>
          </Select>
          <Select value={aspectRatioFilter} onValueChange={(v) => setAspectRatioFilter(v ?? "all")}>
            <SelectTrigger className="w-36">
              <SelectValue>
                {aspectRatioFilter === "all" ? "全部画幅" : aspectRatioFilter === "landscape" ? "横屏" : "竖屏"}
              </SelectValue>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部画幅</SelectItem>
              <SelectItem value="landscape">横屏</SelectItem>
              <SelectItem value="portrait">竖屏</SelectItem>
            </SelectContent>
          </Select>
          <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v ?? "all")}>
            <SelectTrigger className="w-36">
              <SelectValue>{statusFilter === "all" ? "全部状态" : PROJECT_STATUS_LABELS[statusFilter]}</SelectValue>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部状态</SelectItem>
              {Object.entries(PROJECT_STATUS_LABELS).map(([val, label]) => (
                <SelectItem key={val} value={val}>{label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[280px]">选题</TableHead>
              <TableHead>状态</TableHead>
              <TableHead>渲染引擎</TableHead>
              <TableHead>画幅比例</TableHead>
              <TableHead>创建时间</TableHead>
              <TableHead>操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading && (
              <TableRow>
                <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
                  加载中...
                </TableCell>
              </TableRow>
            )}
            {!isLoading && !data?.items.length && (
              <TableRow>
                <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
                  暂无项目，请从选题页创建
                </TableCell>
              </TableRow>
            )}
            {data?.items.map((project) => (
              <TableRow
                key={project.id}
                className="cursor-pointer hover:bg-muted/50"
                onClick={() => setSelectedProject(project)}
              >
                <TableCell className="font-medium max-w-[280px] truncate">
                  {project.topicTitle || "-"}
                </TableCell>
                <TableCell>
                  <span
                    className={`px-2 py-0.5 rounded text-xs font-medium ${
                      PROJECT_STATUS_COLORS[project.status] ?? "bg-gray-100 text-gray-600"
                    }`}
                  >
                    {PROJECT_STATUS_LABELS[project.status] ?? project.status}
                  </span>
                </TableCell>
                <TableCell className="text-sm">{project.renderEngine}</TableCell>
                <TableCell className="text-sm">
                  {project.aspectRatio === "landscape" ? "横屏" : "竖屏"}
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {formatDateTime(project.createdAt)}
                </TableCell>
                <TableCell>
                  <div className="flex items-center justify-end gap-1">
                    {/* <Button
                      variant="ghost"
                      size="sm"
                      onClick={(e) => { e.stopPropagation(); setSelectedProject(project); }}
                    >
                      详情
                    </Button> */}
                    {RESETTABLE_STATUSES.has(project.status) && (
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        className="text-muted-foreground text-destructive"
                        aria-label={`${project.status === "code_failed" ? "重试代码生成" : "重置项目"}：${project.topicTitle || "未命名项目"}`}
                        title={project.status === "code_failed" ? "重试代码生成" : "重置卡死阶段"}
                        disabled={resetProject.isPending}
                        onClick={(e) => { e.stopPropagation(); handleReset(project); }}
                      >
                        <RotateCcw />
                      </Button>
                    )}
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      className="text-muted-foreground hover:text-destructive"
                      aria-label={`删除项目：${project.topicTitle || "未命名项目"}`}
                      title="删除项目"
                      disabled={deleteProject.isPending}
                      onClick={(e) => { e.stopPropagation(); handleDelete(project); }}
                    >
                      <Trash2 />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <ListPagination
        page={page}
        pageSize={PAGE_SIZE}
        total={data?.total ?? 0}
        onPageChange={setPage}
      />

      <ProjectSheet
        project={selectedProject}
        onClose={() => setSelectedProject(null)}
      />
    </div>
  );
}
