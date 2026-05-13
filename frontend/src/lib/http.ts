import type { ApiResponse } from "@/lib/types";

export class ApiError extends Error {
  code: number;
  requestId?: string;
  constructor(message: string, code: number, requestId?: string) {
    super(message);
    this.code = code;
    this.requestId = requestId;
  }
}

export async function apiFetch<T>(
  path: string,
  init?: RequestInit & { json?: unknown }
): Promise<T> {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";
  const url = `${base}${path}`;

  const headers = new Headers(init?.headers);
  if (init?.json !== undefined) headers.set("Content-Type", "application/json");
  if (!headers.has("X-Request-Id")) headers.set("X-Request-Id", crypto.randomUUID());

  const res = await fetch(url, {
    ...init,
    headers,
    body: init?.json !== undefined ? JSON.stringify(init.json) : init?.body,
    cache: "no-store",
  });

  const text = await res.text();
  const payload = text ? (JSON.parse(text) as ApiResponse<T>) : undefined;

  if (!res.ok || !payload) {
    throw new ApiError(
      payload?.message ?? `HTTP ${res.status}`,
      payload?.code ?? res.status,
      payload?.requestId
    );
  }
  if (payload.code !== 200) {
    throw new ApiError(payload.message, payload.code, payload.requestId);
  }
  return payload.data;
}

