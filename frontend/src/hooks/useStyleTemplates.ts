import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type {
  StyleAssistantMessage,
  StyleLibraryAssistantResponse,
  StyleLibraryDraft,
  StyleTemplate,
  StyleTemplateListResponse,
} from "@/types";

interface StyleTemplateInput {
  name: string;
  description?: string;
  styleConfig: Record<string, string>;
}

function serializeLibrary(data: StyleLibraryDraft) {
  return {
    name: data.name,
    description: data.description,
    components: Object.fromEntries(
      Object.entries(data.components).map(([category, component]) => [
        category,
        {
          name: component.name,
          description: component.description,
          prompt_text: component.promptText,
        },
      ])
    ),
  };
}

export function useStyleTemplates() {
  return useQuery<StyleTemplateListResponse>({
    queryKey: ["style-templates"],
    queryFn: () => api.get<StyleTemplateListResponse>("/api/style-templates"),
  });
}

export function useCreateStyleTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: StyleTemplateInput) =>
      api.post<StyleTemplate>("/api/style-templates", {
        name: data.name,
        description: data.description,
        style_config: data.styleConfig,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["style-templates"] });
    },
  });
}

export function useUpdateStyleTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...data }: StyleTemplateInput & { id: string }) =>
      api.put<StyleTemplate>(`/api/style-templates/${id}`, {
        name: data.name,
        description: data.description,
        style_config: data.styleConfig,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["style-templates"] });
    },
  });
}

export function useDeleteStyleTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete(`/api/style-templates/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["style-templates"] });
    },
  });
}

export function useCreateStyleLibrary() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: StyleLibraryDraft) =>
      api.post<StyleTemplate>("/api/style-templates/library", serializeLibrary(data)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["style-templates"] });
      queryClient.invalidateQueries({ queryKey: ["prompt-components"] });
    },
  });
}

export function useUpdateStyleLibrary() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...data }: StyleLibraryDraft & { id: string }) =>
      api.put<StyleTemplate>(
        `/api/style-templates/${id}/library`,
        serializeLibrary(data)
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["style-templates"] });
      queryClient.invalidateQueries({ queryKey: ["prompt-components"] });
    },
  });
}

export function useStyleLibraryAssistant() {
  return useMutation({
    mutationFn: (
      data: StyleLibraryDraft & {
        conversationHistory: StyleAssistantMessage[];
        message: string;
      }
    ) =>
      api.post<StyleLibraryAssistantResponse>("/api/style-templates/assist", {
        ...serializeLibrary(data),
        conversation_history: data.conversationHistory,
        message: data.message,
      }),
  });
}
