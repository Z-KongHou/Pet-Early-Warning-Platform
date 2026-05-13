"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getToken } from "@/lib/auth-client";

/**
 * 不能在首屏 render 中直接读 localStorage：服务端无 window，会与客户端有水合差异。
 * 首帧与服务端一致渲染占位，mount 后再读 token 并跳转或展示子树。
 */
export function RequireAuth({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [mounted, setMounted] = useState(false);
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    setMounted(true);
    setToken(getToken());
  }, []);

  useEffect(() => {
    if (!mounted) return;
    if (!token) router.replace("/login");
  }, [mounted, token, router]);

  if (!mounted) {
    return (
      <div className="flex min-h-dvh items-center justify-center bg-zinc-50 text-sm text-zinc-500">
        加载中…
      </div>
    );
  }

  if (!token) return null;
  return <>{children}</>;
}

