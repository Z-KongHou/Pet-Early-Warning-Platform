"use client";

import { useEffect, useState } from "react";
import { RefreshButton } from "@/components/RefreshButton";
import { apiFetch, ApiError } from "@/lib/http";
import { authHeaders } from "@/lib/authed";
import type { Hamster, Pagination } from "@/lib/types";

const emptyCreateForm = {
  name: "",
  breed: "",
  birthDate: "",
  gender: "0",
  weight: "",
  avatar: "",
  remark: "",
  healthStatus: "0",
};

/** 与后端 `HamsterRequest` / `POST /api/hamsters` 对齐的请求体 */
function buildHamsterCreateJson(values: typeof emptyCreateForm) {
  const name = values.name.trim();
  const json: Record<string, unknown> = {
    name,
    gender: Number(values.gender),
    healthStatus: Number(values.healthStatus),
  };
  const breed = values.breed.trim();
  if (breed) json.breed = breed;
  if (values.birthDate) json.birthDate = values.birthDate;
  const w = values.weight.trim();
  if (w) {
    const n = Number(w);
    if (Number.isNaN(n)) throw new Error("体重需为有效数字");
    json.weight = n;
  }
  const avatar = values.avatar.trim();
  if (avatar) json.avatar = avatar;
  const remark = values.remark.trim();
  if (remark) json.remark = remark;
  return json;
}

