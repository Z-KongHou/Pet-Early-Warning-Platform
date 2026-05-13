import { NextResponse } from "next/server";

const HOP_BY_HOP = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailers",
  "transfer-encoding",
  "upgrade",
  "host",
  "content-length",
]);

function backendOrigin(): string {
  const raw = process.env.BACKEND_URL ?? process.env.API_PROXY_TARGET ?? "http://127.0.0.1:8081";
  return raw.replace(/\/$/, "");
}

/**
 * Forwards the Route Handler request to the Spring Boot API (same path as `/api/...`).
 * Set `BACKEND_URL` or `API_PROXY_TARGET` if the backend is not at http://127.0.0.1:8081.
 */
export async function proxyToBackend(req: Request): Promise<Response> {
  try {
    const incoming = new URL(req.url);
    const target = `${backendOrigin()}${incoming.pathname}${incoming.search}`;

    const headers = new Headers();
    req.headers.forEach((value, key) => {
      if (HOP_BY_HOP.has(key.toLowerCase())) return;
      headers.set(key, value);
    });

    const method = req.method;
    const forwardBody = method !== "GET" && method !== "HEAD" && req.body;
    const init: RequestInit = {
      method,
      headers,
      redirect: "manual",
      ...(forwardBody ? { body: req.body, duplex: "half" as const } : {}),
    };

    return await fetch(target, init);
  } catch {
    return NextResponse.json(
      {
        code: 50201,
        message: "无法连接后端服务，请检查 BACKEND_URL 与后端是否已启动",
        data: null,
        requestId: crypto.randomUUID(),
      },
      { status: 502 }
    );
  }
}
