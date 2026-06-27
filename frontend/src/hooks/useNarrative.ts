import { useQuery } from "@tanstack/react-query";
import { fetchNarrative } from "@/lib/api";

export function useNarrative(projectId: string) {
  return useQuery({
    queryKey: ["narrative", projectId],
    queryFn: () => fetchNarrative(projectId),
    enabled: !!projectId,
    retry: false,
  });
}
