import { getToken } from "@/lib/auth-client";

/** Stable shape for `fetch` / `apiFetch` headers typing */
export function authHeaders(): Record<string, string> {
  const token = getToken();
  const h: Record<string, string> = {};
  if (token) h.Authorization = `Bearer ${token}`;
  return h;
}

