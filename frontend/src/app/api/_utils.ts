import { NextResponse } from "next/server";

export function ok<T>(data: T) {
  return NextResponse.json({ code: 200, message: "success", data });
}

export function fail(code: number, message: string, status = 400) {
  return NextResponse.json(
    {
      code,
      message,
      data: null,
      requestId: crypto.randomUUID(),
    },
    { status }
  );
}

export function unauthorized() {
  return fail(40101, "未授权", 401);
}

