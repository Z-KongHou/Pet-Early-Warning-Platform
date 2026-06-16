"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { clearToken } from "@/lib/auth-client";
import { NotificationProvider, useNotifications } from "@/components/NotificationContext";

const nav = [
  { href: "/dashboard", label: "仪表盘" },
  { href: "/hamsters", label: "仓鼠" },
  { href: "/cameras", label: "摄像头" },
  { href: "/activity", label: "活动" },
  { href: "/messages", label: "站内信", badge: true },
  { href: "/chat", label: "AI 问答" },
  { href: "/settings", label: "配置" },
  { href: "/users/me/cameras", label: "我的摄像头" },
];

function AppShellInner({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { unreadCount } = useNotifications();

  return (
    <div className="flex h-dvh min-h-0 overflow-hidden bg-zinc-50 text-zinc-900">
      <aside className="flex w-64 shrink-0 flex-col border-r border-zinc-200 bg-white">
        <div className="shrink-0 px-4 py-4 border-b border-zinc-200">
          <div className="text-sm font-semibold">Pet Early Warning</div>
        </div>
        <nav className="min-h-0 flex-1 overflow-y-auto p-2 space-y-1">
          {nav.map((n) => {
            const active = pathname === n.href;
            return (
              <Link
                key={n.href}
                href={n.href}
                className={[
                  "flex items-center justify-between rounded-md px-3 py-2 text-sm",
                  active ? "bg-zinc-900 text-white" : "hover:bg-zinc-100",
                ].join(" ")}
              >
                <span>{n.label}</span>
                {n.badge && unreadCount > 0 ? (
                  <span
                    className={[
                      "inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 text-xs font-medium rounded-full",
                      active
                        ? "bg-white text-zinc-900"
                        : "bg-red-500 text-white",
                    ].join(" ")}
                  >
                    {unreadCount > 99 ? "99+" : unreadCount}
                  </span>
                ) : null}
              </Link>
            );
          })}
        </nav>
      </aside>

      <div className="flex min-h-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center justify-between border-b border-zinc-200 bg-white px-4">
          <div className="text-sm text-zinc-600">{pathname}</div>
          <button
            className="text-sm rounded-md border border-zinc-200 px-3 py-1.5 hover:bg-zinc-50"
            onClick={() => {
              clearToken();
              router.push("/login");
            }}
          >
            退出登录
          </button>
        </header>
        <main className="min-h-0 flex-1 overflow-y-auto p-6">{children}</main>
      </div>
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <NotificationProvider>
      <AppShellInner>{children}</AppShellInner>
    </NotificationProvider>
  );
}
