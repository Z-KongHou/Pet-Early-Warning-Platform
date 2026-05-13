import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  if (pathname.startsWith("/login") || pathname.startsWith("/api/")) return NextResponse.next();
  // Demo：鉴权在客户端用 localStorage，这里只做最小守卫（避免直接访问 /login 外页面时空白）
  // 若需要服务端鉴权，可改为基于 cookie。
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};

