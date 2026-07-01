import { supabase } from "./supabase";
import { emitApiError } from "./errorBus";

const API_URL = (
  (import.meta.env.VITE_API_URL as string) ?? "http://localhost:8000"
).replace(/\/+$/, "");

/** Error thrown for a non-2xx API response, carrying the HTTP status. */
export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

const STATUS_MESSAGES: Record<number, string> = {
  400: "Something was wrong with that request.",
  401: "Your session has expired — please sign in again.",
  403: "You don't have permission to do that.",
  404: "We couldn't find what you were looking for.",
  409: "That conflicts with the current state — try refreshing.",
  413: "That file is too large.",
  422: "Some of the details weren't valid.",
  429: "You've reached your usage limit for now.",
};

/** Turn a raw error response body into a short, human-readable message. */
function friendlyMessage(status: number, body: string): string {
  let detail = "";
  try {
    const parsed = JSON.parse(body);
    detail = parsed?.detail ?? parsed?.error ?? parsed?.message ?? "";
    if (detail && typeof detail !== "string") detail = "";
  } catch {
    detail = (body ?? "").trim();
  }
  // Ignore giant HTML error pages / stack traces — fall back to a clean message.
  if (detail.length > 180 || /^\s*</.test(detail)) detail = "";

  if (detail) return detail;
  if (status >= 500) return "Something went wrong on our end. Please try again.";
  return STATUS_MESSAGES[status] ?? `Request failed (${status}).`;
}

async function authHeader(): Promise<Record<string, string>> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit & { timeoutMs?: number } = {}
): Promise<T> {
  const { timeoutMs, ...fetchOptions } = options;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(await authHeader()),
    ...((fetchOptions.headers as Record<string, string>) ?? {}),
  };

  const controller = timeoutMs ? new AbortController() : null;
  const timer =
    controller &&
    window.setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(`${API_URL}${path}`, {
      ...fetchOptions,
      headers,
      signal: controller?.signal,
    });
    if (!res.ok) {
      const body = await res.text();
      const message = friendlyMessage(res.status, body);
      emitApiError(message);
      throw new ApiError(res.status, message);
    }
    if (res.status === 204) return undefined as T;
    return (await res.json()) as T;
  } catch (e) {
    // ApiError already reported above — just rethrow.
    if (e instanceof ApiError) throw e;

    if (e instanceof DOMException && e.name === "AbortError") {
      const message = `The request timed out after ${Math.round((timeoutMs ?? 0) / 1000)}s. Please try again.`;
      emitApiError(message);
      throw new Error(message);
    }

    // Network failure, DNS, CORS, server unreachable, etc.
    emitApiError("Couldn't reach the server. Check your connection and try again.");
    throw e;
  } finally {
    if (timer) window.clearTimeout(timer);
  }
}
