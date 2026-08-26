import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import {
  CheckCircle2,
  Cpu,
  KeyRound,
  Loader2,
  Pencil,
  PlugZap,
  Plus,
  Save,
  Trash2,
  XCircle,
  Zap,
} from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  useAIModelSettings,
  useCreateAIModelProvider,
  useCreateAIProviderModel,
  useDeleteAIBusinessModelConfig,
  useDeleteAIModelProvider,
  useDeleteAIProviderModel,
  useSetAIBusinessModelConfig,
  useTestAIProviderModel,
  useUpdateAIModelProvider,
  useUpdateAIProviderModel,
} from "@/hooks/useAIModelSettings";
import type {
  AIModelProviderInput,
  AIProviderModelInput,
} from "@/hooks/useAIModelSettings";
import type {
  AIModelProvider,
  AIModelTestResponse,
  AIProviderModel,
  AIProviderType,
} from "@/types";

const providerLabels: Record<AIProviderType, string> = {
  deepseek: "DeepSeek",
  openrouter: "OpenRouter",
  gemini: "Gemini",
  doubao: "Doubao",
  anthropic: "Anthropic",
};

const defaultBaseUrls: Record<AIProviderType, string> = {
  deepseek: "https://api.deepseek.com",
  openrouter: "https://openrouter.ai/api/v1",
  gemini: "https://generativelanguage.googleapis.com/v1beta/openai",
  doubao: "https://ark.cn-beijing.volces.com/api/v3",
  // 留空表示走 Anthropic 官方端点；填值则走中转
  anthropic: "",
};

const emptyProviderForm: AIModelProviderInput = {
  name: "",
  providerType: "deepseek",
  baseUrl: defaultBaseUrls.deepseek,
  apiKey: "",
  timeoutSeconds: 600,
  siteUrl: "",
  siteName: "",
  isActive: true,
};

const emptyModelForm: AIProviderModelInput = {
  providerId: "",
  name: "",
  model: "",
  contentMaxTokens: 100000,
  jsonMaxTokens: 100000,
  inputCostPerMillion: "0",
  cachedInputCostPerMillion: "0",
  outputCostPerMillion: "0",
  isActive: true,
};

type SettingsTab = "providers" | "models" | "business";

const settingsTabs: Array<{
  key: SettingsTab;
  label: string;
  icon: typeof PlugZap;
}> = [
  { key: "providers", label: "供应商", icon: PlugZap },
  { key: "models", label: "模型", icon: Cpu },
  { key: "business", label: "业务绑定", icon: CheckCircle2 },
];

function toProviderForm(provider: AIModelProvider): AIModelProviderInput {
  return {
    name: provider.name,
    providerType: provider.providerType,
    baseUrl: provider.baseUrl,
    apiKey: "",
    timeoutSeconds: provider.timeoutSeconds,
    siteUrl: provider.siteUrl ?? "",
    siteName: provider.siteName ?? "",
    isActive: provider.isActive,
  };
}

function toModelForm(model: AIProviderModel): AIProviderModelInput {
  return {
    providerId: model.providerId,
    name: model.name,
    model: model.model,
    contentMaxTokens: model.contentMaxTokens,
    jsonMaxTokens: model.jsonMaxTokens,
    inputCostPerMillion: model.inputCostPerMillion,
    cachedInputCostPerMillion: model.cachedInputCostPerMillion,
    outputCostPerMillion: model.outputCostPerMillion,
    isActive: model.isActive,
  };
}

function showTestResult(result: AIModelTestResponse) {
  if (result.ok) {
    toast.success(
      `模型可用${result.latencyMs != null ? ` · ${result.latencyMs}ms` : ""}`
    );
  } else {
    toast.error(result.message || "模型不可用");
  }
}

