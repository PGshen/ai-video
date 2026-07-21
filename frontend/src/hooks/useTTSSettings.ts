import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { TTSEngineConfig, TTSSettingsResponse, TTSVoice } from "@/types";

export interface TTSEngineInput {
  name: string;
  code: string;
  providerType: "volcengine";
  endpoint: string;
  apiKey?: string;
  resourceId: string;
  timeoutSeconds: number;
  isActive: boolean;
}

export interface TTSVoiceInput {
  engineId: string;
  name: string;
  speakerId: string;
  language: string;
  gender?: string;
  description?: string;
  isActive: boolean;
}

const key = ["tts-settings"];

export function useTTSSettings(activeOnly = false) {
  return useQuery<TTSSettingsResponse>({
    queryKey: [...key, activeOnly],
    queryFn: () => api.get<TTSSettingsResponse>(`/api/tts-settings${activeOnly ? "?active_only=true" : ""}`),
  });
}

function mutation<TInput, TOutput>(fn: (data: TInput) => Promise<TOutput>) {
  return function useConfigMutation() {
    const queryClient = useQueryClient();
    return useMutation({ mutationFn: fn, onSuccess: () => queryClient.invalidateQueries({ queryKey: key }) });
  };
}

export const useCreateTTSEngine = mutation<TTSEngineInput, TTSEngineConfig>(
  (data) => api.post("/api/tts-settings/engines", data)
);
export const useUpdateTTSEngine = mutation<TTSEngineInput & { id: string }, TTSEngineConfig>(
  ({ id, ...data }) => api.put(`/api/tts-settings/engines/${id}`, data)
);
export const useDeleteTTSEngine = mutation<string, void>(
  (id) => api.delete(`/api/tts-settings/engines/${id}`)
);
export const useCreateTTSVoice = mutation<TTSVoiceInput, TTSVoice>(
  (data) => api.post("/api/tts-settings/voices", data)
);
export const useUpdateTTSVoice = mutation<TTSVoiceInput & { id: string }, TTSVoice>(
  ({ id, ...data }) => api.put(`/api/tts-settings/voices/${id}`, data)
);
export const useDeleteTTSVoice = mutation<string, void>(
  (id) => api.delete(`/api/tts-settings/voices/${id}`)
);

export function usePreviewTTSVoice() {
  return useMutation({
    mutationFn: ({ id, text, speed = 1 }: { id: string; text: string; speed?: number }) =>
      api.postBlob(`/api/tts-settings/voices/${id}/preview`, { text, speed }),
  });
}
