const API_KEY = import.meta.env.VITE_API_KEY || "dev-local-key";
const BASE = "/api";

class ApiError extends Error {
  constructor(status, detail) {
    super(detail || `Request failed with status ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: { "x-api-key": API_KEY, ...options.headers },
  });
  if (!res.ok) {
    let detail;
    try {
      detail = (await res.json()).detail;
    } catch {
      detail = res.statusText;
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return null;
  return res.json();
}

export function uploadDocument(file) {
  const form = new FormData();
  form.append("file", file);
  return request("/documents", { method: "POST", body: form });
}

export function getJob(jobId) {
  return request(`/jobs/${jobId}`);
}

export function getTkp(tkpId) {
  return request(`/tkp/${tkpId}`);
}

export function regenerateSection(tkpId, section) {
  return request(`/tkp/${tkpId}/regenerate/${section}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
}

/**
 * EventSource can't send custom headers, so the SSE stream is consumed via a
 * manual fetch + ReadableStream reader instead — keeps auth consistent with
 * every other endpoint (x-api-key header, not a query-string token).
 */
export async function streamJobProgress(jobId, onEvent, { signal } = {}) {
  const res = await fetch(`${BASE}/jobs/${jobId}/stream`, {
    headers: { "x-api-key": API_KEY },
    signal,
  });
  if (!res.ok || !res.body) {
    throw new ApiError(res.status, "Could not open progress stream");
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) return;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop();
    for (const chunk of chunks) {
      const line = chunk.split("\n").find((l) => l.startsWith("data: "));
      if (line) onEvent(JSON.parse(line.slice("data: ".length)));
    }
  }
}

export { ApiError };
