import { useQuery, useMutation } from "@tanstack/react-query";
import { fetchNarrative, regenerateSceneTts } from "@/lib/api";

export function useNarrative(projectId: string) {
  return useQuery({
    queryKey: ["narrative", projectId],
    queryFn: () => fetchNarrative(projectId),
    enabled: !!projectId,
    retry: false,
  });
}

export function useRegenerateTts(projectId: string) {
  return useMutation({
    mutationFn: ({
      sceneIndex,
      narration,
    }: {
      sceneIndex: number;
      narration: string;
    }) => regenerateSceneTts(projectId, sceneIndex, narration),
  });
}
