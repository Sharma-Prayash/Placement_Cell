// Thin fetch wrapper. Session cookie is HttpOnly (JS never sees it); the CSRF token
// is read from its cookie and echoed in a header on every state-changing request.

export class ApiError extends Error {
  status: number;
  data: Record<string, unknown>;
  constructor(status: number, data: Record<string, unknown>) {
    super(typeof data.detail === "string" ? data.detail : "The request could not be completed.");
    this.status = status;
    this.data = data;
  }
}

function csrfToken(): string {
  const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : "";
}

export async function ensureCsrf() {
  if (!csrfToken()) await fetch("/api/auth/csrf", { credentials: "same-origin" });
}

export async function api<T = any>(path: string, opts: { method?: string; body?: unknown; form?: FormData } = {}): Promise<T> {
  const method = opts.method ?? (opts.body !== undefined || opts.form ? "POST" : "GET");
  const headers: Record<string, string> = { Accept: "application/json" };
  if (method !== "GET") {
    await ensureCsrf();
    headers["X-CSRFToken"] = csrfToken();
  }
  if (opts.body !== undefined) headers["Content-Type"] = "application/json";
  const res = await fetch(`/api${path}`, {
    method,
    headers,
    credentials: "same-origin",
    body: opts.form ?? (opts.body !== undefined ? JSON.stringify(opts.body) : undefined),
  });
  const type = res.headers.get("content-type") ?? "";
  if (!res.ok) {
    const data = type.includes("json") ? await res.json() : { detail: `Request failed (${res.status}).` };
    throw new ApiError(res.status, data);
  }
  if (type.includes("json")) return res.json();
  return (await res.blob()) as unknown as T;
}

/** Turn a DRF error payload into readable lines. */
export function errorLines(e: unknown): string[] {
  if (!(e instanceof ApiError)) return ["The server could not be reached. Check that the backend is running."];
  const lines: string[] = [];
  for (const [k, v] of Object.entries(e.data)) {
    if (k === "verdict" || k === "policy") continue;
    const text = Array.isArray(v) ? v.join(" ") : typeof v === "string" ? v : JSON.stringify(v);
    lines.push(k === "detail" || k === "non_field_errors" ? text : `${k.replace(/_/g, " ")}: ${text}`);
  }
  return lines.length ? lines : [e.message];
}
