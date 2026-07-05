import { useState } from "react";
import { Activity, Clock3, Coins, Loader2, Search, Sigma } from "lucide-react";

import { ListPagination } from "@/components/ListPagination";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useAICallRecord, useAICallRecords } from "@/hooks/useAICallRecords";
import type { AICallRecord, AICallStatus } from "@/types";

const PAGE_SIZE = 20;

const statusLabels: Record<AICallStatus, string> = {
  pending: "进行中",
  succeeded: "成功",
  failed: "失败",
  timeout: "超时",
  cancelled: "已取消",
};

const businessLabels: Record<string, string> = {
  narrative_generation: "叙事生成",
  code_generation: "代码生成",
  code_repair: "代码修复",
  topic_brainstorm: "选题脑暴",
  topic_research: "选题研究",
  style_assistant: "风格助手",
  unknown: "未标记",
};

function statusVariant(status: AICallStatus) {
  if (status === "succeeded") return "default" as const;
  if (status === "pending") return "secondary" as const;
  return "destructive" as const;
}

function money(value: string | null | undefined, currency = "USD") {
  if (value == null) return "—";
  return `${currency === "USD" ? "$" : `${currency} `}${Number(value).toFixed(6)}`;
}

function duration(value: number | null) {
  if (value == null) return "—";
  return value < 1000 ? `${value} ms` : `${(value / 1000).toFixed(2)} s`;
}

