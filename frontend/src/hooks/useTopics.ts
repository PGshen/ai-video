import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Topic, TopicScores } from "@/types";

interface TopicListResponse {
  items: Topic[];
  total: number;
}

export function useTopics(status?: string) {
  return useQuery<TopicListResponse>({
    queryKey: ["topics", status],
    queryFn: () =>
      api.get<TopicListResponse>(
        `/api/topics${status ? `?status=${status}` : ""}`
      ),
  });
}

export function useCreateTopic() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      title: string;
      description?: string;
      source: string;
      tags: string[];
    }) => api.post<Topic>("/api/topics", data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["topics"] }),
  });
}

export function useUpdateTopic() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      ...data
    }: {
      id: string;
      scores?: TopicScores;
      status?: string;
      tags?: string[];
    }) => api.patch<Topic>(`/api/topics/${id}`, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["topics"] }),
  });
}
