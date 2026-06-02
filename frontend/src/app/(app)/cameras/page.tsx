"use client";

import { Fragment, useCallback, useEffect, useRef, useState } from "react";
import { HamsterLiveAnalysis } from "@/components/HamsterLiveAnalysis";
import { RefreshButton } from "@/components/RefreshButton";
import { VideoPlayer, type EZUIKitPlayerInstance } from "@/components/VideoPlayer";
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
  const [recordings, setRecordings] = useState<{ fileId: string; startTime: string; endTime: string; fileSize: number; videoLong: number; deviceSerial: string; channelNo: string }[]>([]);
  const [recordingsLoading, setRecordingsLoading] = useState(false);
  const [selectedDate, setSelectedDate] = useState(() => {
    const now = new Date();
    const pad = (n: number) => String(n).padStart(2, "0");
    return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
  });
  // 云录像播放状态
  const [cloudPlaybackInfo, setCloudPlaybackInfo] = useState<{ url: string; accessToken: string; deviceKey: string; channelNo: number; playType?: string } | null>(null);

  // 录像列表分页
  const [recordingPage, setRecordingPage] = useState(1);
  const RECORDINGS_PER_PAGE = 10;

  // 展开的摄像头ID（用于录像列表）
  const [expandedCameraId, setExpandedCameraId] = useState<number | null>(null);

  // 模板列表
  const [templates, setTemplates] = useState<{ templateId: number; templateName: string; format: string; spaceId: number; spaceName: string }[]>([]);
  const [showTemplates, setShowTemplates] = useState(false);

  const playerRef = useRef<EZUIKitPlayerInstance | null>(null);
  const liveVideoColRef = useRef<HTMLDivElement>(null);
  const [analysisPanelMaxH, setAnalysisPanelMaxH] = useState<number | undefined>(undefined);

  useEffect(() => {
    refresh().catch((e) => setErr(e instanceof Error ? e.message : "加载失败"));
  }, []);

  useEffect(() => {
    const el = liveVideoColRef.current;
    if (!el || !streamInfo) {
      setAnalysisPanelMaxH(undefined);
      return;
    }
    const syncHeight = () => setAnalysisPanelMaxH(el.offsetHeight);
    syncHeight();
    const ro = new ResizeObserver(syncHeight);
    ro.observe(el);
    return () => ro.disconnect();
  }, [streamInfo, streamLoading]);

  async function refresh() {
    const d = await apiFetch<Pagination<Camera>>("/api/cameras?page=1&size=20", { headers: authHeaders() });
    setData(d);
  }

  async function fetchTemplates() {
    try {
      const res = await apiFetch<{ templateId: number; templateName: string; format: string; spaceId: number; spaceName: string }[]>(
        "/api/templates",
        { headers: authHeaders() }
      );
      setTemplates(res ?? []);
      setShowTemplates(true);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : e instanceof Error ? e.message : "获取模板列表失败");
    }
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
    setCloudPlaybackInfo(null);
    setRecordingPage(1);
    try {
      const res = await apiFetch<{ fileId: string; startTime: string; endTime: string; fileSize: number; videoLong: number; deviceSerial: string; channelNo: string }[]>(
        `/api/cameras/${cameraId}/recordings/cloud?date=${encodeURIComponent(date)}`,
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
    if (expandedCameraId === camera.id) {
      setExpandedCameraId(null);
      setRecordings([]);
      setCloudPlaybackInfo(null);
      return;
    }
    setStreamErr(null);
    setExpandedCameraId(camera.id);
    setActiveCamera(camera);
    setPlaybackMode(true);
    setPlaybackStart("");
    setPlaybackEnd("");
    setCloudPlaybackInfo(null);
    await fetchRecordings(camera.id, selectedDate);
  }, [selectedDate, fetchRecordings, expandedCameraId]);

  const playRecording = useCallback(async (camera: Camera, startTime: string, endTime: string) => {
    setStreamErr(null);
    setStreamInfo(null);
    setStreamLoading(true);
    setCloudPlaybackInfo(null);
    try {
      const res = await apiFetch<{ url: string; accessToken: string; deviceKey: string; channelNo: number; playType?: string }>(
        `/api/cameras/${camera.id}/recordings/cloud/play?startTime=${encodeURIComponent(startTime)}&endTime=${encodeURIComponent(endTime)}`,
        { headers: authHeaders() }
      );
      setCloudPlaybackInfo({
        url: res.url,
        accessToken: res.accessToken,
        deviceKey: res.deviceKey,
        channelNo: Number(res.channelNo),
        playType: res.playType,
      });
    } catch (e) {
      setStreamErr(e instanceof ApiError ? e.message : e instanceof Error ? e.message : "获取播放地址失败");
    } finally {
      setStreamLoading(false);
    }
  }, []);

  const closeStream = useCallback(() => {
    playerRef.current = null;
    setActiveCamera(null);
    setStreamInfo(null);
    setStreamErr(null);
    setPlaybackMode(false);
    setPlaybackStart("");
    setPlaybackEnd("");
    setRecordings([]);
    setExpandedCameraId(null);
    setCloudPlaybackInfo(null);
  }, []);

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-semibold">摄像头</h1>
          <p className="text-sm text-zinc-500">可新增、更新、删除，查看实时视频画面与录像回放</p>
        </div>
        <div className="flex gap-2">
          <button
            className="rounded-md border border-zinc-200 px-3 py-2 text-sm hover:bg-zinc-50"
            onClick={fetchTemplates}
          >
            查看后处理模板
          </button>
          <RefreshButton onRefresh={refresh} />
        </div>
      </div>

      {err ? (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {err}
        </div>
      ) : null}

      {/* 后处理模板列表 */}
      {showTemplates && (
        <div className="rounded-xl border border-zinc-200 bg-white p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="text-sm font-medium">后处理模板</div>
            <button
              className="rounded-md border border-zinc-200 px-2 py-1 text-xs hover:bg-zinc-50"
              onClick={() => setShowTemplates(false)}
            >
              关闭
            </button>
          </div>
          {templates.length > 0 ? (
            <div className="rounded-md border border-zinc-200 overflow-hidden">
              <table className="w-full text-xs">
                <thead className="bg-zinc-50 text-zinc-500">
                  <tr>
                    <th className="px-3 py-1.5 text-left">模板ID</th>
                    <th className="px-3 py-1.5 text-left">模板名称</th>
                    <th className="px-3 py-1.5 text-left">格式</th>
                    <th className="px-3 py-1.5 text-left">空间ID</th>
                    <th className="px-3 py-1.5 text-left">空间名称</th>
                  </tr>
                </thead>
                <tbody>
                  {templates.map((t) => (
                    <tr key={t.templateId} className="border-t border-zinc-50">
                      <td className="px-3 py-1.5 font-mono">{t.templateId}</td>
                      <td className="px-3 py-1.5">{t.templateName}</td>
                      <td className="px-3 py-1.5">{t.format}</td>
                      <td className="px-3 py-1.5 font-mono">{t.spaceId}</td>
                      <td className="px-3 py-1.5">{t.spaceName}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="text-center text-sm text-zinc-400 py-4">暂无模板</div>
          )}
        </div>
      )}

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
            <div className="flex flex-col lg:flex-row lg:items-start gap-4">
              <div
                ref={liveVideoColRef}
                className="flex-1 min-w-0 w-full aspect-video rounded-lg overflow-hidden bg-black"
              >
                <VideoPlayer
                  deviceKey={streamInfo.deviceKey}
                  channelNo={streamInfo.channelNo}
                  accessToken={streamInfo.accessToken}
                  mode="live"
                  playerRef={playerRef}
                  onError={setStreamErr}
                />
              </div>
              {activeCamera && (
                <HamsterLiveAnalysis
                  cameraId={activeCamera.id}
                  playerRef={playerRef}
                  maxHeight={analysisPanelMaxH}
                />
              )}
            </div>
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
              <Fragment key={c.id}>
                <tr className="border-t border-zinc-100">
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

                        {/* 云录像播放器 */}
                        {cloudPlaybackInfo && (
                          <div className="space-y-2">
                            <div className="flex justify-start">
                              <button
                                className="rounded-md border border-zinc-200 px-3 py-1 text-xs hover:bg-zinc-50"
                                onClick={() => setCloudPlaybackInfo(null)}
                              >
                                关闭视频
                              </button>
                            </div>
                            <div className="aspect-video rounded-lg overflow-hidden bg-black max-w-2xl">
                              {cloudPlaybackInfo.playType === "vod" ? (
                                // 云点播 mp4 直接播放
                                <video
                                  src={cloudPlaybackInfo.url}
                                  controls
                                  autoPlay
                                  className="w-full h-full"
                                />
                              ) : (
                                // ezopen:// 协议使用 EZUIKit 播放
                                <VideoPlayer
                                  deviceKey={cloudPlaybackInfo.deviceKey}
                                  channelNo={cloudPlaybackInfo.channelNo}
                                  accessToken={cloudPlaybackInfo.accessToken}
                                  mode="live"
                                  customUrl={cloudPlaybackInfo.url}
                                  playerRef={playerRef}
                                  onError={setStreamErr}
                                />
                              )}
                            </div>
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
                                    const durSec = r.videoLong ? Math.round(r.videoLong / 1000) : 0;
                                    const mm = String(Math.floor(durSec / 60)).padStart(2, "0");
                                    const ss = String(durSec % 60).padStart(2, "0");
                                    const globalIndex = (recordingPage - 1) * RECORDINGS_PER_PAGE + i + 1;
                                    return (
                                      <tr key={r.fileId} className="border-t border-zinc-50 hover:bg-zinc-50">
                                        <td className="px-3 py-1.5">{globalIndex}</td>
                                        <td className="px-3 py-1.5 font-mono">{r.startTime}</td>
                                        <td className="px-3 py-1.5 font-mono">{r.endTime}</td>
                                        <td className="px-3 py-1.5 font-mono">{mm}:{ss}</td>
                                        <td className="px-3 py-1.5 text-right space-x-1">
                                          <button
                                            className="rounded-md border border-emerald-200 text-emerald-700 px-2 py-0.5 text-xs hover:bg-emerald-50"
                                            onClick={() => playRecording(c, r.startTime, r.endTime)}
                                          >
                                            播放
                                          </button>
                                          <button
                                            className="rounded-md border border-red-200 text-red-700 px-2 py-0.5 text-xs hover:bg-red-50"
                                            onClick={async () => {
                                              try {
                                                await apiFetch(`/api/cameras/${c.id}/recordings/cloud?startTime=${encodeURIComponent(r.startTime)}&endTime=${encodeURIComponent(r.endTime)}`, {
                                                  method: "DELETE",
                                                  headers: authHeaders(),
                                                });
                                                setRecordings((prev) => prev.filter((item) => item.fileId !== r.fileId));
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
                                <span>共 {recordings.length} 条</span>
                                <div className="flex items-center gap-2">
                                  <span>第</span>
                                  <input
                                    type="number"
                                    min={1}
                                    max={Math.ceil(recordings.length / RECORDINGS_PER_PAGE)}
                                    value={recordingPage}
                                    onChange={(e) => {
                                      const v = parseInt(e.target.value);
                                      if (!isNaN(v) && v >= 1 && v <= Math.ceil(recordings.length / RECORDINGS_PER_PAGE)) {
                                        setRecordingPage(v);
                                      }
                                    }}
                                    onKeyDown={(e) => {
                                      if (e.key === 'Enter') {
                                        const v = parseInt((e.target as HTMLInputElement).value);
                                        if (!isNaN(v) && v >= 1 && v <= Math.ceil(recordings.length / RECORDINGS_PER_PAGE)) {
                                          setRecordingPage(v);
                                        }
                                      }
                                    }}
                                    className="w-10 rounded border border-zinc-300 px-1 py-0.5 text-center text-xs"
                                  />
                                  <span>/ {Math.ceil(recordings.length / RECORDINGS_PER_PAGE)} 页</span>
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
              </Fragment>
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
