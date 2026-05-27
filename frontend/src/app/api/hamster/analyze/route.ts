import { NextResponse } from "next/server";

function aiServiceOrigin(): string {
  const raw = process.env.AI_SERVICE_URL ?? "http://127.0.0.1:8000";
  return raw.replace(/\/$/, "");
}

export async function POST(req: Request): Promise<Response> {
  try {
    const target = `${aiServiceOrigin()}/api/hamster/analyze`;
    const formData = await req.formData();

    const res = await fetch(target, {
      method: "POST",
      body: formData,
    });

    const text = await res.text();
    return new Response(text, {
      status: res.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch {
    return NextResponse.json(
      {
        code: 50201,
        message: "无法连接分析服务，请确认 ai-old 已在 8000 端口启动",
        data: null,
      },
      { status: 502 }
    );
  }
}
