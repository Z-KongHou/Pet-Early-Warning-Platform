"use client";

import { useEffect, useRef } from "react";
import Hls from "hls.js";

interface VideoPlayerProps {
  streamUrl: string;
  protocol?: string;
  onError?: (msg: string) => void;
}

export function VideoPlayer({ streamUrl, protocol, onError }: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const video = videoRef.current;
    if (!video || !streamUrl) return;

    let hls: Hls | null = null;

    if (protocol === "rtmp") {
      onError?.("RTMP 协议无法在浏览器中直接播放，请使用 HLS 流");
      return;
    }

    if (Hls.isSupported()) {
      hls = new Hls({
        maxBufferLength: 10,
        maxMaxBufferLength: 30,
        liveSyncDurationCount: 3,
      });
      hls.loadSource(streamUrl);
      hls.attachMedia(video);
      hls.on(Hls.Events.ERROR, (_event, data) => {
        if (data.fatal) {
          onError?.(`播放错误: ${data.type} - ${data.details}`);
          if (data.type === Hls.ErrorTypes.NETWORK_ERROR) {
            hls?.startLoad();
          } else if (data.type === Hls.ErrorTypes.MEDIA_ERROR) {
            hls?.recoverMediaError();
          }
        }
      });
    } else if (video.canPlayType("application/vnd.apple.mpegurl")) {
      video.src = streamUrl;
    } else {
      onError?.("当前浏览器不支持 HLS 播放");
    }

    return () => {
      hls?.destroy();
    };
  }, [streamUrl, protocol, onError]);

  return (
    <video
      ref={videoRef}
      controls
      autoPlay
      muted
      playsInline
      className="w-full rounded-lg bg-black"
      style={{ maxHeight: "480px" }}
    />
  );
}
