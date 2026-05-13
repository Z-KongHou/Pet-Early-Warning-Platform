"use client";

import { useCallback, useRef, useState } from "react";

type RefreshButtonProps = {
  onRefresh: () => Promise<void>;
  className?: string;
  /** 默认「刷新」 */
  label?: string;
};

export function RefreshButton({ onRefresh, className = "", label = "刷新" }: RefreshButtonProps) {
  const [refreshing, setRefreshing] = useState(false);
  const guard = useRef(false);

  const handleClick = useCallback(async () => {
    if (guard.current) return;
    guard.current = true;
    setRefreshing(true);
    try {
      await onRefresh();
    } catch {
      // 列表页多在 onRefresh 外处理错误；此处仍结束 loading
    } finally {
      guard.current = false;
      setRefreshing(false);
    }
  }, [onRefresh]);

  return (
    <button
      type="button"
      className={[
        "inline-flex cursor-pointer items-center justify-center gap-1.5 rounded-md border border-zinc-200 px-3 py-2 text-sm text-zinc-800",
        "transition-[transform,colors,box-shadow] duration-150 ease-out",
        "hover:border-zinc-300 hover:bg-zinc-50",
        "active:scale-[0.97] active:bg-zinc-100",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-900/20 focus-visible:ring-offset-2",
        "disabled:pointer-events-none disabled:opacity-55",
        className,
      ].join(" ")}
      disabled={refreshing}
      aria-busy={refreshing}
      aria-label={refreshing ? `${label}中` : label}
      onClick={handleClick}
    >
      <svg
        className={`h-4 w-4 shrink-0 cursor-pointer text-zinc-600 transition-transform ${refreshing ? "animate-spin" : ""}`}
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden
      >
        <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
        <path d="M3 3v5h5" />
        <path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16" />
        <path d="M16 16h5v5" />
      </svg>
      <span className={["cursor-pointer", refreshing && "text-zinc-500"].filter(Boolean).join(" ")}>{label}</span>
    </button>
  );
}
