import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { WorkerTask } from "@/types";

interface WorkerTaskListResponse {
  items: WorkerTask[];
}

export function useWorkerTasks(projectId?: string) {
  return useQuery<WorkerTaskListResponse>({
    queryKey: ["worker-tasks", projectId],
    queryFn: () =>
      api.get<WorkerTaskListResponse>(
        `/api/worker-tasks${projectId ? `?project_id=${projectId}` : ""}`
      ),
    refetchInterval: 3000,
  });
}
