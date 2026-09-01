export const API_BASE_OVERRIDE_KEY = "anti_fomo_api_base_override";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiRequestError extends Error {
  readonly status: number;
  readonly body: string;

  constructor(status: number, body: string) {
    super(`API ${status}: ${body}`);
    this.name = "ApiRequestError";
    this.status = status;
    this.body = body;
  }
}

export function isApiRequestError(error: unknown): error is ApiRequestError {
  return error instanceof ApiRequestError;
}

export function resolveApiBase(): string {
  if (typeof window !== "undefined") {
    const runtimeOverride = window.localStorage.getItem(API_BASE_OVERRIDE_KEY)?.trim() || "";
    if (/^https?:\/\//i.test(runtimeOverride)) {
      return runtimeOverride.replace(/\/+$/, "");
    }
  }
  return API_BASE.replace(/\/+$/, "");
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${resolveApiBase()}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    const text = await response.text();
    throw new ApiRequestError(response.status, text);
  }
  const text = await response.text();
  if (!text) {
    return undefined as T;
  }
  return JSON.parse(text) as T;
}
