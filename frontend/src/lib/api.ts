const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const API_KEY = import.meta.env.VITE_API_KEY ?? "";

async function request<T>(
  method: string,
  path: string,
  body?: unknown
): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": API_KEY,
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    const detail =
      errorBody && typeof errorBody.detail === "string"
        ? errorBody.detail
        : `API error: ${response.status} ${response.statusText}`;
    throw new Error(detail);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, body),
  delete: (path: string) => request<void>("DELETE", path),
};

export function fetchNarrative(projectId: string) {
  return api.get<import("@/types").NarrativeVersion>(
    `/api/projects/${projectId}/narrative`
  );
}

export function regenerateSceneTts(
  projectId: string,
  sceneIndex: number,
  narration: string
) {
  return api.post<import("@/types").RegenerateTtsResponse>(
    `/api/projects/${projectId}/narrative/tts`,
    { sceneIndex, narration }
  );
}
