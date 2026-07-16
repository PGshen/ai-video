import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type {
  VideoProject, ProjectEvent, ReviewRequest, CodeVersion, NarrativeVersion,
  Scene, CodeRepairResponse,
} from "@/types";

interface ProjectListResponse {
  items: VideoProject[];
  total: number;
}

interface EventListResponse {
  items: ProjectEvent[];
}

interface ProjectFilters {
  status?: string;
  topicId?: string;
  topicTitle?: string;
  renderEngine?: string;
  aspectRatio?: string;
  page?: number;
  pageSize?: number;
}

export function useProjects(filters: ProjectFilters = {}) {
  return useQuery<ProjectListResponse>({
    queryKey: ["projects", filters],
    queryFn: () => {
      const params = new URLSearchParams();
      if (filters.status) params.set("status", filters.status);
      if (filters.topicId) params.set("topic_id", filters.topicId);
      if (filters.topicTitle) params.set("topic_title", filters.topicTitle);
      if (filters.renderEngine) params.set("render_engine", filters.renderEngine);
      if (filters.aspectRatio) params.set("aspect_ratio", filters.aspectRatio);
      params.set("page", String(filters.page ?? 1));
      params.set("page_size", String(filters.pageSize ?? 10));
      const query = params.toString();
      return api.get<ProjectListResponse>(`/api/projects${query ? `?${query}` : ""}`);
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
      ttsEngine: "doubao_1.0" | "doubao_2.0";
      ttsSpeed: 0.9 | 1.0 | 1.1 | 1.2;
      aspectRatio: string;
      narrativeContext: { text: string }[];
      styleConfig?: Record<string, string>;
    }) =>
      api.post<VideoProject>("/api/projects", {
        topic_id: data.topicId,
        render_engine: data.renderEngine,
        tts_voice: data.ttsVoice,
        tts_engine: data.ttsEngine,
        tts_speed: data.ttsSpeed,
        aspect_ratio: data.aspectRatio,
        narrative_context: data.narrativeContext,
        style_config: data.styleConfig ?? {},
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["projects"] });
      qc.invalidateQueries({ queryKey: ["topics"] });
    },
  });
}

export function useDeleteProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete(`/api/projects/${id}`),
    onSuccess: (_data, id) => {
      qc.removeQueries({ queryKey: ["projects", id] });
      qc.invalidateQueries({
        predicate: (query) =>
          query.queryKey[0] === "projects" &&
          Array.isArray((query.state.data as ProjectListResponse | undefined)?.items),
      });
      qc.invalidateQueries({ queryKey: ["topics"] });
    },
  });
}

export function useResetProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.post(`/api/projects/${id}/reset`),
    onSuccess: (_data, id) => {
      qc.invalidateQueries({ queryKey: ["projects"] });
      qc.invalidateQueries({ queryKey: ["projects", id] });
      qc.invalidateQueries({ queryKey: ["projects", id, "events"] });
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
      qc.invalidateQueries({ queryKey: ["projects", vars.projectId, "events"] });
      qc.invalidateQueries({ queryKey: ["projects", vars.projectId, "code"] });
      qc.invalidateQueries({ queryKey: ["projects", vars.projectId, "code-versions"] });
      qc.invalidateQueries({ queryKey: ["projects", vars.projectId, "narrative-versions"] });
    },
  });
}

export function useProjectCode(projectId: string) {
  return useQuery<CodeVersion | undefined>({
    queryKey: ["projects", projectId, "code"],
    queryFn: () =>
      api.get<CodeVersion>(`/api/projects/${projectId}/code`).catch((e: Error & { status?: number }) => {
        if (e.status === 404) return undefined;
        throw e;
      }),
    enabled: !!projectId,
    retry: false,
  });
}

export function useRepairCode() {
  return useMutation({
    mutationFn: ({
      projectId,
      errorMessage,
      scenes,
    }: {
      projectId: string;
      errorMessage: string;
      scenes: Scene[];
    }) =>
      api.post<CodeRepairResponse>(`/api/projects/${projectId}/code/repair`, {
        errorMessage,
        scenes,
      }),
  });
}

export function useNarrativeVersions(projectId: string) {
  return useQuery<NarrativeVersion[]>({
    queryKey: ["projects", projectId, "narrative-versions"],
    queryFn: () =>
      api.get<NarrativeVersion[]>(`/api/projects/${projectId}/narrative-versions`),
    enabled: !!projectId,
    retry: false,
  });
}

export function useNarrativeVersion(projectId: string, versionId: string | null) {
  return useQuery<NarrativeVersion>({
    queryKey: ["projects", projectId, "narrative-versions", versionId],
    queryFn: () =>
      api.get<NarrativeVersion>(
        `/api/projects/${projectId}/narrative-versions/${versionId}`
      ),
    enabled: !!projectId && !!versionId,
    retry: false,
  });
}

export function useCodeVersions(projectId: string) {
  return useQuery<CodeVersion[]>({
    queryKey: ["projects", projectId, "code-versions"],
    queryFn: () =>
      api.get<CodeVersion[]>(`/api/projects/${projectId}/code-versions`),
    enabled: !!projectId,
    retry: false,
  });
}

export function useVideoUrl(projectId: string, assetId: string | null) {
  return useQuery<{ url: string; expires_in: number }>({
    queryKey: ["projects", projectId, "video-url", assetId],
    queryFn: () =>
      api.get(`/api/projects/${projectId}/video-url?asset_id=${assetId}`),
    enabled: !!projectId && !!assetId,
    staleTime: 30 * 60 * 1000, // presigned URL 1h, refetch at 30min
    retry: false,
  });
}

export function useCodeVersion(projectId: string, versionId: string | null) {
  return useQuery<CodeVersion>({
    queryKey: ["projects", projectId, "code-versions", versionId],
    queryFn: () =>
      api.get<CodeVersion>(
        `/api/projects/${projectId}/code-versions/${versionId}`
      ),
    enabled: !!projectId && !!versionId,
    retry: false,
  });
}
