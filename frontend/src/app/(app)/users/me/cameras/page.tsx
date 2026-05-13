"use client";

import { useCallback, useEffect, useState } from "react";
import { RefreshButton } from "@/components/RefreshButton";
import { apiFetch } from "@/lib/http";
import { authHeaders } from "@/lib/authed";
import type { Pagination, UserCameraBinding } from "@/lib/types";

export default function MyCamerasPage() {
  const [data, setData] = useState<Pagination<UserCameraBinding> | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [cameraId, setCameraId] = useState("1");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    const d = await apiFetch<Pagination<UserCameraBinding>>("/api/users/me/cameras?page=1&size=20", {
      headers: authHeaders(),
    });
    setData(d);
  }, []);

  useEffect(() => {
    (async () => {
      try {
        await refresh();
      } catch (e) {
        setErr(e instanceof Error ? e.message : "加载失败");
      }
    })();
  }, [refresh]);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">我的摄像头</h1>
        <p className="text-sm text-zinc-500">来自后端 `GET /api/users/me/cameras`（绑定关系）</p>
      </div>

      {err ? (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {err}
        </div>
      ) : null}

      <div className="rounded-xl border border-zinc-200 bg-white p-4">
        <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div className="flex gap-3 items-end">
            <div>
              <label className="text-sm text-zinc-600">cameraId</label>
              <input
                value={cameraId}
                onChange={(e) => setCameraId(e.target.value)}
                className="mt-1 w-40 rounded-md border border-zinc-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-zinc-900/20"
              />
            </div>
            <button
              className="rounded-md bg-zinc-900 px-3 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-60"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  await apiFetch("/api/users/me/cameras/bind", {
                    method: "POST",
                    headers: authHeaders(),
                    json: { cameraId: Number(cameraId) },
                  });
                  await refresh();
                } finally {
                  setBusy(false);
                }
              }}
            >
              绑定
            </button>
            <button
              className="rounded-md border border-zinc-200 px-3 py-2 text-sm hover:bg-zinc-50 disabled:opacity-60"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  await apiFetch("/api/users/me/cameras/unbind", {
                    method: "POST",
                    headers: authHeaders(),
                    json: { cameraId: Number(cameraId) },
                  });
                  await refresh();
                } finally {
                  setBusy(false);
                }
              }}
            >
              解绑
            </button>
          </div>
          <RefreshButton onRefresh={refresh} />
        </div>
      </div>

      <div className="rounded-xl border border-zinc-200 bg-white overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-zinc-50 text-zinc-600">
            <tr>
              <th className="px-4 py-2 text-left">cameraId</th>
              <th className="px-4 py-2 text-left">名称</th>
              <th className="px-4 py-2 text-left">在线</th>
            </tr>
          </thead>
          <tbody>
            {(data?.list ?? []).map((c) => (
              <tr key={c.cameraId} className="border-t border-zinc-100">
                <td className="px-4 py-2">{c.cameraId}</td>
                <td className="px-4 py-2 font-medium">{c.name}</td>
                <td className="px-4 py-2">{c.onlineStatus === 1 ? "在线" : "离线"}</td>
              </tr>
            ))}
            {!data?.list?.length ? (
              <tr>
                <td className="px-4 py-6 text-zinc-500" colSpan={3}>
                  暂无数据
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}

