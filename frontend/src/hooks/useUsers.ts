import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { ManagedUser, UserListResponse } from "@/types";

export interface CreateUserInput {
  username: string;
  password: string;
  displayName?: string;
  role: "admin" | "user";
  isActive: boolean;
}

export interface UpdateUserInput {
  id: string;
  displayName?: string | null;
  role?: "admin" | "user";
  isActive?: boolean;
}

export function useUsers() {
  return useQuery({
    queryKey: ["users"],
    queryFn: () => api.get<UserListResponse>("/api/users"),
  });
}

export function useCreateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateUserInput) =>
      api.post<ManagedUser>("/api/users", input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users"] }),
  });
}

export function useUpdateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...input }: UpdateUserInput) =>
      api.patch<ManagedUser>(`/api/users/${id}`, input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users"] }),
  });
}

export function useResetPassword() {
  return useMutation({
    mutationFn: ({ id, password }: { id: string; password: string }) =>
      api.post<ManagedUser>(`/api/users/${id}/reset-password`, { password }),
  });
}

export function useSetUserActive() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      api.post<ManagedUser>(`/api/users/${id}/${active ? "enable" : "disable"}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users"] }),
  });
}
