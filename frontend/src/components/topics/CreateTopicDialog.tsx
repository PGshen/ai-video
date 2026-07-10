import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useCreateTopic } from "@/hooks/useTopics";
import { SOURCE_LABELS } from "@/lib/format";

interface Props {
  open: boolean;
  onClose: () => void;
}

export function CreateTopicDialog({ open, onClose }: Props) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [source, setSource] = useState("manual");
  const [tagsInput, setTagsInput] = useState("");
  const createTopic = useCreateTopic();

  const handleSubmit = () => {
    if (!title.trim()) return;
    const tags = tagsInput.split(",").map((t) => t.trim()).filter(Boolean);
    createTopic.mutate(
      { title: title.trim(), description: description.trim() || undefined, source, tags },
      {
        onSuccess: () => {
          setTitle(""); setDescription(""); setSource("manual"); setTagsInput("");
          onClose();
        },
      }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>新增选题</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div className="space-y-1.5">
            <Label>标题 *</Label>
            <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="选题标题" />
          </div>
          <div className="space-y-1.5">
            <Label>描述</Label>
            <Textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="选题描述（可选）" rows={3} />
          </div>
          <div className="space-y-1.5">
            <Label>来源</Label>
            <Select value={source} onValueChange={(v) => v && setSource(v)}>
              <SelectTrigger><SelectValue>{SOURCE_LABELS[source] ?? source}</SelectValue></SelectTrigger>
              <SelectContent>
                {Object.entries(SOURCE_LABELS).map(([value, label]) => (
                  <SelectItem key={value} value={value}>{label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>标签（逗号分隔）</Label>
            <Input value={tagsInput} onChange={(e) => setTagsInput(e.target.value)} placeholder="科学, 物理, 反直觉" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>取消</Button>
          <Button onClick={handleSubmit} disabled={!title.trim() || createTopic.isPending}>
            {createTopic.isPending ? "创建中..." : "创建"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
