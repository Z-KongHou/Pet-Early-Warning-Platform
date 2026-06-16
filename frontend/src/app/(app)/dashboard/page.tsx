"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { authHeaders } from "@/lib/authed";
import { apiFetch } from "@/lib/http";
import type { Alert, Hamster, Pagination, User } from "@/lib/types";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
} from "recharts";

interface AlertStatusCount {
  name: string;
  value: number;
}

interface DailyAlertTrend {
  date: string;
  count: number;
}

const STATUS_LABELS: Record<number, string> = {
  0: "未处理",
  1: "已读",
  2: "已处理",
};

const STATUS_COLORS = ["#f87171", "#fbbf24", "#34d399"];

export default function DashboardPage() {
  const [me, setMe] = useState<User | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [alertsLoading, setAlertsLoading] = useState(true);

  const [hamsters, setHamsters] = useState<Hamster[]>([]);

  // 聚合后的图表数据
  const [statusDist, setStatusDist] = useState<AlertStatusCount[]>([]);
  const [dailyTrend, setDailyTrend] = useState<DailyAlertTrend[]>([]);

  const [kpi, setKpi] = useState({
    total: 0,
    pending: 0,
    today: 0,
  });

  const hamsterMap = useMemo(() => {
    const m = new Map<number, string>();
    hamsters.forEach((h) => m.set(h.id, h.name));
    return m;
  }, [hamsters]);

  const pendingAlerts = useMemo(() => {
    return alerts.filter((a) => a.status === 0).slice(0, 5);
  }, [alerts]);

  useEffect(() => {
    apiFetch<User>("/api/auth/me", { headers: authHeaders() })
      .then(setMe)
      .catch((e) => setErr(e instanceof Error ? e.message : "加载失败"));
  }, []);

  // 加载仓鼠列表用于名称映射
  useEffect(() => {
    apiFetch<Pagination<Hamster>>("/api/hamsters?page=1&size=100", { headers: authHeaders() })
      .then((d) => setHamsters(d.list ?? []))
      .catch(() => {});
  }, []);

  useEffect(() => {
    const loadAlerts = async () => {
      setAlertsLoading(true);
      try {
        // 获取前 200 条预警用于聚合（足够展示趋势）
        const data = await apiFetch<Pagination<Alert>>(
          "/api/alerts?page=1&size=200",
          { headers: authHeaders() }
        );
        const list = data.list ?? [];
        setAlerts(list);

        // KPI 计算
        const todayStr = new Date().toISOString().slice(0, 10);
        const total = data.total ?? list.length;
        const pending = list.filter((a) => a.status === 0).length;
        const today = list.filter((a) => a.createdAt?.startsWith(todayStr)).length;
        setKpi({ total, pending, today });

        // 1. 状态分布
        const statusCount: Record<number, number> = { 0: 0, 1: 0, 2: 0 };
        list.forEach((a) => {
          if (a.status != null && statusCount[a.status] != null) {
            statusCount[a.status]++;
          }
        });
        setStatusDist([
          { name: "未处理", value: statusCount[0] },
          { name: "已读", value: statusCount[1] },
          { name: "已处理", value: statusCount[2] },
        ]);

        // 2. 近7天趋势
        const trendMap = new Map<string, number>();
        const now = new Date();
        for (let i = 6; i >= 0; i--) {
          const d = new Date(now);
          d.setDate(d.getDate() - i);
          const key = d.toISOString().slice(0, 10);
          trendMap.set(key, 0);
        }
        list.forEach((a) => {
          if (a.createdAt) {
            const day = a.createdAt.slice(0, 10);
            if (trendMap.has(day)) {
              trendMap.set(day, (trendMap.get(day) ?? 0) + 1);
            }
          }
        });
        const trendArr: DailyAlertTrend[] = Array.from(trendMap.entries()).map(
          ([date, count]) => ({ date: date.slice(5), count })
        );
        setDailyTrend(trendArr);
      } catch (e) {
        const msg = e instanceof Error ? e.message : "预警数据加载失败";
        setErr(msg);
      } finally {
        setAlertsLoading(false);
      }
    };
    loadAlerts();
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Hello, {me?.username ?? "用户"} 👋</h1>
        <p className="mt-1 text-sm text-zinc-500">欢迎回来，这里是你的宠物健康预警仪表盘。</p>
      </div>

      {err ? (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {err}
        </div>
      ) : null}

      {/* KPI 卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="rounded-xl border border-zinc-200 bg-white p-4">
          <div className="text-xs text-zinc-500">总预警数</div>
          <div className="mt-1 text-2xl font-semibold tabular-nums">{kpi.total}</div>
          <div className="text-xs text-zinc-500">近200条内统计</div>
        </div>
        <div className="rounded-xl border border-zinc-200 bg-white p-4">
          <div className="text-xs text-zinc-500">未处理预警</div>
          <div className="mt-1 text-2xl font-semibold tabular-nums text-red-600">{kpi.pending}</div>
          <div className="text-xs text-zinc-500">需及时处理</div>
        </div>
        <div className="rounded-xl border border-zinc-200 bg-white p-4">
          <div className="text-xs text-zinc-500">今日新增预警</div>
          <div className="mt-1 text-2xl font-semibold tabular-nums text-orange-600">{kpi.today}</div>
          <div className="text-xs text-zinc-500">{new Date().toLocaleDateString()}</div>
        </div>
      </div>

      {/* 图表区域 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* 近7天预警趋势 - 折线图 */}
        <div className="rounded-xl border border-zinc-200 bg-white p-4">
          <div className="text-sm font-semibold mb-3">近7天预警趋势</div>
          {alertsLoading ? (
            <div className="h-[260px] flex items-center justify-center text-sm text-zinc-400">加载中...</div>
          ) : dailyTrend.length > 0 ? (
            <div className="h-[260px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={dailyTrend}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f4f4f5" />
                  <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Line
                    type="monotone"
                    dataKey="count"
                    stroke="#6366f1"
                    strokeWidth={2}
                    dot={{ fill: "#6366f1", r: 3 }}
                    activeDot={{ r: 5 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="h-[260px] flex items-center justify-center text-sm text-zinc-400">暂无数据</div>
          )}
        </div>

        {/* 预警状态分布 - 柱状图 */}
        <div className="rounded-xl border border-zinc-200 bg-white p-4">
          <div className="text-sm font-semibold mb-3">预警状态分布</div>
          {alertsLoading ? (
            <div className="h-[260px] flex items-center justify-center text-sm text-zinc-400">加载中...</div>
          ) : statusDist.some((d) => d.value > 0) ? (
            <div className="h-[260px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={statusDist}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f4f4f5" />
                  <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                    {statusDist.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={STATUS_COLORS[index]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="h-[260px] flex items-center justify-center text-sm text-zinc-400">暂无数据</div>
          )}
        </div>
      </div>

      {/* 最近未处理预警 */}
      <div className="rounded-xl border border-zinc-200 bg-white p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="text-sm font-semibold">最近未处理预警</div>
          <Link href="/activity" className="text-xs text-indigo-600 hover:underline">
            查看全部 →
          </Link>
        </div>
        {alertsLoading ? (
          <div className="py-8 text-center text-sm text-zinc-400">加载中...</div>
        ) : pendingAlerts.length > 0 ? (
          <div className="divide-y divide-zinc-100">
            {pendingAlerts.map((a) => {
              const hName = hamsterMap.get(a.hamsterId) ?? `仓鼠 #${a.hamsterId}`;
              const time = a.createdAt ? new Date(a.createdAt).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }) : "-";
              return (
                <div key={a.id} className="flex items-center justify-between py-3">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="text-xs text-zinc-400 tabular-nums w-20 shrink-0">{time}</div>
                    <div className="font-medium text-sm truncate">{hName}</div>
                    <div className="text-xs px-2 py-0.5 rounded bg-red-100 text-red-700">{a.activityStatus}</div>
                    <div className="text-xs text-zinc-500">得分 {a.activityScore}</div>
                  </div>
                  <Link href="/activity" className="text-xs text-indigo-600 hover:underline shrink-0">
                    去处理
                  </Link>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="py-8 text-center text-sm text-zinc-400">暂无未处理预警</div>
        )}
      </div>
    </div>
  );
}
