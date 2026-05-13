"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { RefreshButton } from "@/components/RefreshButton";
import { ApiError, apiFetch } from "@/lib/http";
import { authHeaders } from "@/lib/authed";
import {
  SETTING_FIELD_META,
  sortSettingsByKnownOrder,
  type SettingFieldMeta,
} from "@/lib/setting-fields";
import type { Setting } from "@/lib/types";

function inputClass(extra = "") {
  return `w-full rounded-md border border-zinc-200 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-zinc-900/20 ${extra}`;
}

function validateValue(keyValue: string, meta: SettingFieldMeta | undefined): string | null {
  if (meta?.kind === "seconds") {
    const n = Number(keyValue);
    if (!Number.isFinite(n) || n < 1 || n > 86400) return "请输入 1～86400 之间的秒数";
  }
  if (meta?.kind === "score0_100") {
    const n = Number(keyValue);
    if (!Number.isInteger(n) || n < 0 || n > 100) return "请输入 0～100 的整数";
  }
  return null;
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<Setting[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [flash, setFlash] = useState<{ type: "ok" | "err"; text: string } | null>(null);
  const [showSecret, setShowSecret] = useState<Record<string, boolean>>({});

  const sorted = useMemo(() => sortSettingsByKnownOrder(settings), [settings]);

  const refresh = useCallback(async () => {
    const list = await apiFetch<Setting[]>("/api/settings", { headers: authHeaders() });
    setSettings(list);
  }, []);

  useEffect(() => {
    (async () => {
      setErr(null);
      setLoading(true);
      try {
        await refresh();
      } catch (e) {
        setErr(e instanceof Error ? e.message : "加载失败");
      } finally {
        setLoading(false);
      }
    })();
  }, [refresh]);

  function patchLocal(keyName: string, patch: Partial<Setting>) {
    setSettings((prev) => prev.map((s) => (s.keyName === keyName ? { ...s, ...patch } : s)));
  }

  async function saveRow(s: Setting) {
    const meta = SETTING_FIELD_META[s.keyName];
    const vErr = validateValue(s.keyValue, meta);
    if (vErr) {
      setFlash({ type: "err", text: vErr });
      return;
    }

    if (s.keyName === "low_activity_threshold" || s.keyName === "high_activity_threshold") {
      const low = Number(settings.find((x) => x.keyName === "low_activity_threshold")?.keyValue);
      const high = Number(settings.find((x) => x.keyName === "high_activity_threshold")?.keyValue);
      if (Number.isFinite(low) && Number.isFinite(high) && low >= high) {
        setFlash({ type: "err", text: "低活动阈值须小于高活动阈值" });
        return;
      }
    }

    setBusyKey(s.keyName);
    setFlash(null);
    try {
      const body: { keyValue: string; description?: string } = { keyValue: s.keyValue };
      if (!meta) body.description = s.description ?? undefined;

      await apiFetch(`/api/settings/${encodeURIComponent(s.keyName)}`, {
        method: "POST",
        headers: authHeaders(),
        json: body,
      });
      await refresh();
      setFlash({ type: "ok", text: `「${meta?.label ?? s.keyName}」已保存` });
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : e instanceof Error ? e.message : "保存失败";
      setFlash({ type: "err", text: msg });
    } finally {
      setBusyKey(null);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-semibold">系统配置</h1>
          <p className="text-sm text-zinc-500">
            与后端 <code className="text-xs">GET /api/settings</code>、
            <code className="text-xs"> POST /api/settings/{"{keyName}"}</code> 同步
          </p>
        </div>
        <RefreshButton
          onRefresh={async () => {
            setErr(null);
            try {
              await refresh();
            } catch (e) {
              setErr(e instanceof Error ? e.message : "刷新失败");
            }
          }}
        />
      </div>

      {err ? (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{err}</div>
      ) : null}

      {flash ? (
        <div
          className={
            flash.type === "ok"
              ? "rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800"
              : "rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
          }
        >
          {flash.text}
        </div>
      ) : null}

      {loading ? (
        <div className="rounded-xl border border-zinc-200 bg-white px-4 py-10 text-center text-sm text-zinc-500">
          加载中…
        </div>
      ) : (
        <div className="space-y-3">
          {sorted.map((s) => {
            const meta = SETTING_FIELD_META[s.keyName];
            const isSecret = meta?.kind === "secret";
            const isNumber = meta?.kind === "seconds" || meta?.kind === "score0_100";

            return (
              <div
                key={s.keyName}
                className="rounded-xl border border-zinc-200 bg-white p-4 shadow-sm"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1 space-y-1">
                    <div className="flex flex-wrap items-baseline gap-2">
                      <h2 className="text-sm font-semibold text-zinc-900">
                        {meta?.label ?? s.keyName}
                      </h2>
                      <span className="font-mono text-xs text-zinc-400">{s.keyName}</span>
                    </div>
                    {meta?.hint ? <p className="text-xs text-zinc-500">{meta.hint}</p> : null}
                    {!meta && s.description ? (
                      <p className="text-xs text-zinc-500">{s.description}</p>
                    ) : null}
                    {meta && s.description ? (
                      <p className="text-xs text-zinc-400">说明：{s.description}</p>
                    ) : null}
                  </div>
                  <button
                    type="button"
                    disabled={busyKey === s.keyName}
                    className="shrink-0 rounded-md bg-zinc-900 px-3 py-2 text-xs font-medium text-white hover:bg-zinc-800 disabled:opacity-60"
                    onClick={() => saveRow(s)}
                  >
                    {busyKey === s.keyName ? "保存中…" : "保存"}
                  </button>
                </div>

                <div className="mt-3">
                  {isSecret ? (
                    <div className="flex gap-2">
                      <input
                        type={showSecret[s.keyName] ? "text" : "password"}
                        autoComplete="off"
                        value={s.keyValue}
                        onChange={(e) => patchLocal(s.keyName, { keyValue: e.target.value })}
                        className={inputClass("font-mono flex-1")}
                        placeholder="输入 API Key"
                      />
                      <button
                        type="button"
                        className="shrink-0 rounded-md border border-zinc-200 px-3 py-2 text-xs text-zinc-700 hover:bg-zinc-50"
                        onClick={() =>
                          setShowSecret((prev) => ({ ...prev, [s.keyName]: !prev[s.keyName] }))
                        }
                      >
                        {showSecret[s.keyName] ? "隐藏" : "显示"}
                      </button>
                    </div>
                  ) : isNumber ? (
                    <input
                      type="number"
                      min={meta?.kind === "seconds" ? 1 : 0}
                      max={meta?.kind === "seconds" ? 86400 : 100}
                      step={meta?.kind === "score0_100" ? 1 : 1}
                      value={s.keyValue}
                      onChange={(e) => patchLocal(s.keyName, { keyValue: e.target.value })}
                      className={inputClass()}
                    />
                  ) : (
                    <input
                      value={s.keyValue}
                      onChange={(e) => patchLocal(s.keyName, { keyValue: e.target.value })}
                      className={inputClass()}
                    />
                  )}
                </div>

                {!meta ? (
                  <div className="mt-3">
                    <label className="text-xs text-zinc-500">description（可选，将一并提交）</label>
                    <input
                      value={s.description ?? ""}
                      onChange={(e) => patchLocal(s.keyName, { description: e.target.value })}
                      className={`${inputClass()} mt-1`}
                    />
                  </div>
                ) : null}

                {s.updatedAt ? (
                  <p className="mt-2 text-xs text-zinc-400">最近更新：{s.updatedAt}</p>
                ) : null}
              </div>
            );
          })}

          {sorted.length === 0 ? (
            <div className="rounded-xl border border-zinc-200 bg-white px-4 py-10 text-center text-sm text-zinc-500">
              暂无配置项
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}
