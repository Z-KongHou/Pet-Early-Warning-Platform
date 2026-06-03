"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/http";
import { setToken } from "@/lib/auth-client";

export default function LoginPage() {
  const router = useRouter();
  const [isRegister, setIsRegister] = useState(false);

  // 登录表单
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("password123");

  // 注册表单
  const [regUsername, setRegUsername] = useState("");
  const [regEmail, setRegEmail] = useState("");
  const [regPassword, setRegPassword] = useState("");
  const [regConfirmPassword, setRegConfirmPassword] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // 登录
  const handleLogin = async (e: React.FormEvent) => {
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
  };

  // 注册
  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    // 密码长度校验
    if (regPassword.length < 6 || regPassword.length > 18) {
      setError("密码长度需为6~18位");
      return;
    }

    // 两次密码一致性校验
    if (regPassword !== regConfirmPassword) {
      setError("两次密码输入不一致，请重试！");
      return;
    }

    setLoading(true);
    try {
      const regResult = await apiFetch<{ token: string }>("/api/auth/register", {
        method: "POST",
        json: { username: regUsername, password: regPassword, email: regEmail },
      });
      // 注册成功，直接使用返回的 token 登录
      setToken(regResult.token);
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "注册失败");
    } finally {
      setLoading(false);
    }
  };

  // 切换登录/注册
  const toggleMode = () => {
    setIsRegister(!isRegister);
    setError(null);
    setSuccess(null);
  };

  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-6 shadow-sm">
      <div className="mb-6">
        <h1 className="text-lg font-semibold">{isRegister ? "注册" : "登录"}</h1>
        <p className="text-sm text-zinc-500">仓鼠健康预警 AIoT 系统（Demo）</p>
      </div>

      {/* 登录表单 */}
      {!isRegister ? (
        <form className="space-y-4" onSubmit={handleLogin}>
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

          <div className="text-center text-sm text-zinc-500">
            还没有账号？
            <button
              type="button"
              onClick={toggleMode}
              className="ml-1 text-zinc-900 font-medium hover:underline"
            >
              立即注册
            </button>
          </div>
        </form>
      ) : (
        /* 注册表单 */
        <form className="space-y-4" onSubmit={handleRegister}>
          <div>
            <label className="text-sm text-zinc-600">账号</label>
            <input
              className="mt-1 w-full rounded-md border border-zinc-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-zinc-900/20"
              value={regUsername}
              onChange={(e) => setRegUsername(e.target.value)}
              placeholder="请输入账号"
            />
          </div>
          <div>
            <label className="text-sm text-zinc-600">邮箱</label>
            <input
              type="email"
              className="mt-1 w-full rounded-md border border-zinc-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-zinc-900/20"
              value={regEmail}
              onChange={(e) => setRegEmail(e.target.value)}
              placeholder="请输入邮箱"
            />
          </div>
          <div>
            <label className="text-sm text-zinc-600">密码</label>
            <input
              type="password"
              className="mt-1 w-full rounded-md border border-zinc-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-zinc-900/20"
              value={regPassword}
              onChange={(e) => setRegPassword(e.target.value)}
              placeholder="6~18位密码"
            />
          </div>
          <div>
            <label className="text-sm text-zinc-600">请确认密码</label>
            <input
              type="password"
              className="mt-1 w-full rounded-md border border-zinc-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-zinc-900/20"
              value={regConfirmPassword}
              onChange={(e) => setRegConfirmPassword(e.target.value)}
              placeholder="再次输入密码"
            />
          </div>

          {error ? (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          ) : null}

          {success ? (
            <div className="rounded-md border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700">
              {success}
            </div>
          ) : null}

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-md bg-zinc-900 px-3 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-60"
          >
            {loading ? "注册中..." : "注册"}
          </button>

          <div className="text-center text-sm text-zinc-500">
            已有账号？
            <button
              type="button"
              onClick={toggleMode}
              className="ml-1 text-zinc-900 font-medium hover:underline"
            >
              返回登录
            </button>
          </div>
        </form>
      )}

      {!isRegister && (
        <div className="mt-6 text-xs text-zinc-500">
          Demo 账号：<span className="font-mono">admin</span> /{" "}
          <span className="font-mono">password123</span>
        </div>
      )}
    </div>
  );
}
