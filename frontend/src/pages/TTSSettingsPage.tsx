import { useEffect, useMemo, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { AudioLines, KeyRound, Loader2, Pencil, Play, Plus, Save, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  useCreateTTSEngine, useCreateTTSVoice, useDeleteTTSEngine, useDeleteTTSVoice,
  usePreviewTTSVoice, useTTSSettings, useUpdateTTSEngine, useUpdateTTSVoice,
} from "@/hooks/useTTSSettings";
import type { TTSEngineInput, TTSVoiceInput } from "@/hooks/useTTSSettings";
import type { TTSEngineConfig, TTSVoice } from "@/types";

const defaultEndpoint = "https://openspeech.bytedance.com/api/v3/tts/unidirectional";
const emptyEngine: TTSEngineInput = {
  name: "", code: "", providerType: "volcengine", endpoint: defaultEndpoint,
  apiKey: "", resourceId: "seed-tts-2.0", timeoutSeconds: 60, isActive: true,
};
const emptyVoice: TTSVoiceInput = {
  engineId: "", name: "", speakerId: "", language: "zh-CN",
  gender: "", description: "", isActive: true,
};

function EngineDialog({ value, open, onClose }: { value: TTSEngineConfig | null; open: boolean; onClose: () => void }) {
  const create = useCreateTTSEngine();
  const update = useUpdateTTSEngine();
  const [form, setForm] = useState(emptyEngine);
  useEffect(() => setForm(value ? {
    name: value.name, code: value.code, providerType: value.providerType,
    endpoint: value.endpoint, apiKey: "", resourceId: value.resourceId,
    timeoutSeconds: value.timeoutSeconds, isActive: value.isActive,
  } : emptyEngine), [value, open]);
  const set = <K extends keyof TTSEngineInput>(key: K, next: TTSEngineInput[K]) => setForm((old) => ({ ...old, [key]: next }));
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!form.name.trim() || !form.code.trim() || !form.endpoint.trim() || !form.resourceId.trim()) return toast.error("请填写完整的引擎信息");
    if (!value && !form.apiKey?.trim()) return toast.error("新增引擎需要填写 API Key");
    const options = { onSuccess: () => { toast.success(value ? "引擎已更新" : "引擎已创建"); onClose(); }, onError: (e: Error) => toast.error(e.message) };
    const data = { ...form, name: form.name.trim(), code: form.code.trim(), endpoint: form.endpoint.trim(), resourceId: form.resourceId.trim(), apiKey: form.apiKey?.trim() };
    if (value) update.mutate({ id: value.id, ...data }, options);
    else create.mutate(data, options);
  };
  const pending = create.isPending || update.isPending;
  return <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
    <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl"><form onSubmit={submit} className="space-y-5">
      <DialogHeader><DialogTitle>{value ? "编辑 TTS 引擎" : "新增 TTS 引擎"}</DialogTitle><DialogDescription>引擎保存调用地址和鉴权信息，API Key 不会在页面回显。</DialogDescription></DialogHeader>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="显示名称"><Input value={form.name} onChange={(e) => set("name", e.target.value)} placeholder="例如 豆包 2.0" /></Field>
        <Field label="引擎编码"><Input value={form.code} onChange={(e) => set("code", e.target.value)} placeholder="例如 doubao_2.0" /></Field>
        <Field label="供应商类型"><Input value="volcengine" disabled /></Field>
        <Field label="资源 ID"><Input value={form.resourceId} onChange={(e) => set("resourceId", e.target.value)} /></Field>
        <div className="space-y-2 sm:col-span-2"><Label>接口地址</Label><Input value={form.endpoint} onChange={(e) => set("endpoint", e.target.value)} /></div>
        <Field label="API Key"><Input type="password" value={form.apiKey ?? ""} onChange={(e) => set("apiKey", e.target.value)} placeholder={value ? "留空保留当前密钥" : "必填"} /></Field>
        <Field label="超时秒数"><Input type="number" min={1} max={600} value={form.timeoutSeconds} onChange={(e) => set("timeoutSeconds", Number(e.target.value))} /></Field>
        <ActiveField checked={form.isActive} onChange={(v) => set("isActive", v)} text="可用于新项目和 TTS 生成" />
      </div>
      <DialogFooter><Button type="button" variant="outline" onClick={onClose}>取消</Button><Button type="submit" disabled={pending}>{pending ? <Loader2 className="animate-spin" /> : <Save />}保存</Button></DialogFooter>
    </form></DialogContent>
  </Dialog>;
}

