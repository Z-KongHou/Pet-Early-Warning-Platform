"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { RefreshButton } from "@/components/RefreshButton";
import { apiFetch } from "@/lib/http";
import { authHeaders } from "@/lib/authed";
import type { ActivityHistory, Alert, Pagination } from "@/lib/types";

export default function ActivityPage() {
  const [hamsterId, setHamsterId] = useState("1");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [actPage, setActPage] = useState(1);
  const [actSize, setActSize] = useState(20);

  const [activityData, setActivityData] = useState<Pagination<ActivityHistory> | null>(null);
  const [activityErr, setActivityErr] = useState<string | null>(null);

  const [statsPeriod, setStatsPeriod] = useState("week");
  const [statsJson, setStatsJson] = useState<string | null>(null);
  const [trendPeriod, setTrendPeriod] = useState("day");
  const [trendDays, setTrendDays] = useState(7);
  const [trendJson, setTrendJson] = useState<string | null>(null);

  const [alertsData, setAlertsData] = useState<Pagination<Alert> | null>(null);
  const [alertsErr, setAlertsErr] = useState<string | null>(null);
  const [alertStatus, setAlertStatus] = useState("");
  const [busy, setBusy] = useState(false);

  const activityQuery = useMemo(() => {
    const params = new URLSearchParams({
      page: String(actPage),
      size: String(actSize),
    });
    const id = hamsterId.trim();
    if (id) params.set("hamsterId", id);
    if (startDate.trim()) params.set("startDate", startDate.trim());
    if (endDate.trim()) params.set("endDate", endDate.trim());
    return `/api/activity/history?${params.toString()}`;
  }, [hamsterId, startDate, endDate, actPage, actSize]);

  const alertsQuery = useMemo(() => {
    const params = new URLSearchParams({ page: "1", size: "20" });
    const id = hamsterId.trim();
    if (id) params.set("hamsterId", id);
    if (alertStatus !== "") params.set("status", alertStatus);
    return `/api/alerts?${params.toString()}`;
  }, [hamsterId, alertStatus]);

  const refreshActivity = useCallback(async () => {
    const id = hamsterId.trim();
    if (!id) {
      setActivityErr("请填写仓鼠 ID 后再查询活动记录");
      setActivityData(null);
      return;
    }
    setActivityErr(null);
    const d = await apiFetch<Pagination<ActivityHistory>>(activityQuery, { headers: authHeaders() });
    setActivityData(d);
  }, [activityQuery, hamsterId]);

  const refreshAlerts = useCallback(async () => {
    setAlertsErr(null);
    const d = await apiFetch<Pagination<Alert>>(alertsQuery, { headers: authHeaders() });
    setAlertsData(d);
  }, [alertsQuery]);

  const refreshAll = useCallback(async () => {
    try {
      await Promise.all([refreshActivity(), refreshAlerts()]);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "加载失败";
      setActivityErr(msg);
      setAlertsErr(msg);
    }
  }, [refreshActivity, refreshAlerts]);

  useEffect(() => {
    (async () => {
      try {
        await refreshActivity();
      } catch (e) {
        setActivityErr(e instanceof Error ? e.message : "活动记录加载失败");
      }
    })();
  }, [refreshActivity]);

  useEffect(() => {
    (async () => {
      try {
        await refreshAlerts();
      } catch (e) {
        setAlertsErr(e instanceof Error ? e.message : "预警加载失败");
      }
    })();
  }, [refreshAlerts]);

  const loadStatistics = async () => {
    const id = hamsterId.trim();
    if (!id) {
      setStatsJson("请先填写仓鼠 ID");
      return;
    }
    const params = new URLSearchParams({ hamsterId: id, period: statsPeriod });
    const data = await apiFetch<{ statistics: unknown }>(`/api/activity/statistics?${params}`, {
      headers: authHeaders(),
    });
    setStatsJson(JSON.stringify(data.statistics ?? null, null, 2));
  };

  const loadTrend = async () => {
    const id = hamsterId.trim();
    if (!id) {
      setTrendJson("请先填写仓鼠 ID");
      return;
    }
    const params = new URLSearchParams({
      hamsterId: id,
      period: trendPeriod,
      days: String(trendDays),
    });
    const data = await apiFetch<{ trend: unknown }>(`/api/activity/trend?${params}`, {
      headers: authHeaders(),
    });
    setTrendJson(JSON.stringify(data.trend ?? null, null, 2));
  };

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-semibold">活动</h1>
          <p className="text-sm text-zinc-500">
            活动记录对接 <code className="text-xs">GET /api/activity/history</code>；下方内置预警列表与处理操作
          </p>
        </div>
        <RefreshButton onRefresh={refreshAll} />
      </div>

      <div className="rounded-xl border border-zinc-200 bg-white p-4 space-y-4">
        <h2 className="text-sm font-semibold text-zinc-800">筛选</h2>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-4 lg:grid-cols-6">
          <div>
            <label className="text-sm text-zinc-600">仓鼠 ID</label>
            <input
              value={hamsterId}
              onChange={(e) => setHamsterId(e.target.value)}
              className="mt-1 w-full rounded-md border border-zinc-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-zinc-900/20"
              placeholder="例如 1"
            />
          </div>
          <div>
            <label className="text-sm text-zinc-600">活动开始日</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="mt-1 w-full rounded-md border border-zinc-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-zinc-900/20"
            />
          </div>
          <div>
            <label className="text-sm text-zinc-600">活动结束日</label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="mt-1 w-full rounded-md border border-zinc-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-zinc-900/20"
            />
          </div>
          <div>
            <label className="text-sm text-zinc-600">活动页码</label>
            <input
              type="number"
              min={1}
              value={actPage}
              onChange={(e) => setActPage(Math.max(1, Number(e.target.value) || 1))}
              className="mt-1 w-full rounded-md border border-zinc-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-zinc-900/20"
            />
          </div>
          <div>
            <label className="text-sm text-zinc-600">每页条数</label>
            <input
              type="number"
              min={1}
              max={100}
              value={actSize}
              onChange={(e) => setActSize(Math.min(100, Math.max(1, Number(e.target.value) || 20)))}
              className="mt-1 w-full rounded-md border border-zinc-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-zinc-900/20"
            />
          </div>
          <div>
            <label className="text-sm text-zinc-600">预警状态</label>
            <select
              value={alertStatus}
              onChange={(e) => setAlertStatus(e.target.value)}
              className="mt-1 w-full rounded-md border border-zinc-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-zinc-900/20"
            >
              <option value="">全部</option>
              <option value="0">未处理</option>
              <option value="1">已读</option>
              <option value="2">已处理</option>
            </select>
          </div>
        </div>
      </div>

      {activityErr ? (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{activityErr}</div>
      ) : null}
      {alertsErr ? (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{alertsErr}</div>
      ) : null}

      <section className="rounded-xl border border-zinc-200 bg-white overflow-hidden">
        <div className="border-b border-zinc-100 bg-zinc-50 px-4 py-3 flex items-center justify-between gap-2 flex-wrap">
          <h2 className="text-sm font-semibold text-zinc-800">活动记录</h2>
          <button
            type="button"
            className="rounded-md border border-zinc-200 bg-white px-3 py-1.5 text-xs hover:bg-zinc-50"
            onClick={() => void refreshActivity().catch((e) => setActivityErr(e instanceof Error ? e.message : "刷新失败"))}
          >
            仅刷新活动
          </button>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-zinc-50/80 text-zinc-600">
              <tr>
                <th className="px-4 py-2 text-left">ID</th>
                <th className="px-4 py-2 text-left">cameraId</th>
                <th className="px-4 py-2 text-left">score</th>
                <th className="px-4 py-2 text-left">status</th>
                <th className="px-4 py-2 text-left">analysis</th>
                <th className="px-4 py-2 text-left">createdAt</th>
              </tr>
            </thead>
            <tbody>
              {(activityData?.list ?? []).map((row) => (
                <tr key={row.id} className="border-t border-zinc-100">
                  <td className="px-4 py-2">{row.id}</td>
                  <td className="px-4 py-2">{row.cameraId ?? "-"}</td>
                  <td className="px-4 py-2 font-mono text-xs">{row.activityScore ?? "-"}</td>
                  <td className="px-4 py-2 font-mono text-xs">{row.status ?? "-"}</td>
                  <td className="px-4 py-2 max-w-[200px] truncate text-zinc-600" title={row.analysisResult}>
                    {row.analysisResult ?? "-"}
                  </td>
                  <td className="px-4 py-2 text-zinc-500">{row.createdAt ?? "-"}</td>
                </tr>
              ))}
              {!activityData?.list?.length ? (
                <tr>
                  <td className="px-4 py-6 text-zinc-500" colSpan={6}>
                    暂无活动记录（或尚未填写仓鼠 ID）
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
        {activityData && activityData.total != null ? (
          <div className="border-t border-zinc-100 px-4 py-2 text-xs text-zinc-500">
            共 {activityData.total} 条 · 第 {activityData.page ?? actPage} 页 · 每页 {activityData.size ?? actSize} 条
          </div>
        ) : null}
      </section>

      <section className="rounded-xl border border-zinc-200 bg-white p-4 space-y-4">
        <h2 className="text-sm font-semibold text-zinc-800">活动统计与趋势</h2>
        <p className="text-xs text-zinc-500">
          对接 <code className="text-[11px]">GET /api/activity/statistics</code> 与{" "}
          <code className="text-[11px]">GET /api/activity/trend</code>。若后端尚未实现业务数据，接口可能返回{" "}
          <code className="text-[11px]">null</code>。
        </p>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div className="space-y-2">
            <div className="flex flex-wrap items-end gap-2">
              <div>
                <label className="text-xs text-zinc-600">period</label>
                <select
                  value={statsPeriod}
                  onChange={(e) => setStatsPeriod(e.target.value)}
                  className="mt-0.5 block rounded-md border border-zinc-200 px-2 py-1.5 text-sm"
                >
                  <option value="week">week</option>
                  <option value="day">day</option>
                  <option value="month">month</option>
                </select>
              </div>
              <button
                type="button"
                className="rounded-md bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-zinc-800"
                onClick={() =>
                  void loadStatistics().catch((e) => setStatsJson(e instanceof Error ? e.message : "请求失败"))
                }
              >
                加载统计
              </button>
            </div>
            <pre className="rounded-md border border-zinc-100 bg-zinc-50 p-3 text-xs overflow-auto max-h-40">
              {statsJson ?? "点击「加载统计」"}
            </pre>
          </div>
          <div className="space-y-2">
            <div className="flex flex-wrap items-end gap-2">
              <div>
                <label className="text-xs text-zinc-600">period</label>
                <select
                  value={trendPeriod}
                  onChange={(e) => setTrendPeriod(e.target.value)}
                  className="mt-0.5 block rounded-md border border-zinc-200 px-2 py-1.5 text-sm"
                >
                  <option value="day">day</option>
                  <option value="week">week</option>
                </select>
              </div>
              <div>
                <label className="text-xs text-zinc-600">days</label>
                <input
                  type="number"
                  min={1}
                  max={90}
                  value={trendDays}
                  onChange={(e) => setTrendDays(Math.min(90, Math.max(1, Number(e.target.value) || 7)))}
                  className="mt-0.5 w-20 rounded-md border border-zinc-200 px-2 py-1.5 text-sm"
                />
              </div>
              <button
                type="button"
                className="rounded-md bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-zinc-800"
                onClick={() => void loadTrend().catch((e) => setTrendJson(e instanceof Error ? e.message : "请求失败"))}
              >
                加载趋势
              </button>
            </div>
            <pre className="rounded-md border border-zinc-100 bg-zinc-50 p-3 text-xs overflow-auto max-h-40">
              {trendJson ?? "点击「加载趋势」"}
            </pre>
          </div>
        </div>
      </section>

      <section className="rounded-xl border border-zinc-200 bg-white overflow-hidden">
        <div className="border-b border-zinc-100 bg-zinc-50 px-4 py-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-sm font-semibold text-zinc-800">预警</h2>
            <p className="text-xs text-zinc-500 mt-0.5">与上方仓鼠 ID、预警状态联动；可查询、更新状态、删除</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              disabled={busy}
              className="rounded-md bg-zinc-900 px-3 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-60"
              onClick={async () => {
                setBusy(true);
                try {
                  await apiFetch("/api/analysis/activity", {
                    method: "POST",
                    headers: authHeaders(),
                    json: { cameraId: 1, imageUrl: "https://example.com/snapshots/demo.jpg" },
                  });
                  await refreshAll();
                } finally {
                  setBusy(false);
                }
              }}
            >
              触发 demo 分析（可能生成预警）
            </button>
            <span className="text-xs text-zinc-500">POST /api/analysis/activity</span>
          </div>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-zinc-50 text-zinc-600">
            <tr>
              <th className="px-4 py-2 text-left">ID</th>
              <th className="px-4 py-2 text-left">hamsterId</th>
              <th className="px-4 py-2 text-left">activityStatus</th>
              <th className="px-4 py-2 text-left">score / th</th>
              <th className="px-4 py-2 text-left">status</th>
              <th className="px-4 py-2 text-left">createdAt</th>
              <th className="px-4 py-2 text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            {(alertsData?.list ?? []).map((a) => (
              <tr key={a.id} className="border-t border-zinc-100">
                <td className="px-4 py-2">{a.id}</td>
                <td className="px-4 py-2">{a.hamsterId}</td>
                <td className="px-4 py-2 font-mono text-xs">{a.activityStatus}</td>
                <td className="px-4 py-2 font-mono text-xs">
                  {a.activityScore} / {a.threshold}
                </td>
                <td className="px-4 py-2">{a.status}</td>
                <td className="px-4 py-2 text-zinc-500">{a.createdAt ?? "-"}</td>
                <td className="px-4 py-2">
                  <div className="flex justify-end gap-2 flex-wrap">
                    <button
                      className="rounded-md border border-zinc-200 px-2 py-1 text-xs hover:bg-zinc-50"
                      onClick={async () => {
                        await apiFetch(`/api/alerts/${a.id}/status`, {
                          method: "POST",
                          headers: authHeaders(),
                          json: { status: 1, handleRemark: "已读" },
                        });
                        await refreshAlerts();
                      }}
                    >
                      标记已读
                    </button>
                    <button
                      className="rounded-md border border-zinc-200 px-2 py-1 text-xs hover:bg-zinc-50"
                      onClick={async () => {
                        await apiFetch(`/api/alerts/${a.id}/status`, {
                          method: "POST",
                          headers: authHeaders(),
                          json: { status: 2, handleRemark: "已处理" },
                        });
                        await refreshAlerts();
                      }}
                    >
                      标记已处理
                    </button>
                    <button
                      className="rounded-md border border-red-200 text-red-700 px-2 py-1 text-xs hover:bg-red-50"
                      onClick={async () => {
                        await apiFetch(`/api/alerts/${a.id}`, { method: "DELETE", headers: authHeaders() });
                        await refreshAlerts();
                      }}
                    >
                      删除
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {!alertsData?.list?.length ? (
              <tr>
                <td className="px-4 py-6 text-zinc-500" colSpan={7}>
                  暂无预警数据
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </section>
    </div>
  );
}
