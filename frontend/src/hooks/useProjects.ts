import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { VideoProject } from "@/types";

interface ProjectListResponse {
  items: VideoProject[];
  total: number;
}

export function useProjects(status?: string) {
  return useQuery<ProjectListResponse>({
    queryKey: ["projects", status],
    queryFn: () =>
      api.get<ProjectListResponse>(
        `/api/projects${status ? `?status=${status}` : ""}`
      ),
  });
}

export function useProject(id: string) {
  return useQuery<VideoProject>({
    queryKey: ["projects", id],
    queryFn: () => api.get<VideoProject>(`/api/projects/${id}`),
    enabled: !!id,
  });
}
