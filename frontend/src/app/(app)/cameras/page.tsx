"use client";

import { useCallback, useEffect, useState } from "react";
import { RefreshButton } from "@/components/RefreshButton";
import { VideoPlayer } from "@/components/VideoPlayer";
import { ApiError, apiFetch } from "@/lib/http";
import { authHeaders } from "@/lib/authed";
import type { Camera, Pagination } from "@/lib/types";

export default function CamerasPage() {
  const [data, setData] = useState<Pagination<Camera> | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [create, setCreate] = useState({ hamsterId: "1", name: "", deviceKey: "", channelNo: "1" });

  // 视频播放状态
  const [streamUrl, setStreamUrl] = useState<string | null>(null);
  const [streamProtocol, setStreamProtocol] = useState<string | null>(null);
  const [streamCameraName, setStreamCameraName] = useState<string>("");
  const [streamErr, setStreamErr] = useState<string | null>(null);
  const [streamLoading, setStreamLoading] = useState(false);

  useEffect(() => {
    refresh().catch((e) => setErr(e instanceof Error ? e.message : "加载失败"));
  }, []);

  async function refresh() {
    const d = await apiFetch<Pagination<Camera>>("/api/cameras?page=1&size=20", { headers: authHeaders() });
    setData(d);
  }

  const openStream = useCallback(async (camera: Camera) => {
    setStreamErr(null);
    setStreamLoading(true);
    setStreamUrl(null);
    setStreamCameraName(camera.name);
    try {
      const res = await apiFetch<{ streamUrl: string; protocol: string }>(
        `/api/cameras/${camera.id}/stream`,
        { headers: authHeaders() }
      );
      setStreamUrl(res.streamUrl);
      setStreamProtocol(res.protocol);
    } catch (e) {
      setStreamErr(e instanceof ApiError ? e.message : e instanceof Error ? e.message : "获取视频流失败");
    } finally {
      setStreamLoading(false);
    }
  }, []);

  const closeStream = useCallback(() => {
    setStreamUrl(null);
    setStreamProtocol(null);
    setStreamErr(null);
    setStreamCameraName("");
  }, []);

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-semibold">摄像头</h1>
          <p className="text-sm text-zinc-500">可新增、更新、删除，并查看实时视频画面</p>
        </div>
        <RefreshButton onRefresh={refresh} />
      </div>

      {err ? (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {err}
        </div>
      ) : null}

      {/* 新增摄像头表单 */}
      <div className="rounded-xl border border-zinc-200 bg-white p-4">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-5">
          <div>
            <label className="text-sm text-zinc-600">hamsterId</label>
            <input
              value={create.hamsterId}
              onChange={(e) => setCreate({ ...create, hamsterId: e.target.value })}
              className="mt-1 w-full rounded-md border border-zinc-200 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="text-sm text-zinc-600">name</label>
            <input
              value={create.name}
              onChange={(e) => setCreate({ ...create, name: e.target.value })}
              className="mt-1 w-full rounded-md border border-zinc-200 px-3 py-2 text-sm"
              placeholder="例如 客厅摄像头"
            />
          </div>
          <div>
            <label className="text-sm text-zinc-600">deviceKey</label>
            <input
              value={create.deviceKey}
              onChange={(e) => setCreate({ ...create, deviceKey: e.target.value })}
              className="mt-1 w-full rounded-md border border-zinc-200 px-3 py-2 text-sm font-mono"
              placeholder="例如 C8680..."
            />
          </div>
          <div>
            <label className="text-sm text-zinc-600">channelNo</label>
            <input
              value={create.channelNo}
              onChange={(e) => setCreate({ ...create, channelNo: e.target.value })}
              className="mt-1 w-full rounded-md border border-zinc-200 px-3 py-2 text-sm"
            />
          </div>
          <div className="flex items-end">
            <button
              disabled={busy}
              className="w-full rounded-md bg-zinc-900 px-3 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-60"
              onClick={async () => {
                setErr(null);
                setBusy(true);
                try {
                  await apiFetch("/api/cameras", {
                    method: "POST",
                    headers: authHeaders(),
                    json: {
                      hamsterId: Number(create.hamsterId),
                      name: create.name,
                      deviceKey: create.deviceKey,
                      channelNo: Number(create.channelNo),
                    },
                  });
                  setCreate({ hamsterId: "1", name: "", deviceKey: "", channelNo: "1" });
                  await refresh();
                } catch (e) {
                  setErr(e instanceof ApiError ? e.message : e instanceof Error ? e.message : "新增失败");
                } finally {
                  setBusy(false);
                }
              }}
            >
              新增摄像头
            </button>
          </div>
        </div>
      </div>

      {/* 实时视频播放区 */}
      {(streamUrl || streamErr || streamLoading) && (
        <div className="rounded-xl border border-zinc-200 bg-white p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="text-sm font-medium">
              {streamLoading ? "正在连接..." : `实时画面 — ${streamCameraName}`}
            </div>
            <button
              className="rounded-md border border-zinc-200 px-2 py-1 text-xs hover:bg-zinc-50"
              onClick={closeStream}
            >
              关闭
            </button>
          </div>
          {streamErr ? (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {streamErr}
            </div>
          ) : streamLoading ? (
            <div className="flex items-center justify-center h-64 text-sm text-zinc-500">
              <svg className="animate-spin h-5 w-5 mr-2 text-zinc-400" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              正在获取视频流地址...
            </div>
          ) : streamUrl ? (
            <VideoPlayer
              streamUrl={streamUrl}
              protocol={streamProtocol ?? undefined}
              onError={setStreamErr}
            />
          ) : null}
        </div>
      )}

      {/* 摄像头列表 */}
      <div className="rounded-xl border border-zinc-200 bg-white overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-zinc-50 text-zinc-600">
            <tr>
              <th className="px-4 py-2 text-left">ID</th>
              <th className="px-4 py-2 text-left">仓鼠ID</th>
              <th className="px-4 py-2 text-left">名称</th>
              <th className="px-4 py-2 text-left">设备序列号</th>
              <th className="px-4 py-2 text-left">在线</th>
              <th className="px-4 py-2 text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            {(data?.list ?? []).map((c) => (
              <tr key={c.id} className="border-t border-zinc-100">
                <td className="px-4 py-2">{c.id}</td>
                <td className="px-4 py-2">{c.hamsterId}</td>
                <td className="px-4 py-2 font-medium">{c.name}</td>
                <td className="px-4 py-2 font-mono text-xs">{c.deviceKey}</td>
                <td className="px-4 py-2">{c.onlineStatus === 1 ? "在线" : "离线"}</td>
                <td className="px-4 py-2">
                  <div className="flex justify-end gap-2 flex-wrap">
                    <button
                      className="rounded-md border border-blue-200 text-blue-700 px-2 py-1 text-xs hover:bg-blue-50"
                      onClick={() => openStream(c)}
                    >
                      查看实时画面
                    </button>
                    <button
                      className="rounded-md border border-red-200 text-red-700 px-2 py-1 text-xs hover:bg-red-50"
                      onClick={async () => {
                        await apiFetch(`/api/cameras/${c.id}`, { method: "DELETE", headers: authHeaders() });
                        await refresh();
                      }}
                    >
                      删除
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {!data?.list?.length ? (
              <tr>
                <td className="px-4 py-6 text-zinc-500" colSpan={6}>
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
