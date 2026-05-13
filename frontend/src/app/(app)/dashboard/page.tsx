"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/http";
import { authHeaders } from "@/lib/authed";
import type { User } from "@/lib/types";

export default function DashboardPage() {
  const [me, setMe] = useState<User | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<User>("/api/auth/me", { headers: authHeaders() })
      .then(setMe)
      .catch((e) => setErr(e instanceof Error ? e.message : "加载失败"));
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">仪表盘</h1>
        <p className="text-sm text-zinc-500">
          前端经 Next Route 代理至 Spring Boot（默认 <code className="text-xs">127.0.0.1:8081</code>，可用环境变量
          <code className="text-xs"> BACKEND_URL </code>覆盖）。
        </p>
      </div>

      {err ? (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {err}
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <div className="rounded-xl border border-zinc-200 bg-white p-4">
          <div className="text-xs text-zinc-500">当前用户</div>
          <div className="mt-1 text-sm font-medium">{me ? me.username : "加载中..."}</div>
          <div className="mt-1 text-xs text-zinc-500">{me?.email ?? ""}</div>
        </div>
        <div className="rounded-xl border border-zinc-200 bg-white p-4">
          <div className="text-xs text-zinc-500">状态口径</div>
          <div className="mt-1 text-sm font-medium">normal / low / high</div>
          <div className="mt-1 text-xs text-zinc-500">与 docs 保持一致</div>
        </div>
        <div className="rounded-xl border border-zinc-200 bg-white p-4">
          <div className="text-xs text-zinc-500">删除策略</div>
          <div className="mt-1 text-sm font-medium">软删除</div>
          <div className="mt-1 text-xs text-zinc-500">isDeleted + deletedAt</div>
        </div>
      </div>
    </div>
  );
}

