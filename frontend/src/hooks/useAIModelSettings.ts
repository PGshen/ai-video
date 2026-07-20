import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type {
  AIBusinessModelConfig,
  AIModelProvider,
  AIModelSettingsResponse,
  AIModelTestResponse,
  AIProviderModel,
  AIProviderType,
} from "@/types";

export interface AIModelProviderInput {
  name: string;
  providerType: AIProviderType;
  baseUrl: string;
  apiKey?: string;
  timeoutSeconds: number;
  siteUrl?: string;
  siteName?: string;
  isActive: boolean;
}

export interface AIProviderModelInput {
  providerId: string;
  name: string;
  model: string;
  contentMaxTokens: number;
  jsonMaxTokens: number;
  inputCostPerMillion: string;
  cachedInputCostPerMillion: string;
  outputCostPerMillion: string;
  isActive: boolean;
}

export function useAIModelSettings() {
  return useQuery<AIModelSettingsResponse>({
    queryKey: ["ai-model-settings"],
    queryFn: () => api.get<AIModelSettingsResponse>("/api/ai-model-settings"),
  });
}

export function useCreateAIModelProvider() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: AIModelProviderInput) =>
      api.post<AIModelProvider>("/api/ai-model-settings/providers", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ai-model-settings"] });
    },
  });
}

export function useUpdateAIModelProvider() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...data }: AIModelProviderInput & { id: string }) =>
      api.put<AIModelProvider>(`/api/ai-model-settings/providers/${id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ai-model-settings"] });
    },
  });
}

export function useDeleteAIModelProvider() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete(`/api/ai-model-settings/providers/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ai-model-settings"] });
    },
  });
}

export function useCreateAIProviderModel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: AIProviderModelInput) =>
      api.post<AIProviderModel>("/api/ai-model-settings/models", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ai-model-settings"] });
    },
  });
}

export function useUpdateAIProviderModel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...data }: AIProviderModelInput & { id: string }) =>
      api.put<AIProviderModel>(`/api/ai-model-settings/models/${id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ai-model-settings"] });
    },
  });
}

export function useDeleteAIProviderModel() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete(`/api/ai-model-settings/models/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ai-model-settings"] });
    },
  });
}

export function useTestAIProviderModel() {
  return useMutation({
    mutationFn: (data: { providerId: string; model: string }) =>
      api.post<AIModelTestResponse>("/api/ai-model-settings/models/test", data),
  });
}

export function useSetAIBusinessModelConfig() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ business, modelId }: { business: string; modelId: string }) =>
      api.put<AIBusinessModelConfig>(
        `/api/ai-model-settings/business-configs/${business}`,
        { modelId }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ai-model-settings"] });
    },
  });
}

export function useDeleteAIBusinessModelConfig() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (business: string) =>
      api.delete(`/api/ai-model-settings/business-configs/${business}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ai-model-settings"] });
    },
  });
}