function VoiceDialog({ value, engines, selectedEngineId, open, onClose }: { value: TTSVoice | null; engines: TTSEngineConfig[]; selectedEngineId: string; open: boolean; onClose: () => void }) {
  const create = useCreateTTSVoice();
  const update = useUpdateTTSVoice();
  const [form, setForm] = useState(emptyVoice);
  useEffect(() => setForm(value ? {
    engineId: value.engineId, name: value.name, speakerId: value.speakerId,
    language: value.language, gender: value.gender ?? "", description: value.description ?? "", isActive: value.isActive,
  } : { ...emptyVoice, engineId: selectedEngineId || engines[0]?.id || "" }), [value, open, engines, selectedEngineId]);
  const set = <K extends keyof TTSVoiceInput>(key: K, next: TTSVoiceInput[K]) => setForm((old) => ({ ...old, [key]: next }));
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!form.engineId || !form.name.trim() || !form.speakerId.trim()) return toast.error("请填写所属引擎、名称和 Speaker ID");
    const data = { ...form, name: form.name.trim(), speakerId: form.speakerId.trim(), language: form.language.trim(), gender: form.gender?.trim() || undefined, description: form.description?.trim() || undefined };
    const options = { onSuccess: () => { toast.success(value ? "音色已更新" : "音色已创建"); onClose(); }, onError: (e: Error) => toast.error(e.message) };
    if (value) update.mutate({ id: value.id, ...data }, options);
    else create.mutate(data, options);
  };
  const pending = create.isPending || update.isPending;
  return <Dialog open={open} onOpenChange={(v) => !v && onClose()}><DialogContent className="sm:max-w-2xl"><form onSubmit={submit} className="space-y-5">
    <DialogHeader><DialogTitle>{value ? "编辑音色" : "新增音色"}</DialogTitle><DialogDescription>音色必须归属于一个 TTS 引擎，Speaker ID 会直接传给供应商。</DialogDescription></DialogHeader>
    <div className="grid gap-4 sm:grid-cols-2">
      <div className="space-y-2"><Label>所属引擎</Label><select className="h-9 w-full rounded-md border bg-background px-3 text-sm" value={form.engineId} onChange={(e) => set("engineId", e.target.value)}>{engines.map((engine) => <option key={engine.id} value={engine.id}>{engine.name}</option>)}</select></div>
      <Field label="音色名称"><Input value={form.name} onChange={(e) => set("name", e.target.value)} placeholder="例如 清澈梓梓" /></Field>
      <Field label="Speaker ID"><Input value={form.speakerId} onChange={(e) => set("speakerId", e.target.value)} /></Field>
      <Field label="语言"><Input value={form.language} onChange={(e) => set("language", e.target.value)} /></Field>
      <div className="space-y-2"><Label>性别</Label><select className="h-9 w-full rounded-md border bg-background px-3 text-sm" value={form.gender ?? ""} onChange={(e) => set("gender", e.target.value)}><option value="">未设置</option><option value="female">女声</option><option value="male">男声</option><option value="neutral">中性</option></select></div>
      <div className="space-y-2 sm:col-span-2"><Label>说明</Label><Input value={form.description ?? ""} onChange={(e) => set("description", e.target.value)} placeholder="音色特点、适用场景等" /></div>
      <ActiveField checked={form.isActive} onChange={(v) => set("isActive", v)} text="可在创建项目时选择" />
    </div>
    <DialogFooter><Button type="button" variant="outline" onClick={onClose}>取消</Button><Button type="submit" disabled={pending}>{pending ? <Loader2 className="animate-spin" /> : <Save />}保存</Button></DialogFooter>
  </form></DialogContent></Dialog>;
}

function Field({ label, children }: { label: string; children: ReactNode }) { return <div className="space-y-2"><Label>{label}</Label>{children}</div>; }
function ActiveField({ checked, onChange, text }: { checked: boolean; onChange: (v: boolean) => void; text: string }) { return <div className="space-y-2"><Label>启用状态</Label><label className="flex h-9 items-center gap-2 rounded-md border px-3 text-sm"><input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />{text}</label></div>; }