function ProviderDialog({
  provider,
  open,
  onClose,
}: {
  provider: AIModelProvider | null;
  open: boolean;
  onClose: () => void;
}) {
  const createProvider = useCreateAIModelProvider();
  const updateProvider = useUpdateAIModelProvider();
  const [form, setForm] = useState<AIModelProviderInput>(emptyProviderForm);
  const isEditing = Boolean(provider);
  const pending = createProvider.isPending || updateProvider.isPending;

  useEffect(() => {
    setForm(provider ? toProviderForm(provider) : emptyProviderForm);
  }, [provider, open]);

  const setField = <K extends keyof AIModelProviderInput>(
    key: K,
    value: AIModelProviderInput[K]
  ) => setForm((current) => ({ ...current, [key]: value }));

  const changeProviderType = (value: AIProviderType) => {
    setForm((current) => ({
      ...current,
      providerType: value,
      baseUrl:
        current.baseUrl === defaultBaseUrls[current.providerType]
          ? defaultBaseUrls[value]
          : current.baseUrl,
    }));
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    // Anthropic 的 Base URL 可留空，表示走官方端点
    const baseUrlRequired = form.providerType !== "anthropic";
    if (!form.name.trim() || (baseUrlRequired && !form.baseUrl.trim())) {
      toast.error("请填写供应商名称和 Base URL");
      return;
    }
    if (!isEditing && !form.apiKey?.trim()) {
      toast.error("新增供应商需要填写 API Key");
      return;
    }
    const payload: AIModelProviderInput = {
      ...form,
      name: form.name.trim(),
      baseUrl: form.baseUrl.trim(),
      apiKey: form.apiKey?.trim(),
      siteUrl: form.siteUrl?.trim() || undefined,
      siteName: form.siteName?.trim() || undefined,
    };
    const options = {
      onSuccess: () => {
        toast.success(isEditing ? "供应商已更新" : "供应商已创建");
        onClose();
      },
      onError: (error: Error) => toast.error(error.message || "保存失败"),
    };
    if (isEditing && provider) {
      updateProvider.mutate({ id: provider.id, ...payload }, options);
    } else {
      createProvider.mutate(payload, options);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(nextOpen) => !nextOpen && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <form onSubmit={submit} className="space-y-5">
          <DialogHeader>
            <DialogTitle>{isEditing ? "编辑供应商" : "新增供应商"}</DialogTitle>
            <DialogDescription>
              供应商保存 Base URL、API Key 和通用请求参数；具体模型在下一层维护。
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label>供应商名称</Label>
              <Input
                value={form.name}
                onChange={(event) => setField("name", event.target.value)}
                placeholder="例如 DeepSeek 官方"
              />
            </div>
            <div className="space-y-2">
              <Label>供应商类型</Label>
              <select
                className="h-9 w-full rounded-md border bg-background px-3 text-sm"
                value={form.providerType}
                onChange={(event) =>
                  changeProviderType(event.target.value as AIProviderType)
                }
              >
                {Object.entries(providerLabels).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-2 md:col-span-2">
              <Label>Base URL</Label>
              <Input
                value={form.baseUrl}
                onChange={(event) => setField("baseUrl", event.target.value)}
                placeholder={
                  form.providerType === "anthropic"
                    ? "留空走 Anthropic 官方端点，填值走中转"
                    : undefined
                }
              />
            </div>
            <div className="space-y-2">
              <Label>API Key</Label>
              <Input
                value={form.apiKey ?? ""}
                onChange={(event) => setField("apiKey", event.target.value)}
                type="password"
                placeholder={isEditing ? "留空保留当前密钥" : "必填"}
              />
            </div>
            <div className="space-y-2">
              <Label>超时秒数</Label>
              <Input
                value={form.timeoutSeconds}
                onChange={(event) =>
                  setField("timeoutSeconds", Number(event.target.value))
                }
                type="number"
                min={1}
              />
            </div>
            <div className="space-y-2">
              <Label>启用状态</Label>
              <label className="flex h-9 items-center gap-2 rounded-md border px-3 text-sm">
                <input
                  checked={form.isActive}
                  onChange={(event) => setField("isActive", event.target.checked)}
                  type="checkbox"
                />
                可用于模型调用
              </label>
            </div>
            {form.providerType === "openrouter" && (
              <>
                <div className="space-y-2">
                  <Label>站点 URL</Label>
                  <Input
                    value={form.siteUrl ?? ""}
                    onChange={(event) => setField("siteUrl", event.target.value)}
                    placeholder="可选"
                  />
                </div>
                <div className="space-y-2">
                  <Label>站点名称</Label>
                  <Input
                    value={form.siteName ?? ""}
                    onChange={(event) => setField("siteName", event.target.value)}
                    placeholder="可选"
                  />
                </div>
              </>
            )}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>
              取消
            </Button>
            <Button type="submit" disabled={pending}>
              {pending ? <Loader2 className="animate-spin" /> : <Save />}
              保存
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function ModelDialog({
  model,
  providers,
  open,
  onClose,
}: {
  model: AIProviderModel | null;
  providers: AIModelProvider[];
  open: boolean;
  onClose: () => void;
}) {
  const createModel = useCreateAIProviderModel();
  const updateModel = useUpdateAIProviderModel();
  const testModel = useTestAIProviderModel();
  const [form, setForm] = useState<AIProviderModelInput>(emptyModelForm);
  const isEditing = Boolean(model);
  const pending = createModel.isPending || updateModel.isPending;

  useEffect(() => {
    setForm(
      model
        ? toModelForm(model)
        : { ...emptyModelForm, providerId: providers[0]?.id ?? "" }
    );
  }, [model, open, providers]);

  const setField = <K extends keyof AIProviderModelInput>(
    key: K,
    value: AIProviderModelInput[K]
  ) => setForm((current) => ({ ...current, [key]: value }));

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!form.providerId || !form.name.trim() || !form.model.trim()) {
      toast.error("请填写供应商、模型名称和模型 ID");
      return;
    }
    const payload: AIProviderModelInput = {
      ...form,
      name: form.name.trim(),
      model: form.model.trim(),
    };
    const options = {
      onSuccess: () => {
        toast.success(isEditing ? "模型已更新" : "模型已创建");
        onClose();
      },
      onError: (error: Error) => toast.error(error.message || "保存失败"),
    };
    if (isEditing && model) {
      updateModel.mutate({ id: model.id, ...payload }, options);
    } else {
      createModel.mutate(payload, options);
    }
  };

  const runTest = () => {
    if (!form.providerId || !form.model.trim()) {
      toast.error("请先选择供应商并填写模型 ID");
      return;
    }
    testModel.mutate(
      { providerId: form.providerId, model: form.model.trim() },
      {
        onSuccess: showTestResult,
        onError: (error: Error) => toast.error(error.message || "测试请求失败"),
      }
    );
  };

  return (
    <Dialog open={open} onOpenChange={(nextOpen) => !nextOpen && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-3xl">
        <form onSubmit={submit} className="space-y-5">
          <DialogHeader>
            <DialogTitle>{isEditing ? "编辑模型" : "新增模型"}</DialogTitle>
            <DialogDescription>
              模型保存具体 model ID、结构化输出 token 上限与费用估算。
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label>所属供应商</Label>
              <select
                className="h-9 w-full rounded-md border bg-background px-3 text-sm"
                value={form.providerId}
                onChange={(event) => setField("providerId", event.target.value)}
              >
                <option value="">请选择供应商</option>
                {providers.map((provider) => (
                  <option key={provider.id} value={provider.id}>
                    {provider.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <Label>模型显示名</Label>
              <Input
                value={form.name}
                onChange={(event) => setField("name", event.target.value)}
                placeholder="例如 DeepSeek Flash"
              />
            </div>
            <div className="space-y-2 md:col-span-2">
              <Label>模型 ID</Label>
              <Input
                value={form.model}
                onChange={(event) => setField("model", event.target.value)}
                placeholder="deepseek-v4-flash"
              />
            </div>
            <div className="space-y-2">
              <Label>内容 max tokens</Label>
              <Input
                value={form.contentMaxTokens}
                onChange={(event) =>
                  setField("contentMaxTokens", Number(event.target.value))
                }
                type="number"
                min={1}
              />
            </div>
            <div className="space-y-2">
              <Label>JSON max tokens</Label>
              <Input
                value={form.jsonMaxTokens}
                onChange={(event) =>
                  setField("jsonMaxTokens", Number(event.target.value))
                }
                type="number"
                min={1}
              />
            </div>
            <div className="space-y-2">
              <Label>输入成本 / 百万 token</Label>
              <Input
                value={form.inputCostPerMillion}
                onChange={(event) =>
                  setField("inputCostPerMillion", event.target.value)
                }
                type="number"
                min={0}
                step="0.000001"
              />
            </div>
            <div className="space-y-2">
              <Label>缓存输入成本 / 百万 token</Label>
              <Input
                value={form.cachedInputCostPerMillion}
                onChange={(event) =>
                  setField("cachedInputCostPerMillion", event.target.value)
                }
                type="number"
                min={0}
                step="0.000001"
              />
            </div>
            <div className="space-y-2">
              <Label>输出成本 / 百万 token</Label>
              <Input
                value={form.outputCostPerMillion}
                onChange={(event) =>
                  setField("outputCostPerMillion", event.target.value)
                }
                type="number"
                min={0}
                step="0.000001"
              />
            </div>
            <div className="space-y-2">
              <Label>启用状态</Label>
              <label className="flex h-9 items-center gap-2 rounded-md border px-3 text-sm">
                <input
                  checked={form.isActive}
                  onChange={(event) => setField("isActive", event.target.checked)}
                  type="checkbox"
                />
                可被业务配置选择
              </label>
            </div>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              className="sm:mr-auto"
              onClick={runTest}
              disabled={testModel.isPending}
            >
              {testModel.isPending ? <Loader2 className="animate-spin" /> : <Zap />}
              测试连通
            </Button>
            <Button type="button" variant="outline" onClick={onClose}>
              取消
            </Button>
            <Button type="submit" disabled={pending}>
              {pending ? <Loader2 className="animate-spin" /> : <Save />}
              保存
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default function AIModelSettingsPage() {
  const settings = useAIModelSettings();
  const deleteProvider = useDeleteAIModelProvider();
  const deleteModel = useDeleteAIProviderModel();
  const setBusinessConfig = useSetAIBusinessModelConfig();
  const deleteBusinessConfig = useDeleteAIBusinessModelConfig();
  const testModel = useTestAIProviderModel();
  const [testingModelId, setTestingModelId] = useState<string | null>(null);
  const [providerDialogOpen, setProviderDialogOpen] = useState(false);
  const [modelDialogOpen, setModelDialogOpen] = useState(false);
  const [editingProvider, setEditingProvider] = useState<AIModelProvider | null>(null);
  const [editingModel, setEditingModel] = useState<AIProviderModel | null>(null);
  const [activeTab, setActiveTab] = useState<SettingsTab>("providers");

  const providerMap = useMemo(() => {
    return new Map(settings.data?.providers.map((provider) => [provider.id, provider]));
  }, [settings.data?.providers]);

  const modelMap = useMemo(() => {
    return new Map(settings.data?.models.map((model) => [model.id, model]));
  }, [settings.data?.models]);

  const configMap = useMemo(() => {
    return new Map(
      settings.data?.businessConfigs.map((config) => [config.business, config])
    );
  }, [settings.data?.businessConfigs]);

  const removeProvider = (provider: AIModelProvider) => {
    if (!confirm(`确认删除供应商「${provider.name}」？`)) return;
    deleteProvider.mutate(provider.id, {
      onSuccess: () => toast.success("供应商已删除"),
      onError: (error) => toast.error(error.message || "删除失败"),
    });
  };

  const runModelTest = (model: AIProviderModel) => {
    setTestingModelId(model.id);
    testModel.mutate(
      { providerId: model.providerId, model: model.model },
      {
        onSuccess: showTestResult,
        onError: (error) => toast.error(error.message || "测试请求失败"),
        onSettled: () => setTestingModelId(null),
      }
    );
  };

  const removeModel = (model: AIProviderModel) => {
    if (!confirm(`确认删除模型「${model.name}」？`)) return;
    deleteModel.mutate(model.id, {
      onSuccess: () => toast.success("模型已删除"),
      onError: (error) => toast.error(error.message || "删除失败"),
    });
  };

  const updateBusiness = (business: string, modelId: string) => {
    if (!modelId) {
      deleteBusinessConfig.mutate(business, {
        onSuccess: () => toast.success("已恢复为默认 fallback"),
        onError: (error) => toast.error(error.message || "更新失败"),
      });
      return;
    }
    setBusinessConfig.mutate(
      { business, modelId },
      {
        onSuccess: () => toast.success("业务模型配置已更新"),
        onError: (error) => toast.error(error.message || "更新失败"),
      }
    );
  };

  return (
    <div className="space-y-6 p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">模型配置</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            先维护供应商连接，再为供应商添加模型，最后按业务绑定具体模型。
          </p>
        </div>
        <div className="flex gap-2">
          {activeTab === "providers" && (
            <Button
              onClick={() => {
                setEditingProvider(null);
                setProviderDialogOpen(true);
              }}
            >
              <PlugZap />
              新增供应商
            </Button>
          )}
          {activeTab === "models" && (
            <Button
              onClick={() => {
                setEditingModel(null);
                setModelDialogOpen(true);
              }}
            >
              <Plus />
              新增模型
            </Button>
          )}
        </div>
      </div>

      {settings.isLoading && (
        <div className="flex h-40 items-center justify-center">
          <Loader2 className="animate-spin" />
        </div>
      )}

      {settings.data && (
        <>
          <div className="flex w-full max-w-xl rounded-md bg-muted/30 p-1">
            {settingsTabs.map(({ key, label, icon: Icon }) => {
              const isActive = activeTab === key;
              return (
                <button
                  key={key}
                  type="button"
                  role="tab"
                  aria-selected={isActive}
                  className={`flex h-9 flex-1 items-center justify-center gap-2 rounded-sm px-3 text-sm font-medium cursor-pointer transition-colors ${
                    isActive
                      ? "bg-background text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                  onClick={() => setActiveTab(key)}
                >
                  <Icon className="size-4" />
                  {label}
                </button>
              );
            })}
          </div>

          {activeTab === "providers" && (
          <section className="space-y-3">
            {settings.data.providers.length === 0 ? (
              <div className="rounded-md border border-dashed p-8 text-center text-sm text-muted-foreground">
                暂无供应商配置，业务会使用环境变量 fallback。
              </div>
            ) : (
              <div className="grid min-w-0 grid-cols-[repeat(auto-fit,minmax(min(100%,20rem),1fr))] gap-3">
                {settings.data.providers.map((provider) => (
                  <Card key={provider.id} className="min-w-0 overflow-hidden">
                    <CardHeader className="gap-2">
                      <div className="flex min-w-0 items-start justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          <CardTitle className="truncate text-base">
                            {provider.name}
                          </CardTitle>
                          <p
                            className="mt-1 flex min-w-0 max-w-full items-center gap-1 text-xs text-muted-foreground"
                            title={`${providerLabels[provider.providerType]} · ${provider.baseUrl}`}
                          >
                            <span className="shrink-0 font-medium">
                              {providerLabels[provider.providerType]}
                            </span>
                            <span className="shrink-0">·</span>
                            <span className="min-w-0 flex-1 truncate">
                              {provider.baseUrl}
                            </span>
                          </p>
                        </div>
                        <Badge
                          className="shrink-0"
                          variant={provider.isActive ? "default" : "secondary"}
                        >
                          {provider.isActive ? "启用" : "停用"}
                        </Badge>
                      </div>
                    </CardHeader>
                    <CardContent className="min-w-0 space-y-3 text-sm">
                      <div className="flex flex-wrap items-center gap-3 text-xs">
                        <span className="flex min-w-0 items-center gap-1">
                          <KeyRound className="size-3.5" />
                          {provider.apiKeySet ? "密钥已设置" : "未设置密钥"}
                        </span>
                        <span>超时 {provider.timeoutSeconds}s</span>
                      </div>
                      <div className="flex shrink-0 justify-end gap-1 pt-1">
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          onClick={() => {
                            setEditingProvider(provider);
                            setProviderDialogOpen(true);
                          }}
                          aria-label={`编辑 ${provider.name}`}
                        >
                          <Pencil />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          className="text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                          onClick={() => removeProvider(provider)}
                          disabled={deleteProvider.isPending}
                          aria-label={`删除 ${provider.name}`}
                        >
                          <Trash2 />
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </section>
          )}

          {activeTab === "models" && (
          <section className="space-y-3">
            <div className="overflow-hidden rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>模型</TableHead>
                    <TableHead>供应商</TableHead>
                    <TableHead>Token 上限</TableHead>
                    <TableHead>成本 / 百万 token</TableHead>
                    <TableHead className="text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {settings.data.models.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={5} className="h-24 text-center text-muted-foreground">
                        暂无模型配置。
                      </TableCell>
                    </TableRow>
                  )}
                  {settings.data.models.map((model) => {
                    const provider = providerMap.get(model.providerId);
                    return (
                      <TableRow key={model.id}>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <span className="font-medium">{model.name}</span>
                            <Badge variant={model.isActive ? "default" : "secondary"}>
                              {model.isActive ? "启用" : "停用"}
                            </Badge>
                          </div>
                          <p className="text-xs text-muted-foreground">{model.model}</p>
                        </TableCell>
                        <TableCell>{provider?.name ?? "供应商已缺失"}</TableCell>
                        <TableCell>
                          内容 {model.contentMaxTokens.toLocaleString()} / JSON{" "}
                          {model.jsonMaxTokens.toLocaleString()}
                        </TableCell>
                        <TableCell>
                          输入 {Number(model.inputCostPerMillion).toFixed(4)} · 缓存{" "}
                          {Number(model.cachedInputCostPerMillion).toFixed(4)} · 输出{" "}
                          {Number(model.outputCostPerMillion).toFixed(4)}
                        </TableCell>
                        <TableCell className="text-right">
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            onClick={() => runModelTest(model)}
                            disabled={testModel.isPending}
                            aria-label={`测试 ${model.name} 连通性`}
                            title="发送 Hi 测试连通性"
                          >
                            {testingModelId === model.id ? (
                              <Loader2 className="animate-spin" />
                            ) : (
                              <Zap />
                            )}
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            onClick={() => {
                              setEditingModel(model);
                              setModelDialogOpen(true);
                            }}
                            aria-label={`编辑 ${model.name}`}
                          >
                            <Pencil />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            className="text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                            onClick={() => removeModel(model)}
                            disabled={deleteModel.isPending}
                            aria-label={`删除 ${model.name}`}
                          >
                            <Trash2 />
                          </Button>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          </section>
          )}

          {activeTab === "business" && (
          <section className="space-y-3">
            <div className="overflow-hidden rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>业务</TableHead>
                    <TableHead>当前模型</TableHead>
                    <TableHead>选择模型</TableHead>
                    <TableHead className="text-right">状态</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {settings.data.businessOptions.map((business) => {
                    const config = configMap.get(business.key);
                    const model = config ? modelMap.get(config.modelId) : undefined;
                    const provider = model ? providerMap.get(model.providerId) : undefined;
                    return (
                      <TableRow key={business.key}>
                        <TableCell className="font-medium">{business.label}</TableCell>
                        <TableCell>
                          <p>{model ? `${model.name} · ${model.model}` : "未配置"}</p>
                          <p className="text-xs text-muted-foreground">
                            {provider?.name ??
                              (business.key === "default"
                                ? "未命中具体业务配置时使用"
                                : "未配置时走默认或环境变量 fallback")}
                          </p>
                        </TableCell>
                        <TableCell>
                          <select
                            className="h-9 w-full max-w-md rounded-md border bg-background px-3 text-sm"
                            value={config?.modelId ?? ""}
                            onChange={(event) =>
                              updateBusiness(business.key, event.target.value)
                            }
                            disabled={
                              setBusinessConfig.isPending ||
                              deleteBusinessConfig.isPending
                            }
                          >
                            <option value="">环境变量 fallback</option>
                            {settings.data.models
                              .filter((item) => {
                                const itemProvider = providerMap.get(item.providerId);
                                return item.isActive && itemProvider?.isActive;
                              })
                              .map((item) => {
                                const itemProvider = providerMap.get(item.providerId);
                                return (
                                  <option key={item.id} value={item.id}>
                                    {item.name} · {itemProvider?.name}
                                  </option>
                                );
                              })}
                          </select>
                        </TableCell>
                        <TableCell className="text-right">
                          {model ? (
                            <Badge variant="default">
                              <CheckCircle2 className="size-3" />
                              已绑定
                            </Badge>
                          ) : (
                            <Badge variant="secondary">
                              <XCircle className="size-3" />
                              fallback
                            </Badge>
                          )}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          </section>
          )}
        </>
      )}

      <ProviderDialog
        provider={editingProvider}
        open={providerDialogOpen}
        onClose={() => setProviderDialogOpen(false)}
      />
      <ModelDialog
        model={editingModel}
        providers={settings.data?.providers ?? []}
        open={modelDialogOpen}
        onClose={() => setModelDialogOpen(false)}
      />
    </div>
  );
}
