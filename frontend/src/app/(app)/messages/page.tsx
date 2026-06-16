"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { RefreshButton } from "@/components/RefreshButton";
import { useNotifications } from "@/components/NotificationContext";
import { apiFetch } from "@/lib/http";
import { authHeaders } from "@/lib/authed";
import type { Message, Pagination } from "@/lib/types";

export default function MessagesPage() {
  const [data, setData] = useState<Pagination<Message> | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [isRead, setIsRead] = useState<string>("");

  const { unreadCount, refreshUnread, alertVersion } = useNotifications();

  const query = useMemo(() => {
    const params = new URLSearchParams({ page: "1", size: "20" });
    if (isRead !== "") params.set("isRead", isRead);
    return `/api/messages?${params.toString()}`;
  }, [isRead]);

  const refresh = useCallback(async () => {
    const [list] = await Promise.all([
      apiFetch<Pagination<Message>>(query, { headers: authHeaders() }),
      refreshUnread(),
    ]);
    setData(list);
  }, [query, refreshUnread]);

  // Initial load + refresh when filter changes
  useEffect(() => {
    (async () => {
      try {
        await refresh();
      } catch (e) {
        setErr(e instanceof Error ? e.message : "加载失败");
      }
    })();
  }, [refresh]);

  // Auto-refresh when a new alert arrives via SSE
  useEffect(() => {
    if (alertVersion > 0) {
      refresh();
    }
  }, [alertVersion]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-semibold">站内信</h1>
          <p className="text-sm text-zinc-500">
            未读：<span className="font-medium">{unreadCount}</span>
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={isRead}
            onChange={(e) => setIsRead(e.target.value)}
            className="rounded-md border border-zinc-200 px-3 py-2 text-sm"
          >
            <option value="">全部</option>
            <option value="0">未读</option>
            <option value="1">已读</option>
          </select>
          <RefreshButton onRefresh={refresh} />
          <button
            className="rounded-md bg-zinc-900 px-3 py-2 text-sm font-medium text-white hover:bg-zinc-800"
            onClick={async () => {
              await apiFetch("/api/messages/read-all", {
                method: "POST",
                headers: authHeaders(),
              });
              await refresh();
            }}
          >
            全部已读
          </button>
        </div>
      </div>

      {err ? (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {err}
        </div>
      ) : null}

      <div className="rounded-xl border border-zinc-200 bg-white overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-zinc-50 text-zinc-600">
            <tr>
              <th className="px-4 py-2 text-left">ID</th>
              <th className="px-4 py-2 text-left">标题</th>
              <th className="px-4 py-2 text-left">已读</th>
              <th className="px-4 py-2 text-left">创建时间</th>
              <th className="px-4 py-2 text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            {(data?.list ?? []).map((m) => (
              <tr key={m.id} className="border-t border-zinc-100 align-top">
                <td className="px-4 py-2">{m.id}</td>
                <td className="px-4 py-2">
                  <div className="font-medium">{m.title}</div>
                  <div className="mt-1 text-xs text-zinc-500">{m.content}</div>
                </td>
                <td className="px-4 py-2">{m.isRead === 1 ? "是" : "否"}</td>
                <td className="px-4 py-2 text-zinc-500">{m.createdAt ?? "-"}</td>
                <td className="px-4 py-2">
                  <div className="flex justify-end gap-2">
                    {m.isRead === 0 ? (
                      <button
                        className="rounded-md border border-zinc-200 px-2 py-1 text-xs hover:bg-zinc-50"
                        onClick={async () => {
                          await apiFetch(`/api/messages/${m.id}/read`, {
                            method: "POST",
                            headers: authHeaders(),
                          });
                          await refresh();
                        }}
                      >
                        标记已读
                      </button>
                    ) : null}
                    <button
                      className="rounded-md border border-red-200 text-red-700 px-2 py-1 text-xs hover:bg-red-50"
                      onClick={async () => {
                        await apiFetch(`/api/messages/${m.id}`, {
                          method: "DELETE",
                          headers: authHeaders(),
                        });
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
                <td className="px-4 py-6 text-zinc-500" colSpan={5}>
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