export default function HamstersPage() {
  const [data, setData] = useState<Pagination<Hamster> | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [formErr, setFormErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [create, setCreate] = useState(emptyCreateForm);

  useEffect(() => {
    refresh().catch((e) => setErr(e instanceof Error ? e.message : "加载失败"));
  }, []);

  async function refresh() {
    const d = await apiFetch<Pagination<Hamster>>("/api/hamsters?page=1&size=20", { headers: authHeaders() });
    setData(d);
  }

  return (
    <div className="space-y-3">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-xl font-semibold">仓鼠</h1>
          <p className="text-xs text-zinc-500">对接后端 `/api/hamsters`</p>
        </div>
        <RefreshButton onRefresh={refresh} />
      </div>

      {err ? (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {err}
        </div>
      ) : null}

      <div className="rounded-lg border border-zinc-200 bg-white p-3">
        <form
          className="space-y-2"
          onSubmit={async (e) => {
            e.preventDefault();
            setFormErr(null);
            setBusy(true);
            try {
              const json = buildHamsterCreateJson(create);
              await apiFetch("/api/hamsters", {
                method: "POST",
                headers: authHeaders(),
                json,
              });
              setCreate({ ...emptyCreateForm });
              await refresh();
            } catch (ex) {
              setFormErr(
                ex instanceof ApiError ? ex.message : ex instanceof Error ? ex.message : "提交失败"
              );
            } finally {
              setBusy(false);
            }
          }}
        >
          <fieldset className="min-w-0 border-0 p-0 m-0">
            <legend className="text-xs font-medium text-zinc-800">新增仓鼠</legend>
            {formErr ? (
              <div className="mt-1.5 rounded border border-red-200 bg-red-50 px-2 py-1 text-xs text-red-700">
                {formErr}
              </div>
            ) : null}
            <div className="mt-2 grid grid-cols-2 gap-x-2 gap-y-2 sm:grid-cols-3 lg:grid-cols-6">
              <div className="min-w-0">
                <label htmlFor="hamster-name" className="text-xs text-zinc-600">
                  名称 <span className="text-red-600">*</span>
                </label>
                <input
                  id="hamster-name"
                  name="name"
                  required
                  autoComplete="off"
                  value={create.name}
                  onChange={(e) => setCreate({ ...create, name: e.target.value })}
                  className="mt-0.5 w-full rounded border border-zinc-200 px-2 py-1 text-sm"
                  placeholder="小白"
                />
              </div>
              <div className="min-w-0">
                <label htmlFor="hamster-breed" className="text-xs text-zinc-600">
                  品种
                </label>
                <input
                  id="hamster-breed"
                  name="breed"
                  value={create.breed}
                  onChange={(e) => setCreate({ ...create, breed: e.target.value })}
                  className="mt-0.5 w-full rounded border border-zinc-200 px-2 py-1 text-sm"
                  placeholder="金丝熊"
                />
              </div>
              <div className="min-w-0">
                <label htmlFor="hamster-birth" className="text-xs text-zinc-600">
                  出生日期
                </label>
                <input
                  id="hamster-birth"
                  name="birthDate"
                  type="date"
                  value={create.birthDate}
                  onChange={(e) => setCreate({ ...create, birthDate: e.target.value })}
                  className="mt-0.5 w-full rounded border border-zinc-200 px-2 py-1 text-sm"
                />
              </div>
              <div className="min-w-0">
                <label htmlFor="hamster-gender" className="text-xs text-zinc-600">
                  性别
                </label>
                <select
                  id="hamster-gender"
                  name="gender"
                  value={create.gender}
                  onChange={(e) => setCreate({ ...create, gender: e.target.value })}
                  className="mt-0.5 w-full rounded border border-zinc-200 px-2 py-1 text-sm"
                >
                  <option value="0">未知</option>
                  <option value="1">公</option>
                  <option value="2">母</option>
                </select>
              </div>
              <div className="min-w-0">
                <label htmlFor="hamster-weight" className="text-xs text-zinc-600">
                  体重（克）
                </label>
                <input
                  id="hamster-weight"
                  name="weight"
                  inputMode="decimal"
                  value={create.weight}
                  onChange={(e) => setCreate({ ...create, weight: e.target.value })}
                  className="mt-0.5 w-full rounded border border-zinc-200 px-2 py-1 text-sm"
                  placeholder="120.5"
                />
              </div>
              <div className="min-w-0">
                <label htmlFor="hamster-health" className="text-xs text-zinc-600">
                  健康
                </label>
                <select
                  id="hamster-health"
                  name="healthStatus"
                  value={create.healthStatus}
                  onChange={(e) => setCreate({ ...create, healthStatus: e.target.value })}
                  className="mt-0.5 w-full rounded border border-zinc-200 px-2 py-1 text-sm"
                >
                  <option value="0">正常</option>
                  <option value="1">异常</option>
                  <option value="2">治疗中</option>
                </select>
              </div>
              <div className="col-span-2 min-w-0 sm:col-span-3 lg:col-span-6">
                <details className="rounded border border-zinc-100 bg-zinc-50/80 px-2 py-1">
                  <summary className="text-xs text-zinc-600 select-none [&::-webkit-details-marker]:hidden">
                    更多：头像、备注
                  </summary>
                  <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
                    <div className="min-w-0">
                      <label htmlFor="hamster-avatar" className="text-xs text-zinc-600">
                        头像 URL
                      </label>
                      <input
                        id="hamster-avatar"
                        name="avatar"
                        type="text"
                        inputMode="url"
                        value={create.avatar}
                        onChange={(e) => setCreate({ ...create, avatar: e.target.value })}
                        className="mt-0.5 w-full rounded border border-zinc-200 bg-white px-2 py-1 text-sm"
                        placeholder="https://…"
                      />
                    </div>
                    <div className="min-w-0">
                      <label htmlFor="hamster-remark" className="text-xs text-zinc-600">
                        备注
                      </label>
                      <textarea
                        id="hamster-remark"
                        name="remark"
                        rows={1}
                        value={create.remark}
                        onChange={(e) => setCreate({ ...create, remark: e.target.value })}
                        className="mt-0.5 min-h-[1.875rem] w-full resize-y rounded border border-zinc-200 bg-white px-2 py-1 text-sm leading-snug"
                        placeholder="可选"
                      />
                    </div>
                  </div>
                </details>
              </div>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              <button
                type="submit"
                disabled={busy}
                className="rounded border border-zinc-900 bg-zinc-900 px-3 py-1 text-sm font-medium text-white hover:bg-zinc-800 disabled:opacity-60"
              >
                {busy ? "提交中…" : "新增仓鼠"}
              </button>
              <button
                type="button"
                disabled={busy}
                className="rounded border border-zinc-200 px-3 py-1 text-sm hover:bg-zinc-50 disabled:opacity-60"
                onClick={() => {
                  setCreate({ ...emptyCreateForm });
                  setFormErr(null);
                }}
              >
                清空表单
              </button>
            </div>
          </fieldset>
        </form>
      </div>

      <div className="rounded-xl border border-zinc-200 bg-white overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-zinc-50 text-zinc-600">
            <tr>
              <th className="px-4 py-2 text-left">ID</th>
              <th className="px-4 py-2 text-left">名称</th>
              <th className="px-4 py-2 text-left">品种</th>
              <th className="px-4 py-2 text-left">健康状态</th>
              <th className="px-4 py-2 text-left">创建时间</th>
              <th className="px-4 py-2 text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            {(data?.list ?? []).map((h) => (
              <tr key={h.id} className="border-t border-zinc-100">
                <td className="px-4 py-2">{h.id}</td>
                <td className="px-4 py-2 font-medium">{h.name}</td>
                <td className="px-4 py-2">{h.breed ?? "-"}</td>
                <td className="px-4 py-2">{h.healthStatus}</td>
                <td className="px-4 py-2 text-zinc-500">{h.createdAt ?? "-"}</td>
                <td className="px-4 py-2">
                  <div className="flex justify-end gap-2">
                    <button
                      className="rounded-md border border-zinc-200 px-2 py-1 text-xs hover:bg-zinc-50"
                      onClick={async () => {
                        await apiFetch(`/api/hamsters/${h.id}`, {
                          method: "POST",
                          headers: authHeaders(),
                          json: { healthStatus: h.healthStatus === 0 ? 1 : 0 },
                        });
                        await refresh();
                      }}
                    >
                      切换健康状态
                    </button>
                    <button
                      className="rounded-md border border-red-200 text-red-700 px-2 py-1 text-xs hover:bg-red-50"
                      onClick={async () => {
                        await apiFetch(`/api/hamsters/${h.id}`, { method: "DELETE", headers: authHeaders() });
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

