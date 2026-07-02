import { useQuery, useMutation } from "@tanstack/react-query";
import { fetchNarrative, regenerateSceneTts } from "@/lib/api";
import type { NarrativeBeat } from "@/types";

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
      beats,
    }: {
      sceneIndex: number;
      narration: string;
      beats: NarrativeBeat[];
    }) => regenerateSceneTts(projectId, sceneIndex, narration, beats),
  });
}
