import { useMemo, useState } from "react";
import { Check, Loader2, Plus, RotateCcw, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { useBrainstormTopics, useImportBrainstormCandidates } from "@/hooks/useTopics";
import type { BrainstormCandidate } from "@/types";

interface Props {
  open: boolean;
  onClose: () => void;
}

function normalizeCount(value: string) {
  const parsed = Number.parseInt(value, 10);
  if (Number.isNaN(parsed)) return 5;
  return Math.min(Math.max(parsed, 1), 20);
}

export function BrainstormDialog({ open, onClose }: Props) {
  const [topicDirection, setTopicDirection] = useState("");
  const [count, setCount] = useState(5);
  const [candidates, setCandidates] = useState<BrainstormCandidate[]>([]);
  const [selectedIndexes, setSelectedIndexes] = useState<Set<number>>(new Set());
  const [error, setError] = useState<string | null>(null);

  const brainstorm = useBrainstormTopics();
  const importCandidates = useImportBrainstormCandidates();

  const selectedCandidates = useMemo(
    () => candidates.filter((_, index) => selectedIndexes.has(index)),
    [candidates, selectedIndexes]
  );

  const isGenerating = brainstorm.isPending;
  const isImporting = importCandidates.isPending;
  const hasCandidates = candidates.length > 0;
  const allSelected = hasCandidates && selectedIndexes.size === candidates.length;

  const resetResults = () => {
    setCandidates([]);
    setSelectedIndexes(new Set());
    setError(null);
  };

  const handleGenerate = () => {
    if (!topicDirection.trim()) return;
    resetResults();
    brainstorm.mutate(
      { topicDirection: topicDirection.trim(), count },
      {
        onSuccess: (data) => {
          const items = data.candidates ?? [];
          setCandidates(items);
          setSelectedIndexes(new Set(items.map((_, index) => index)));
        },
        onError: () => setError("AI 生成失败，请稍后重试"),
      }
    );
  };

  const handleToggle = (index: number) => {
    setSelectedIndexes((prev) => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  };

  const handleToggleAll = () => {
    if (allSelected) {
      setSelectedIndexes(new Set());
    } else {
      setSelectedIndexes(new Set(candidates.map((_, index) => index)));
    }
  };

  const handleImport = () => {
    if (selectedCandidates.length === 0) return;
    setError(null);
    importCandidates.mutate(selectedCandidates, {
      onSuccess: () => {
        setTopicDirection("");
        setCount(5);
        resetResults();
        onClose();
      },
      onError: () => setError("候选选题入库失败，请稍后重试"),
    });
  };

  const handleClose = () => {
    if (isGenerating || isImporting) return;
    onClose();
  };

  return (
    <Dialog open={open} onOpenChange={(nextOpen) => !nextOpen && handleClose()}>
      <DialogContent className="sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="size-4" />
            AI 批量产出候选选题
          </DialogTitle>
          <DialogDescription>
            输入主题方向后生成候选，确认勾选后加入选题池。
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="grid gap-3 sm:grid-cols-[1fr_120px_auto] sm:items-end">
            <div className="space-y-1.5">
              <Label>主题方向 *</Label>
              <Input
                value={topicDirection}
                onChange={(event) => setTopicDirection(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") handleGenerate();
                }}
                placeholder="例如：生活中的反直觉物理"
              />
            </div>
            <div className="space-y-1.5">
              <Label>数量</Label>
              <Input
                type="number"
                min={1}
                max={20}
                value={count}
                onChange={(event) => setCount(normalizeCount(event.target.value))}
              />
            </div>
            <Button
              onClick={handleGenerate}
              disabled={!topicDirection.trim() || isGenerating || isImporting}
              className="sm:self-end"
            >
              {isGenerating ? <Loader2 className="animate-spin" /> : <Sparkles />}
              {hasCandidates ? "重新生成" : "生成候选"}
            </Button>
          </div>

          {error && (
            <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}
            </div>
          )}

          <div className="min-h-[280px] rounded-md border">
            <div className="flex h-10 items-center justify-between border-b px-3">
              <div className="text-sm font-medium">候选列表</div>
              {hasCandidates && (
                <Button variant="ghost" size="sm" onClick={handleToggleAll} disabled={isImporting}>
                  <Check />
                  {allSelected ? "取消全选" : "全选"}
                </Button>
              )}
            </div>

            {!hasCandidates && (
              <div className="flex h-[238px] items-center justify-center text-sm text-muted-foreground">
                {isGenerating ? "生成中..." : "暂无候选"}
              </div>
            )}

            {hasCandidates && (
              <div className="max-h-[420px] overflow-y-auto">
                {candidates.map((candidate, index) => (
                  <label
                    key={`${candidate.title}-${index}`}
                    className="grid cursor-pointer grid-cols-[24px_1fr] gap-3 border-b px-3 py-3 last:border-b-0 hover:bg-muted/50"
                  >
                    <input
                      type="checkbox"
                      checked={selectedIndexes.has(index)}
                      disabled={isImporting}
                      onChange={() => handleToggle(index)}
                      className="mt-1 size-4 accent-foreground"
                    />
                    <span className="space-y-2">
                      <span className="block font-medium leading-snug">{candidate.title}</span>
                      {candidate.description && (
                        <span className="block text-sm leading-6 text-muted-foreground">
                          {candidate.description}
                        </span>
                      )}
                      {!!candidate.tags?.length && (
                        <span className="flex flex-wrap gap-1">
                          {candidate.tags.map((tag) => (
                            <Badge key={tag} variant="secondary" className="text-xs">
                              {tag}
                            </Badge>
                          ))}
                        </span>
                      )}
                    </span>
                  </label>
                ))}
              </div>
            )}
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={handleClose} disabled={isGenerating || isImporting}>
            取消
          </Button>
          {hasCandidates && (
            <Button variant="outline" onClick={handleGenerate} disabled={isGenerating || isImporting}>
              {isGenerating ? <Loader2 className="animate-spin" /> : <RotateCcw />}
              重新生成
            </Button>
          )}
          <Button onClick={handleImport} disabled={selectedCandidates.length === 0 || isImporting || isGenerating}>
            {isImporting ? <Loader2 className="animate-spin" /> : <Plus />}
            加入选题池
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
