"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/http";
import { setToken } from "@/lib/auth-client";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("password123");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-6 shadow-sm">
      <div className="mb-6">
        <h1 className="text-lg font-semibold">登录</h1>
        <p className="text-sm text-zinc-500">仓鼠健康预警 AIoT 系统（Demo）</p>
      </div>

      <form
        className="space-y-4"
        onSubmit={async (e) => {
          e.preventDefault();
          setError(null);
          setLoading(true);
          try {
            const data = await apiFetch<{ token: string; expiresIn: number }>("/api/auth/login", {
              method: "POST",
              json: { username, password },
            });
            setToken(data.token);
            router.replace("/dashboard");
          } catch (err) {
            setError(err instanceof Error ? err.message : "登录失败");
          } finally {
            setLoading(false);
          }
        }}
      >
        <div>
          <label className="text-sm text-zinc-600">用户名</label>
          <input
            className="mt-1 w-full rounded-md border border-zinc-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-zinc-900/20"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
        </div>
        <div>
          <label className="text-sm text-zinc-600">密码</label>
          <input
            type="password"
            className="mt-1 w-full rounded-md border border-zinc-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-zinc-900/20"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>

        {error ? (
          <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-md bg-zinc-900 px-3 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-60"
        >
          {loading ? "登录中..." : "登录"}
        </button>
      </form>

      <div className="mt-6 text-xs text-zinc-500">
        Demo 账号：<span className="font-mono">admin</span> /{" "}
        <span className="font-mono">password123</span>
      </div>
    </div>
  );
}

