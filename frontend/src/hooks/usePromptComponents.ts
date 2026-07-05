import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type {
  PromptComponent,
  PromptComponentListResponse,
  StyleAssistantMessage,
  StyleAssistantResponse,
} from "@/types";

export function usePromptComponents(category?: string) {
  return useQuery<PromptComponentListResponse>({
    queryKey: ["prompt-components", category],
    queryFn: () =>
      api.get<PromptComponentListResponse>(
        `/api/prompt-components${category ? `?category=${category}` : ""}`
      ),
  });
}

export function useCreatePromptComponent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { category: string; name: string; description?: string; promptText: string }) =>
      api.post<PromptComponent>("/api/prompt-components", {
        category: data.category,
        name: data.name,
        description: data.description,
        prompt_text: data.promptText,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["prompt-components"] });
    },
  });
}

export function useUpdatePromptComponent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...data }: { id: string; category?: string; name?: string; description?: string; promptText?: string }) =>
      api.put<PromptComponent>(`/api/prompt-components/${id}`, {
        category: data.category,
        name: data.name,
        description: data.description,
        prompt_text: data.promptText,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["prompt-components"] });
    },
  });
}

export function useDeletePromptComponent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete(`/api/prompt-components/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["prompt-components"] });
    },
  });
}

export function useDuplicatePromptComponent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      api.post<PromptComponent>(`/api/prompt-components/${id}/duplicate`, {}),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["prompt-components"] });
    },
  });
}

export function useStylePromptAssistant() {
  return useMutation({
    mutationFn: (data: {
      category: string;
      name: string;
      description: string;
      promptText: string;
      conversationHistory: StyleAssistantMessage[];
      message: string;
    }) =>
      api.post<StyleAssistantResponse>("/api/prompt-components/assist", {
        category: data.category,
        name: data.name,
        description: data.description,
        prompt_text: data.promptText,
        conversation_history: data.conversationHistory,
        message: data.message,
      }),
  });
}
