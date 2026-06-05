import { NextResponse } from "next/server";

function aiServiceOrigin(): string {
  const raw = process.env.AI_SERVICE_URL ?? "http://127.0.0.1:8000";
  return raw.replace(/\/$/, "");
}

export async function POST(req: Request): Promise<Response> {
  try {
    const target = `${aiServiceOrigin()}/api/rag/query/stream`;
    const headers = new Headers({ "Content-Type": "application/json" });
    const requestId = req.headers.get("X-Request-Id");
    if (requestId) headers.set("X-Request-Id", requestId);

    const res = await fetch(target, {
      method: "POST",
      headers,
      body: await req.text(),
    });

    if (!res.body) {
      const text = await res.text();
      return new Response(text, {
        status: res.status,
        headers: { "Content-Type": res.headers.get("Content-Type") ?? "application/json" },
      });
    }

    return new Response(res.body, {
      status: res.status,
      headers: {
        "Content-Type": "text/event-stream; charset=utf-8",
        "Cache-Control": "no-cache, no-transform",
        Connection: "keep-alive",
        "X-Accel-Buffering": "no",
      },
    });
  } catch {
    return NextResponse.json(
      {
        code: 50201,
        message:
          "无法连接 RAG 服务，请确认 ai 服务已在 8000 端口启动（cd ai && poetry run yingshi-ai）",
        data: null,
      },
      { status: 502 }
    );
  }
}
