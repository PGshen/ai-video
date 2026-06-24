import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Topic } from "@/types";

interface TopicListResponse {
  items: Topic[];
  total: number;
}

export function useTopics() {
  return useQuery<TopicListResponse>({
    queryKey: ["topics"],
    queryFn: () => api.get<TopicListResponse>("/api/topics"),
  });
}