export default function TTSSettingsPage() {
  const { data, isLoading, error } = useTTSSettings();
  const removeEngine = useDeleteTTSEngine();
  const removeVoice = useDeleteTTSVoice();
  const previewVoice = usePreviewTTSVoice();
  const [selectedEngineId, setSelectedEngineId] = useState("");
  const [previewText, setPreviewText] = useState("你好，这是一段音色试听文本。");
  const [previewVoiceId, setPreviewVoiceId] = useState("");
  const [audioUrl, setAudioUrl] = useState("");
  const [engineDialog, setEngineDialog] = useState<{ open: boolean; value: TTSEngineConfig | null }>({ open: false, value: null });
  const [voiceDialog, setVoiceDialog] = useState<{ open: boolean; value: TTSVoice | null }>({ open: false, value: null });
  const engines = useMemo(() => data?.engines ?? [], [data]);
  useEffect(() => { if (!selectedEngineId && engines[0]) setSelectedEngineId(engines[0].id); }, [engines, selectedEngineId]);
  useEffect(() => () => { if (audioUrl) URL.revokeObjectURL(audioUrl); }, [audioUrl]);
  const voices = useMemo(() => (data?.voices ?? []).filter((v) => !selectedEngineId || v.engineId === selectedEngineId), [data, selectedEngineId]);
  const selectedEngine = engines.find((engine) => engine.id === selectedEngineId);
  const deleteItem = (kind: "engine" | "voice", id: string, name: string) => {
    if (!window.confirm(`确认删除“${name}”？`)) return;
    const action = kind === "engine" ? removeEngine : removeVoice;
    action.mutate(id, { onSuccess: () => toast.success("已删除"), onError: (e: Error) => toast.error(e.message) });
  };

  const playPreview = (voice: TTSVoice) => {
    const text = previewText.trim();
    if (!text) {
      toast.error("请先填写试听文字");
      return;
    }
    setPreviewVoiceId(voice.id);
    previewVoice.mutate(
      { id: voice.id, text },
      {
        onSuccess: (blob) => {
          setAudioUrl(URL.createObjectURL(blob));
          toast.success(`已生成“${voice.name}”试听音频`);
        },
        onError: (previewError: Error) => toast.error(previewError.message),
      }
    );
  };

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-6 lg:p-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">TTS 音色管理</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          选择左侧引擎，在右侧维护音色并试听实际效果。
        </p>
      </div>

      {isLoading ? (
        <div className="flex h-40 items-center justify-center">
          <Loader2 className="animate-spin" />
        </div>
      ) : error ? (
        <p className="text-destructive">{(error as Error).message}</p>
      ) : (
        <div className="grid items-start gap-5 lg:grid-cols-[240px_minmax(0,1fr)]">
          <Card className="lg:sticky lg:top-6">
            <CardHeader className="flex flex-row items-center justify-between gap-2 px-4">
              <CardTitle className="flex items-center gap-2 text-base">
                <KeyRound className="size-4" />
                TTS 引擎
              </CardTitle>
              <Button
                size="icon"
                variant="outline"
                onClick={() => setEngineDialog({ open: true, value: null })}
                title="新增引擎"
              >
                <Plus />
              </Button>
            </CardHeader>
            <CardContent className="space-y-2 px-3">
              {engines.map((engine) => {
                const selected = engine.id === selectedEngineId;
                return (
                  <div
                    key={engine.id}
                    role="button"
                    tabIndex={0}
                    onClick={() => setSelectedEngineId(engine.id)}
                    onKeyDown={(event) => event.key === "Enter" && setSelectedEngineId(engine.id)}
                    className={`group cursor-pointer rounded-lg border p-3 transition-colors ${
                      selected ? "border-primary bg-primary/5 ring-1 ring-primary/20" : "hover:bg-muted/50"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <div className="truncate text-sm font-semibold">{engine.name}</div>
                        <div className="mt-1 truncate font-mono text-[11px] text-muted-foreground">
                          {engine.code}
                        </div>
                      </div>
                      <Badge variant={engine.isActive ? "default" : "secondary"}>
                        {engine.isActive ? "启用" : "停用"}
                      </Badge>
                    </div>
                    <div className="mt-3 flex items-center justify-between border-t pt-2">
                      <span className="truncate text-[11px] text-muted-foreground">
                        {engine.resourceId}
                      </span>
                      <div className="flex shrink-0">
                        <Button
                          size="icon"
                          variant="ghost"
                          onClick={(event) => {
                            event.stopPropagation();
                            setEngineDialog({ open: true, value: engine });
                          }}
                          title="编辑引擎"
                        >
                          <Pencil />
                        </Button>
                        <Button
                          size="icon"
                          variant="ghost"
                          onClick={(event) => {
                            event.stopPropagation();
                            deleteItem("engine", engine.id, engine.name);
                          }}
                          title="删除引擎"
                        >
                          <Trash2 />
                        </Button>
                      </div>
                    </div>
                  </div>
                );
              })}
              {!engines.length && (
                <div className="py-8 text-center text-sm text-muted-foreground">暂无 TTS 引擎</div>
              )}
            </CardContent>
          </Card>

          <Card className="min-w-0">
            <CardHeader className="flex flex-row items-start justify-between gap-4">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <AudioLines className="size-5" />
                  音色
                </CardTitle>
                <p className="mt-1 text-sm text-muted-foreground">
                  {selectedEngine ? `${selectedEngine.name} 下的音色` : "请先选择引擎"}
                </p>
              </div>
              <Button
                disabled={!selectedEngine}
                onClick={() => setVoiceDialog({ open: true, value: null })}
              >
                <Plus />
                新增音色
              </Button>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="rounded-lg border bg-muted/20 p-3">
                <div className="flex flex-col gap-2 sm:flex-row">
                  <Input
                    value={previewText}
                    onChange={(event) => setPreviewText(event.target.value)}
                    maxLength={500}
                    placeholder="输入试听文字，然后点击某个音色的试听按钮"
                  />
                  <span className="self-center text-xs text-muted-foreground">
                    {previewText.length}/500
                  </span>
                </div>
                {audioUrl && (
                  <audio className="mt-3 h-10 w-full" controls autoPlay src={audioUrl}>
                    <track kind="captions" />
                  </audio>
                )}
              </div>

              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>名称</TableHead>
                    <TableHead>Speaker ID</TableHead>
                    <TableHead>语言 / 性别</TableHead>
                    <TableHead>状态</TableHead>
                    <TableHead className="text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {voices.map((voice) => (
                    <TableRow key={voice.id}>
                      <TableCell>
                        <div className="font-medium">{voice.name}</div>
                        {voice.description && (
                          <div className="max-w-64 truncate text-xs text-muted-foreground">
                            {voice.description}
                          </div>
                        )}
                      </TableCell>
                      <TableCell className="max-w-72 truncate font-mono text-xs">
                        {voice.speakerId}
                      </TableCell>
                      <TableCell>
                        {voice.language} · {voice.gender === "female" ? "女声" : voice.gender === "male" ? "男声" : voice.gender || "未设置"}
                      </TableCell>
                      <TableCell>
                        <Badge variant={voice.isActive ? "default" : "secondary"}>
                          {voice.isActive ? "启用" : "停用"}
                        </Badge>
                      </TableCell>
                      <TableCell className="space-x-1 text-right">
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={previewVoice.isPending && previewVoiceId === voice.id}
                          onClick={() => playPreview(voice)}
                        >
                          {previewVoice.isPending && previewVoiceId === voice.id ? (
                            <Loader2 className="animate-spin" />
                          ) : (
                            <Play />
                          )}
                          试听
                        </Button>
                        <Button
                          size="icon"
                          variant="ghost"
                          onClick={() => setVoiceDialog({ open: true, value: voice })}
                          title="编辑音色"
                        >
                          <Pencil />
                        </Button>
                        <Button
                          size="icon"
                          variant="ghost"
                          onClick={() => deleteItem("voice", voice.id, voice.name)}
                          title="删除音色"
                        >
                          <Trash2 />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                  {!voices.length && (
                    <TableRow>
                      <TableCell colSpan={5} className="h-24 text-center text-muted-foreground">
                        当前引擎下暂无音色
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </div>
      )}

      <EngineDialog
        value={engineDialog.value}
        open={engineDialog.open}
        onClose={() => setEngineDialog({ open: false, value: null })}
      />
      <VoiceDialog
        value={voiceDialog.value}
        engines={engines}
        selectedEngineId={selectedEngineId}
        open={voiceDialog.open}
        onClose={() => setVoiceDialog({ open: false, value: null })}
      />
    </div>
  );
}
