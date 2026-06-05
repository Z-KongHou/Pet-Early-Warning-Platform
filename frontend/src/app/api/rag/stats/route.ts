import { NextResponse } from "next/server";

function aiServiceOrigin(): string {
  const raw = process.env.AI_SERVICE_URL ?? "http://127.0.0.1:8000";
  return raw.replace(/\/$/, "");
}

export async function GET(): Promise<Response> {
  try {
    const target = `${aiServiceOrigin()}/api/rag/stats`;
    const res = await fetch(target, { method: "GET", cache: "no-store" });
    const text = await res.text();
    return new Response(text, {
      status: res.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch {
    return NextResponse.json(
      {
        code: 50201,
        message: "无法连接 RAG 服务，请确认 ai 服务已启动",
        data: null,
      },
      { status: 502 }
    );
  }
}