function JsonBlock({ value }: { value: unknown }) {
  return (
    <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-all rounded-md border bg-muted/40 p-3 text-xs leading-5">
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}

function RecordDialog({
  record,
  onClose,
}: {
  record: AICallRecord | null;
  onClose: () => void;
}) {
  const detail = useAICallRecord(record?.id ?? null);

  return (
    <Dialog open={Boolean(record)} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-4xl">
        <DialogHeader>
          <DialogTitle>AI 调用详情</DialogTitle>
          <DialogDescription>
            {record && businessLabels[record.business]} · {record?.provider} · {record?.model} · {record?.id}
          </DialogDescription>
        </DialogHeader>
        {detail.isLoading && (
          <div className="flex justify-center py-12">
            <Loader2 className="animate-spin" />
          </div>
        )}
        {detail.data && (
          <div className="grid gap-5">
            <div className="grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
              <div><span className="text-muted-foreground">状态</span><p>{statusLabels[detail.data.status]}</p></div>
              <div><span className="text-muted-foreground">耗时</span><p>{duration(detail.data.durationMs)}</p></div>
              <div><span className="text-muted-foreground">Token</span><p>{detail.data.totalTokens?.toLocaleString() ?? "—"}</p></div>
              <div><span className="text-muted-foreground">费用</span><p>{money(detail.data.totalCost, detail.data.currency)}</p></div>
            </div>
            <section>
              <h3 className="mb-2 text-sm font-semibold">输入 / Prompt</h3>
              <JsonBlock value={detail.data.input} />
            </section>
            <section>
              <h3 className="mb-2 text-sm font-semibold">模型输出</h3>
              <pre className="max-h-96 overflow-auto whitespace-pre-wrap break-words rounded-md border bg-muted/40 p-3 text-xs leading-5">
                {detail.data.output || "（无输出）"}
              </pre>
            </section>
            <section>
              <h3 className="mb-2 text-sm font-semibold">Token 与费用原始明细</h3>
              <JsonBlock value={detail.data.usage ?? {}} />
            </section>
            {detail.data.errorMessage && (
              <section>
                <h3 className="mb-2 text-sm font-semibold text-destructive">异常</h3>
                <pre className="whitespace-pre-wrap rounded-md border border-destructive/30 bg-destructive/5 p-3 text-xs text-destructive">
                  {detail.data.errorType}: {detail.data.errorMessage}
                </pre>
              </section>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default function AICallRecordsPage() {
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");
  const [provider, setProvider] = useState("");
  const [business, setBusiness] = useState("");
  const [modelInput, setModelInput] = useState("");
  const [model, setModel] = useState("");
  const [selected, setSelected] = useState<AICallRecord | null>(null);
  const records = useAICallRecords({
    page,
    pageSize: PAGE_SIZE,
    status,
    provider,
    business,
    model,
  });
  const summary = records.data?.summary;

  const applyModel = () => {
    setModel(modelInput.trim());
    setPage(1);
  };

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold">AI 调用记录</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          检查模型输入输出、Token 消耗、费用、耗时与异常。
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[
          { title: "调用次数", value: summary?.calls.toLocaleString() ?? "—", icon: Activity },
          { title: "Token 总量", value: summary?.totalTokens.toLocaleString() ?? "—", icon: Sigma },
          { title: "总费用", value: money(summary?.totalCost), icon: Coins },
          { title: "平均耗时", value: duration(summary?.averageDurationMs ?? null), icon: Clock3 },
        ].map(({ title, value, icon: Icon }) => (
          <Card key={title}>
            <CardHeader className="flex flex-row items-center justify-between pb-1">
              <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
              <Icon className="size-4 text-muted-foreground" />
            </CardHeader>
            <CardContent className="text-2xl font-semibold">{value}</CardContent>
          </Card>
        ))}
      </div>

      <div className="flex flex-wrap gap-3">
        <select
          className="h-9 rounded-md border bg-background px-3 text-sm"
          value={business}
          onChange={(event) => { setBusiness(event.target.value); setPage(1); }}
          aria-label="按业务筛选"
        >
          <option value="">全部业务</option>
          {Object.entries(businessLabels).map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
        <select
          className="h-9 rounded-md border bg-background px-3 text-sm"
          value={status}
          onChange={(event) => { setStatus(event.target.value); setPage(1); }}
          aria-label="按状态筛选"
        >
          <option value="">全部状态</option>
          {Object.entries(statusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        <select
          className="h-9 rounded-md border bg-background px-3 text-sm"
          value={provider}
          onChange={(event) => { setProvider(event.target.value); setPage(1); }}
          aria-label="按提供商筛选"
        >
          <option value="">全部提供商</option>
          <option value="deepseek">DeepSeek</option>
          <option value="openrouter">OpenRouter</option>
          <option value="gemini">Gemini</option>
        </select>
        <div className="flex min-w-64 gap-2">
          <Input
            value={modelInput}
            onChange={(event) => setModelInput(event.target.value)}
            onKeyDown={(event) => event.key === "Enter" && applyModel()}
            placeholder="搜索模型名称"
          />
          <Button variant="outline" onClick={applyModel}><Search /></Button>
        </div>
      </div>

      <div className="overflow-hidden rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>时间</TableHead>
              <TableHead>业务</TableHead>
              <TableHead>模型</TableHead>
              <TableHead>状态</TableHead>
              <TableHead className="text-right">Token</TableHead>
              <TableHead className="text-right">缓存 / 推理</TableHead>
              <TableHead className="text-right">费用</TableHead>
              <TableHead className="text-right">耗时</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {records.isLoading && (
              <TableRow><TableCell colSpan={8} className="h-32 text-center"><Loader2 className="mx-auto animate-spin" /></TableCell></TableRow>
            )}
            {records.data?.items.map((record) => (
              <TableRow key={record.id} className="cursor-pointer" onClick={() => setSelected(record)}>
                <TableCell className="whitespace-nowrap text-xs">{new Date(record.startedAt).toLocaleString()}</TableCell>
                <TableCell className="whitespace-nowrap font-medium">{businessLabels[record.business] ?? record.business}</TableCell>
                <TableCell><p className="font-medium">{record.model}</p><p className="text-xs text-muted-foreground">{record.provider} · {record.requestType}</p></TableCell>
                <TableCell><Badge variant={statusVariant(record.status)}>{statusLabels[record.status]}</Badge>{record.errorType && <p className="mt-1 text-xs text-destructive">{record.errorType}</p>}</TableCell>
                <TableCell className="text-right tabular-nums">{record.totalTokens?.toLocaleString() ?? "—"}<p className="text-xs text-muted-foreground">{record.promptTokens ?? "—"} / {record.completionTokens ?? "—"}</p></TableCell>
                <TableCell className="text-right text-xs tabular-nums">{record.cachedTokens ?? "—"} / {record.reasoningTokens ?? "—"}</TableCell>
                <TableCell className="text-right tabular-nums">{money(record.totalCost, record.currency)}</TableCell>
                <TableCell className="text-right tabular-nums">{duration(record.durationMs)}</TableCell>
              </TableRow>
            ))}
            {!records.isLoading && records.data?.items.length === 0 && (
              <TableRow><TableCell colSpan={8} className="h-32 text-center text-muted-foreground">暂无调用记录</TableCell></TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <ListPagination page={page} pageSize={PAGE_SIZE} total={records.data?.total ?? 0} onPageChange={setPage} />
      <RecordDialog record={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
