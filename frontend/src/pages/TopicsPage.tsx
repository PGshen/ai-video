import { useState } from "react";
import { Plus, Sparkles, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { useDeleteTopic, useTopics } from "@/hooks/useTopics";
import { BrainstormDialog } from "@/components/topics/BrainstormDialog";
import { CreateTopicDialog } from "@/components/topics/CreateTopicDialog";
import { TopicSheet } from "@/components/topics/TopicSheet";
import {
  timeAgo,
  SOURCE_LABELS,
  TOPIC_STATUS_LABELS,
  TOPIC_STATUS_COLORS,
} from "@/lib/format";
import type { Topic } from "@/types";

function ScoreBadge({ score }: { score: number | null }) {
  if (score === null) return <span className="text-muted-foreground text-sm">-</span>;
  const color =
    score >= 4
      ? "bg-green-100 text-green-800"
      : score >= 2.5
      ? "bg-yellow-100 text-yellow-800"
      : "bg-red-100 text-red-800";
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${color}`}>
      {score.toFixed(1)}
    </span>
  );
}

export default function TopicsPage() {
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [createOpen, setCreateOpen] = useState(false);
  const [brainstormOpen, setBrainstormOpen] = useState(false);
  const [selectedTopic, setSelectedTopic] = useState<Topic | null>(null);

  const { data, isLoading } = useTopics(statusFilter === "all" ? undefined : statusFilter);
  const deleteTopic = useDeleteTopic();

  const handleDelete = (topic: Topic) => {
    if (!window.confirm(`确认删除选题「${topic.title}」？此操作不可撤销。`)) return;
    deleteTopic.mutate(topic.id, {
      onSuccess: () => {
        if (selectedTopic?.id === topic.id) setSelectedTopic(null);
        toast.success("选题已删除");
      },
      onError: (error) => toast.error(error.message || "删除失败，请重试"),
    });
  };

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">选题池</h1>
        <div className="flex items-center gap-3">
          <Select value={statusFilter} onValueChange={(v) => v && setStatusFilter(v)}>
            <SelectTrigger className="w-32">
              <SelectValue>{statusFilter === "all" ? "全部状态" : TOPIC_STATUS_LABELS[statusFilter]}</SelectValue>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部状态</SelectItem>
              {Object.entries(TOPIC_STATUS_LABELS).map(([val, label]) => (
                <SelectItem key={val} value={val}>{label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button variant="outline" onClick={() => setBrainstormOpen(true)}>
            <Sparkles />
            AI 批量生成
          </Button>
          <Button onClick={() => setCreateOpen(true)}>
            <Plus />
            新增选题
          </Button>
        </div>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[280px]">标题</TableHead>
              <TableHead>来源</TableHead>
              <TableHead>综合评分</TableHead>
              <TableHead>状态</TableHead>
              <TableHead>标签</TableHead>
              <TableHead>创建时间</TableHead>
              <TableHead className="w-[128px]"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading && (
              <TableRow>
                <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                  加载中...
                </TableCell>
              </TableRow>
            )}
            {!isLoading && !data?.items.length && (
              <TableRow>
                <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                  暂无选题，点击「新增选题」开始
                </TableCell>
              </TableRow>
            )}
            {data?.items.map((topic) => (
              <TableRow
                key={topic.id}
                className="cursor-pointer hover:bg-muted/50"
                onClick={() => setSelectedTopic(topic)}
              >
                <TableCell className="font-medium max-w-[280px] truncate">{topic.title}</TableCell>
                <TableCell>
                  <span className="text-sm text-muted-foreground">
                    {SOURCE_LABELS[topic.source] ?? topic.source}
                  </span>
                </TableCell>
                <TableCell>
                  <ScoreBadge score={topic.compositeScore} />
                </TableCell>
                <TableCell>
                  <span
                    className={`px-2 py-0.5 rounded text-xs font-medium ${
                      TOPIC_STATUS_COLORS[topic.status] ?? "bg-gray-100 text-gray-700"
                    }`}
                  >
                    {TOPIC_STATUS_LABELS[topic.status] ?? topic.status}
                  </span>
                </TableCell>
                <TableCell>
                  <div className="flex gap-1 flex-wrap">
                    {topic.tags.slice(0, 3).map((tag) => (
                      <Badge key={tag} variant="secondary" className="text-xs">{tag}</Badge>
                    ))}
                    {topic.tags.length > 3 && (
                      <span className="text-xs text-muted-foreground">+{topic.tags.length - 3}</span>
                    )}
                  </div>
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {timeAgo(topic.createdAt)}
                </TableCell>
                <TableCell>
                  <div className="flex items-center justify-end gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={(e) => { e.stopPropagation(); setSelectedTopic(topic); }}
                    >
                      打分
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      className="text-muted-foreground hover:text-destructive"
                      aria-label={`删除选题：${topic.title}`}
                      title="删除选题"
                      disabled={deleteTopic.isPending}
                      onClick={(e) => { e.stopPropagation(); handleDelete(topic); }}
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

      <BrainstormDialog open={brainstormOpen} onClose={() => setBrainstormOpen(false)} />
      <CreateTopicDialog open={createOpen} onClose={() => setCreateOpen(false)} />
      <TopicSheet topic={selectedTopic} onClose={() => setSelectedTopic(null)} />
    </div>
  );
}
