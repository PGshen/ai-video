import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { BrainstormCandidate, Topic, TopicScores } from "@/types";

interface TopicListResponse {
  items: Topic[];
  total: number;
}

interface BrainstormResponse {
  candidates: BrainstormCandidate[];
}

export function useTopics(status?: string, title?: string) {
  return useQuery<TopicListResponse>({
    queryKey: ["topics", status, title],
    queryFn: () => {
      const params = new URLSearchParams();
      if (status) params.set("status", status);
      if (title) params.set("title", title);
      const query = params.toString();
      return api.get<TopicListResponse>(`/api/topics${query ? `?${query}` : ""}`);
    },
  });
}

export function useBrainstormTopics() {
  return useMutation({
    mutationFn: (data: { topicDirection: string; count: number }) =>
      api.post<BrainstormResponse>("/api/topics/brainstorm", {
        topic_direction: data.topicDirection,
        count: data.count,
      }),
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

export function useImportBrainstormCandidates() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (candidates: BrainstormCandidate[]) =>
      Promise.all(
        candidates.map((candidate) =>
          api.post<Topic>("/api/topics", {
            title: candidate.title,
            description: candidate.description || undefined,
            source: "ai_brainstorm",
            tags: candidate.tags ?? [],
          })
        )
      ),
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

export function useDeleteTopic() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete(`/api/topics/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["topics"] }),
  });
}
