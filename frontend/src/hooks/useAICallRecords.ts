import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type {
  AICallRecordDetail,
  AICallRecordListResponse,
} from "@/types";

interface RecordFilters {
  page: number;
  pageSize: number;
  status?: string;
  provider?: string;
  business?: string;
  model?: string;
}

export function useAICallRecords(filters: RecordFilters) {
  const params = new URLSearchParams({
    page: String(filters.page),
    page_size: String(filters.pageSize),
  });
  if (filters.status) params.set("status", filters.status);
  if (filters.provider) params.set("provider", filters.provider);
  if (filters.business) params.set("business", filters.business);
  if (filters.model) params.set("model", filters.model);

  return useQuery<AICallRecordListResponse>({
    queryKey: ["ai-call-records", filters],
    queryFn: () =>
      api.get<AICallRecordListResponse>(
        `/api/ai-call-records?${params.toString()}`
      ),
    refetchInterval: 15_000,
  });
}

export function useAICallRecord(id: string | null) {
  return useQuery<AICallRecordDetail>({
    queryKey: ["ai-call-record", id],
    queryFn: () => api.get<AICallRecordDetail>(`/api/ai-call-records/${id}`),
    enabled: Boolean(id),
  });
}
