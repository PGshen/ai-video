import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { VideoProject, ProjectEvent, ReviewRequest, ScriptVersion } from "@/types";

interface ProjectListResponse {
  items: VideoProject[];
  total: number;
}

interface EventListResponse {
  items: ProjectEvent[];
}

export function useProjects(status?: string) {
  return useQuery<ProjectListResponse>({
    queryKey: ["projects", status],
    queryFn: () =>
      api.get<ProjectListResponse>(
        `/api/projects${status ? `?status=${status}` : ""}`
      ),
    refetchInterval: (query) => {
      const items = query.state.data?.items ?? [];
      return items.some((p) => TRANSITIONAL_STATUSES.has(p.status)) ? 3000 : false;
    },
  });
}

const TRANSITIONAL_STATUSES = new Set([
  "narrative_generating",
  "code_generating",
  "video_generating",
]);

export function useProject(id: string) {
  return useQuery<VideoProject>({
    queryKey: ["projects", id],
    queryFn: () => api.get<VideoProject>(`/api/projects/${id}`),
    enabled: !!id,
    refetchInterval: (query) =>
      query.state.data && TRANSITIONAL_STATUSES.has(query.state.data.status)
        ? 3000
        : false,
  });
}

export function useProjectEvents(projectId: string) {
  return useQuery<EventListResponse>({
    queryKey: ["projects", projectId, "events"],
    queryFn: () =>
      api.get<EventListResponse>(`/api/projects/${projectId}/events`),
    enabled: !!projectId,
  });
}

export function useCreateProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: {
      topicId: string;
      renderEngine: string;
      ttsVoice: string;
      aspectRatio: string;
    }) =>
      api.post<VideoProject>("/api/projects", {
        topic_id: data.topicId,
        render_engine: data.renderEngine,
        tts_voice: data.ttsVoice,
        aspect_ratio: data.aspectRatio,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["projects"] });
      qc.invalidateQueries({ queryKey: ["topics"] });
    },
  });
}

export function useSubmitReview() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      projectId,
      ...body
    }: ReviewRequest & { projectId: string }) =>
      api.post(`/api/projects/${projectId}/review`, body),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["projects"] });
      qc.invalidateQueries({ queryKey: ["projects", vars.projectId] });
    },
  });
}

export function useProjectScript(projectId: string) {
  return useQuery<ScriptVersion>({
    queryKey: ["projects", projectId, "script"],
    queryFn: () => api.get<ScriptVersion>(`/api/projects/${projectId}/script`),
    enabled: !!projectId,
    retry: false,
  });
}
