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
  const [activeCamera, setActiveCamera] = useState<Camera | null>(null);
  const [streamInfo, setStreamInfo] = useState<{ accessToken: string; deviceKey: string; channelNo: number } | null>(null);
  const [streamErr, setStreamErr] = useState<string | null>(null);
  const [streamLoading, setStreamLoading] = useState(false);
  const [playbackMode, setPlaybackMode] = useState(false);
  const [playbackStart, setPlaybackStart] = useState("");
  const [playbackEnd, setPlaybackEnd] = useState("");

  // 录像列表状态
  const [recordings, setRecordings] = useState<{ startTime: string; endTime: string; fileName: string; fileSize: string }[]>([]);
  const [recordingsLoading, setRecordingsLoading] = useState(false);
  const [selectedDate, setSelectedDate] = useState(() => {
    const now = new Date();
    const pad = (n: number) => String(n).padStart(2, "0");
    return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
  });
  // 本地录像播放URL
  const [localVideoUrl, setLocalVideoUrl] = useState<string | null>(null);

  // 录像列表分页
  const [recordingPage, setRecordingPage] = useState(1);
  const RECORDINGS_PER_PAGE = 10;

  // 展开的摄像头ID（用于录像列表）
  const [expandedCameraId, setExpandedCameraId] = useState<number | null>(null);

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
    setStreamInfo(null);
    setActiveCamera(camera);
    setPlaybackMode(false);
    try {
      const res = await apiFetch<{ accessToken: string; deviceKey: string; channelNo: string }>(
        `/api/cameras/${camera.id}/stream`,
        { headers: authHeaders() }
      );
      setStreamInfo({
        accessToken: res.accessToken,
        deviceKey: res.deviceKey,
        channelNo: Number(res.channelNo),
      });
    } catch (e) {
      setStreamErr(e instanceof ApiError ? e.message : e instanceof Error ? e.message : "获取视频流失败");
    } finally {
      setStreamLoading(false);
    }
  }, []);

  const fetchRecordings = useCallback(async (cameraId: number, date: string) => {
    setRecordingsLoading(true);
    setRecordings([]);
    setLocalVideoUrl(null);
    setRecordingPage(1);
    try {
      const res = await apiFetch<{ startTime: string; endTime: string; fileName: string; fileSize: string }[]>(
        `/api/cameras/${cameraId}/recordings/local?date=${encodeURIComponent(date)}`,
        { headers: authHeaders() }
      );
      setRecordings(res ?? []);
    } catch (e) {
      setStreamErr(e instanceof ApiError ? e.message : e instanceof Error ? e.message : "获取录像列表失败");
    } finally {
      setRecordingsLoading(false);
    }
  }, []);

  const openPlayback = useCallback(async (camera: Camera) => {
    // 如果点击已展开的摄像头，则收起
    if (expandedCameraId === camera.id) {
      setExpandedCameraId(null);
      setRecordings([]);
      if (localVideoUrl) URL.revokeObjectURL(localVideoUrl);
      setLocalVideoUrl(null);
      return;
    }
    setStreamErr(null);
    setExpandedCameraId(camera.id);
    setActiveCamera(camera);
    setPlaybackMode(true);
    setPlaybackStart("");
    setPlaybackEnd("");
    if (localVideoUrl) URL.revokeObjectURL(localVideoUrl);
    setLocalVideoUrl(null);
    await fetchRecordings(camera.id, selectedDate);
  }, [selectedDate, fetchRecordings, expandedCameraId, localVideoUrl]);

  const playRecording = useCallback(async (camera: Camera, fileName: string) => {
    setStreamErr(null);
    setStreamInfo(null);
    setStreamLoading(true);
    if (localVideoUrl) URL.revokeObjectURL(localVideoUrl);
    setLocalVideoUrl(null);
    try {
      const url = `/api/cameras/${camera.id}/recordings/local/play?date=${encodeURIComponent(selectedDate)}&file=${encodeURIComponent(fileName)}`;
      const res = await fetch(url, { headers: authHeaders() });
      if (!res.ok) {
        throw new Error(`加载视频失败 (${res.status})`);
      }
      const blob = await res.blob();
      setLocalVideoUrl(URL.createObjectURL(blob));
    } catch (e) {
      setStreamErr(e instanceof Error ? e.message : "视频加载失败");
    } finally {
      setStreamLoading(false);
    }
  }, [selectedDate, localVideoUrl]);

  const closeStream = useCallback(() => {
    setActiveCamera(null);
    setStreamInfo(null);
    setStreamErr(null);
    setPlaybackMode(false);
    setPlaybackStart("");
    setPlaybackEnd("");
    setRecordings([]);
    setExpandedCameraId(null);
    if (localVideoUrl) URL.revokeObjectURL(localVideoUrl);
    setLocalVideoUrl(null);
  }, [localVideoUrl]);

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-semibold">摄像头</h1>
          <p className="text-sm text-zinc-500">可新增、更新、删除，查看实时视频画面与录像回放</p>
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

      {/* 实时视频播放区（非录像回放模式时显示） */}
      {activeCamera !== null && !playbackMode && (
        <div className="rounded-xl border border-zinc-200 bg-white p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="text-sm font-medium">
              {streamLoading ? "正在连接..." : `实时画面 — ${activeCamera.name}`}
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
              正在获取视频流...
            </div>
          ) : streamInfo ? (
            <VideoPlayer
              deviceKey={streamInfo.deviceKey}
              channelNo={streamInfo.channelNo}
              accessToken={streamInfo.accessToken}
              mode="live"
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
              <th className="px-4 py-2 text-center">录像</th>
              <th className="px-4 py-2 text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            {(data?.list ?? []).map((c) => (
              <>
                <tr key={c.id} className="border-t border-zinc-100">
                  <td className="px-4 py-2">{c.id}</td>
                  <td className="px-4 py-2">{c.hamsterId}</td>
                  <td className="px-4 py-2 font-medium">{c.name}</td>
                  <td className="px-4 py-2 font-mono text-xs">{c.deviceKey}</td>
                  <td className="px-4 py-2">{c.onlineStatus === 1 ? "在线" : "离线"}</td>
                  <td className="px-4 py-2 text-center">
                    <button
                      onClick={async () => {
                        try {
                          const res = await apiFetch<{ enabled: boolean }>(`/api/cameras/${c.id}/recording/toggle`, {
                            method: "POST",
                            headers: authHeaders(),
                            json: { enabled: !c.recordingEnabled },
                          });
                          setData((prev) => {
                            if (!prev) return prev;
                            return {
                              ...prev,
                              list: prev.list.map((item) =>
                                item.id === c.id ? { ...item, recordingEnabled: res.enabled } : item
                              ),
                            };
                          });
                        } catch (e) {
                          setErr(e instanceof ApiError ? e.message : e instanceof Error ? e.message : "切换录像状态失败");
                        }
                      }}
                      className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                        c.recordingEnabled ? "bg-emerald-500" : "bg-zinc-300"
                      }`}
                      title={c.recordingEnabled ? "点击关闭录像" : "点击开启录像"}
                    >
                      <span
                        className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                          c.recordingEnabled ? "translate-x-4" : "translate-x-0.5"
                        }`}
                      />
                    </button>
                  </td>
                  <td className="px-4 py-2">
                    <div className="flex justify-end gap-2 flex-wrap">
                      <button
                        className="rounded-md border border-blue-200 text-blue-700 px-2 py-1 text-xs hover:bg-blue-50"
                        onClick={() => openStream(c)}
                      >
                        查看实时画面
                      </button>
                      <button
                        className={`rounded-md border px-2 py-1 text-xs ${
                          expandedCameraId === c.id
                            ? "border-emerald-500 bg-emerald-50 text-emerald-700"
                            : "border-emerald-200 text-emerald-700 hover:bg-emerald-50"
                        }`}
                        onClick={() => openPlayback(c)}
                      >
                        录像回放
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
                {/* 展开的录像列表 */}
                {expandedCameraId === c.id && (
                  <tr>
                    <td colSpan={7} className="bg-zinc-50 px-4 py-3">
                      <div className="space-y-3">
                        {/* 日期选择和视频播放器 */}
                        <div className="flex items-center gap-3">
                          <label className="text-sm text-zinc-600">选择日期：</label>
                          <input
                            type="date"
                            value={selectedDate}
                            onChange={(e) => {
                              setSelectedDate(e.target.value);
                              fetchRecordings(c.id, e.target.value);
                            }}
                            className="rounded-md border border-zinc-200 px-3 py-1.5 text-sm"
                          />
                        </div>

                        {/* 视频播放器 */}
                        {localVideoUrl && (
                          <div className="space-y-2">
                            <div className="flex justify-start">
                              <button
                                className="rounded-md border border-zinc-200 px-3 py-1 text-xs hover:bg-zinc-50"
                                onClick={() => {
                                  if (localVideoUrl) URL.revokeObjectURL(localVideoUrl);
                                  setLocalVideoUrl(null);
                                }}
                              >
                                关闭视频
                              </button>
                            </div>
                            <video
                              src={localVideoUrl}
                              controls
                              autoPlay
                              className="rounded-lg max-w-full"
                              style={{ maxHeight: 360 }}
                              onError={() => setStreamErr("视频播放失败")}
                            >
                              您的浏览器不支持视频播放
                            </video>
                          </div>
                        )}

                        {/* 录像列表 */}
                        {recordingsLoading ? (
                          <div className="flex items-center justify-center h-20 text-sm text-zinc-500">
                            <svg className="animate-spin h-4 w-4 mr-2 text-zinc-400" viewBox="0 0 24 24">
                              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                            </svg>
                            正在查询录像列表...
                          </div>
                        ) : recordings.length > 0 ? (
                          <div className="space-y-2">
                            <div className="rounded-md border border-zinc-200 bg-white">
                              <table className="w-full text-xs">
                                <thead className="bg-zinc-50 text-zinc-500">
                                  <tr>
                                    <th className="px-3 py-1.5 text-left">序号</th>
                                    <th className="px-3 py-1.5 text-left">开始时间</th>
                                    <th className="px-3 py-1.5 text-left">结束时间</th>
                                    <th className="px-3 py-1.5 text-left">时长</th>
                                    <th className="px-3 py-1.5 text-right">操作</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {recordings.slice((recordingPage - 1) * RECORDINGS_PER_PAGE, recordingPage * RECORDINGS_PER_PAGE).map((r, i) => {
                                    const toSec = (t: string) => {
                                      const [h, m, s] = t.split(":").map(Number);
                                      return h * 3600 + m * 60 + s;
                                    };
                                    const dur = Math.max(0, toSec(r.endTime) - toSec(r.startTime));
                                    const mm = String(Math.floor(dur / 60)).padStart(2, "0");
                                    const ss = String(dur % 60).padStart(2, "0");
                                    const globalIndex = (recordingPage - 1) * RECORDINGS_PER_PAGE + i + 1;
                                    return (
                                      <tr key={r.fileName} className="border-t border-zinc-50 hover:bg-zinc-50">
                                        <td className="px-3 py-1.5">{globalIndex}</td>
                                        <td className="px-3 py-1.5 font-mono">{r.startTime}</td>
                                        <td className="px-3 py-1.5 font-mono">{r.endTime}</td>
                                        <td className="px-3 py-1.5 font-mono">{mm}:{ss}</td>
                                        <td className="px-3 py-1.5 text-right space-x-1">
                                          <button
                                            className="rounded-md border border-emerald-200 text-emerald-700 px-2 py-0.5 text-xs hover:bg-emerald-50"
                                            onClick={() => playRecording(c, r.fileName)}
                                          >
                                            播放
                                          </button>
                                          <button
                                            className="rounded-md border border-red-200 text-red-700 px-2 py-0.5 text-xs hover:bg-red-50"
                                            onClick={async () => {
                                              try {
                                                await apiFetch(`/api/cameras/${c.id}/recordings/local?date=${encodeURIComponent(selectedDate)}&file=${encodeURIComponent(r.fileName)}`, {
                                                  method: "DELETE",
                                                  headers: authHeaders(),
                                                });
                                                setRecordings((prev) => prev.filter((item) => item.fileName !== r.fileName));
                                              } catch (e) {
                                                setStreamErr(e instanceof ApiError ? e.message : e instanceof Error ? e.message : "删除失败");
                                              }
                                            }}
                                          >
                                            删除
                                          </button>
                                        </td>
                                      </tr>
                                    );
                                  })}
                                </tbody>
                              </table>
                            </div>
                            {/* 分页控件 */}
                            {recordings.length > RECORDINGS_PER_PAGE && (
                              <div className="flex items-center justify-between text-xs text-zinc-500">
                                <span>共 {recordings.length} 条，第 {recordingPage}/{Math.ceil(recordings.length / RECORDINGS_PER_PAGE)} 页</span>
                                <div className="flex gap-1">
                                  <button
                                    disabled={recordingPage <= 1}
                                    onClick={() => setRecordingPage((p) => Math.max(1, p - 1))}
                                    className="rounded border border-zinc-200 px-2 py-0.5 hover:bg-zinc-50 disabled:opacity-40"
                                  >
                                    上一页
                                  </button>
                                  <button
                                    disabled={recordingPage >= Math.ceil(recordings.length / RECORDINGS_PER_PAGE)}
                                    onClick={() => setRecordingPage((p) => p + 1)}
                                    className="rounded border border-zinc-200 px-2 py-0.5 hover:bg-zinc-50 disabled:opacity-40"
                                  >
                                    下一页
                                  </button>
                                </div>
                              </div>
                            )}
                          </div>
                        ) : (
                          <div className="text-center text-sm text-zinc-400 py-4">
                            该日期暂无录像记录
                          </div>
                        )}
                      </div>
                    </td>
                  </tr>
                )}
              </>
            ))}
            {!data?.list?.length ? (
              <tr>
                <td className="px-4 py-6 text-zinc-500" colSpan={7}>
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
