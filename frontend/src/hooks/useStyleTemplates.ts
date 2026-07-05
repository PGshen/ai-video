import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { StyleTemplate, StyleTemplateListResponse } from "@/types";

interface StyleTemplateInput {
  name: string;
  description?: string;
  styleConfig: Record<string, string>;
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
