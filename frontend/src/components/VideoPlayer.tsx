"use client";

import { useEffect, useRef, type MutableRefObject } from "react";

/** Minimal EZUIKit player surface used by capture / parent refs */
export type EZUIKitPlayerInstance = {
  id?: string;
  /**
   * EZUIKit v9: capturePicture(fileName?, arg2?, download?, cloudUpload?)
   * 第二参数传函数（旧版 callback 写法）会被当成 truthy 从而触发浏览器下载。
   */
  capturePicture?: (
    fileName?: string,
    arg2?: boolean,
    download?: boolean,
    cloudUpload?: boolean
  ) => Promise<{ code?: number; data?: { base64?: string; fileName?: string } }> | void;
  stop?: () => void;
};

interface VideoPlayerProps {
  deviceKey: string;
  channelNo: number;
  accessToken: string;
  mode?: "live" | "playback";
  startTime?: string;
  endTime?: string;
  onError?: (msg: string) => void;
  onPlayerReady?: (player: EZUIKitPlayerInstance) => void;
  playerRef?: MutableRefObject<EZUIKitPlayerInstance | null>;
}

function measureContainer(container: HTMLElement): { width: number; height: number } {
  const rect = container.getBoundingClientRect();
  const width = Math.max(Math.floor(rect.width), 320);
  const height = Math.max(Math.floor(rect.height), 180);
  return { width, height };
}

export function VideoPlayer({
  deviceKey,
  channelNo,
  accessToken,
  mode = "live",
  startTime,
  endTime,
  onError,
  onPlayerReady,
  playerRef: externalPlayerRef,
}: VideoPlayerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const internalPlayerRef = useRef<EZUIKitPlayerInstance | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || !deviceKey || !accessToken) return;

    let cancelled = false;
    let resizeObserver: ResizeObserver | null = null;
    let player: EZUIKitPlayerInstance | null = null;

    const assignPlayer = (instance: EZUIKitPlayerInstance | null) => {
      internalPlayerRef.current = instance;
      if (externalPlayerRef) externalPlayerRef.current = instance;
      if (instance) onPlayerReady?.(instance);
    };

    async function initPlayer() {
      try {
        const mod = await import("ezuikit-js");
        const EZUIKitPlayer = mod.EZUIKitPlayer || mod.default?.EZUIKitPlayer || mod.default;

        if (cancelled || !container) return;

        const divId = `ezuikit-${deviceKey}-${channelNo}`;
        const { width, height } = measureContainer(container);
        container.innerHTML = `<div id="${divId}" style="width:100%;height:100%;"></div>`;

        const ezopenUrl =
          mode === "playback"
            ? `ezopen://open.ys7.com/${deviceKey}/${channelNo}.cloud.rec?begin=${startTime}&end=${endTime}`
            : `ezopen://open.ys7.com/${deviceKey}/${channelNo}.live`;

        player = new EZUIKitPlayer({
          id: divId,
          url: ezopenUrl,
          accessToken,
          template: "simple",
          width,
          height,
          handleError: (err: unknown) => {
            console.error("EZUIKit error:", err);
            onError?.(`播放错误: ${JSON.stringify(err)}`);
          },
        }) as EZUIKitPlayerInstance;

        assignPlayer(player);

        resizeObserver = new ResizeObserver(() => {
          if (!player || cancelled || !container) return;
          const next = measureContainer(container);
          const inner = container.querySelector(`#${divId}`) as HTMLElement | null;
          if (inner) {
            inner.style.width = "100%";
            inner.style.height = "100%";
          }
          const maybeResize = player as EZUIKitPlayerInstance & {
            resize?: (w: number, h: number) => void;
          };
          maybeResize.resize?.(next.width, next.height);
        });
        resizeObserver.observe(container);
      } catch (e) {
        console.error("Failed to init EZUIKit:", e);
        onError?.(`初始化播放器失败: ${e instanceof Error ? e.message : String(e)}`);
      }
    }

    initPlayer();

    return () => {
      cancelled = true;
      resizeObserver?.disconnect();
      if (player) {
        try {
          player.stop?.();
        } catch {
          /* ignore */
        }
      }
      assignPlayer(null);
      if (container) {
        container.innerHTML = "";
      }
    };
  }, [deviceKey, channelNo, accessToken, mode, startTime, endTime, onError, onPlayerReady, externalPlayerRef]);

  return (
    <div ref={containerRef} className="h-full w-full overflow-hidden bg-black" />
  );
}
