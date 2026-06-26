import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useProjects } from "@/hooks/useProjects";
import {
  timeAgo,
  PROJECT_STATUS_LABELS,
  PROJECT_STATUS_COLORS,
} from "@/lib/format";

export default function ProjectsPage() {
  const [statusFilter, setStatusFilter] = useState("all");
  const navigate = useNavigate();

  const { data, isLoading } = useProjects(statusFilter === "all" ? undefined : statusFilter);

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">视频项目</h1>
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

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[280px]">选题</TableHead>
              <TableHead>状态</TableHead>
              <TableHead>渲染引擎</TableHead>
              <TableHead>画幅比例</TableHead>
              <TableHead>创建时间</TableHead>
              <TableHead className="w-[80px]"></TableHead>
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
                onClick={() => navigate(`/projects/${project.id}`)}
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
                  {timeAgo(project.createdAt)}
                </TableCell>
                <TableCell>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={(e) => { e.stopPropagation(); navigate(`/projects/${project.id}`); }}
                  >
                    详情
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

    </div>
  );
}
