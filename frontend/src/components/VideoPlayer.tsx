"use client";

import { useEffect, useRef } from "react";

interface VideoPlayerProps {
  deviceKey: string;
  channelNo: number;
  accessToken: string;
  onError?: (msg: string) => void;
}

export function VideoPlayer({ deviceKey, channelNo, accessToken, onError }: VideoPlayerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const playerRef = useRef<any>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || !deviceKey || !accessToken) return;

    let cancelled = false;

    async function initPlayer() {
      try {
        const { default: EZUIKit } = await import("ezuikit-js");

        if (cancelled || !container) return;

        const divId = `ezuikit-${deviceKey}-${channelNo}`;
        container.innerHTML = `<div id="${divId}" style="width:100%;height:480px;"></div>`;

        const ezopenUrl = `ezopen://open.ys7.com/${deviceKey}/${channelNo}.hd.live`;

        const player = new EZUIKit.EZUIKitPlayer({
          id: divId,
          url: ezopenUrl,
          accessToken: accessToken,
          decoderPath: "/PlayCtrlWasm",
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
  }, [deviceKey, channelNo, accessToken, onError]);

  return <div ref={containerRef} className="w-full rounded-lg overflow-hidden bg-black" />;
}
