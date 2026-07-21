const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function throwResponseError(response: Response): Promise<never> {
  if (response.status === 401) {
    window.dispatchEvent(new CustomEvent("auth:unauthorized"));
  }
  const errorBody = await response.json().catch(() => null);
  const detail =
    errorBody && typeof errorBody.detail === "string"
      ? errorBody.detail
      : `API error: ${response.status} ${response.statusText}`;
  const error = new Error(detail) as Error & { status: number };
  error.status = response.status;
  throw error;
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown
): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    method,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    return throwResponseError(response);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

async function postBlob(path: string, body: unknown): Promise<Blob> {
  const response = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) return throwResponseError(response);
  return response.blob();
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body),
  put: <T>(path: string, body?: unknown) => request<T>("PUT", path, body),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, body),
  delete: (path: string) => request<void>("DELETE", path),
  postBlob,
};

export function fetchNarrative(projectId: string) {
  return api.get<import("@/types").NarrativeVersion>(
    `/api/projects/${projectId}/narrative`
  );
}

export function regenerateSceneTts(
  projectId: string,
  sceneIndex: number,
  narration: string,
  beats: import("@/types").NarrativeBeat[]
) {
  return api.post<import("@/types").RegenerateTtsResponse>(
    `/api/projects/${projectId}/narrative/tts`,
    { sceneIndex, narration, beats }
  );
}
