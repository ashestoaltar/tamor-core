// ui/src/api/client.js

/**
 * Resolve the base URL for the Tamor backend.
 *
 * In dev (Vite on :5173) we talk to Flask on :5055.
 * In production we assume UI + API are on the same origin and the
 * backend is mounted at /api.
 */
function resolveApiBase() {
  if (typeof window === "undefined") {
    return "http://localhost:5055/api";
  }

  const origin = window.location.origin;

  // If we're on Vite dev (port 5173), talk to Flask on 5055
  if (origin.includes(":5173")) {
    return origin.replace(":5173", ":5055") + "/api";
  }

  // Otherwise (production), UI + API are on same origin at /api
  return origin + "/api";
}

export const API_BASE = resolveApiBase();

/**
 * Thin wrapper around fetch() that:
 *  - prefixes the URL with API_BASE
 *  - sends/receives JSON by default
 *  - includes credentials for cookie-based auth
 *  - throws on non-2xx responses with a helpful error
 */
export async function apiFetch(path, options = {}) {
  const { method = "GET", headers = {}, body = undefined, ...rest } = options;

  const url = API_BASE + path;

  const finalHeaders = {
    Accept: "application/json",
    ...headers,
  };

  let finalBody = body;

  // If the body is a plain object, send as JSON.
  // If it's FormData, let the browser set Content-Type.
  if (body && !(body instanceof FormData)) {
    finalHeaders["Content-Type"] = "application/json";
    finalBody = JSON.stringify(body);
  }

  const resp = await fetch(url, {
    method,
    headers: finalHeaders,
    body: finalBody,
    credentials: "include",
    ...rest,
  });

  const contentType = resp.headers.get("content-type") || "";
  const isJson = contentType.includes("application/json");

  if (!resp.ok) {
    let errorPayload;
    try {
      errorPayload = isJson ? await resp.json() : await resp.text();
    } catch (_) {
      errorPayload = null;
    }

    const err = new Error(
      `API error ${resp.status} ${resp.statusText}` +
        (errorPayload ? ": " + JSON.stringify(errorPayload) : "")
    );
    err.status = resp.status;
    err.payload = errorPayload;
    throw err;
  }

  if (resp.status === 204) return null;

  return isJson ? resp.json() : resp.text();
}

// --- Convenience endpoints used by UI ---

export async function getHealth() {
  return apiFetch("/health");
}

export async function getStatus() {
  return apiFetch("/status");
}

// Phase 4.4: Task run history
export async function getTaskRuns(taskId, limit = 10) {
  return apiFetch(`/tasks/${taskId}/runs?limit=${encodeURIComponent(limit)}`);
}

