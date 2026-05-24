"use client";

import { useEffect, useRef } from "react";

interface VideoPlayerProps {
  deviceKey: string;
  channelNo: number;
  accessToken: string;
  mode?: "live" | "playback";
  startTime?: string;
  endTime?: string;
  onError?: (msg: string) => void;
}

export function VideoPlayer({ deviceKey, channelNo, accessToken, mode = "live", startTime, endTime, onError }: VideoPlayerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const playerRef = useRef<any>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || !deviceKey || !accessToken) return;

    let cancelled = false;

    async function initPlayer() {
      try {
        const mod = await import("ezuikit-js");
        const EZUIKitPlayer = mod.EZUIKitPlayer || mod.default?.EZUIKitPlayer || mod.default;

        if (cancelled || !container) return;

        const divId = `ezuikit-${deviceKey}-${channelNo}`;
        container.innerHTML = `<div id="${divId}" style="width:100%;height:480px;"></div>`;

        const ezopenUrl = mode === "playback"
          ? `ezopen://open.ys7.com/${deviceKey}/${channelNo}.cloud.rec?begin=${startTime}&end=${endTime}`
          : `ezopen://open.ys7.com/${deviceKey}/${channelNo}.live`;

        const player = new EZUIKitPlayer({
          id: divId,
          url: ezopenUrl,
          accessToken: accessToken,
          template: "simple",
          width: 800,
          height: 450,
          handleError: (err: any) => {
            console.error("EZUIKit error:", err);
            onError?.(`播放错误: ${JSON.stringify(err)}`);
          },
        });

        playerRef.current = player;
      } catch (e) {
        console.error("Failed to init EZUIKit:", e);
        onError?.(`初始化播放器失败: ${e instanceof Error ? e.message : String(e)}`);
      }
    }

    initPlayer();

    return () => {
      cancelled = true;
      if (playerRef.current) {
        try {
          playerRef.current.stop && playerRef.current.stop();
        } catch {}
        playerRef.current = null;
      }
      if (container) {
        container.innerHTML = "";
      }
    };
  }, [deviceKey, channelNo, accessToken, mode, startTime, endTime, onError]);

  return <div ref={containerRef} className="w-full rounded-lg overflow-hidden bg-black" />;
}
