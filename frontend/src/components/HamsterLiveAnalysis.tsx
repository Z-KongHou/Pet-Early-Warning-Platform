"use client";

import { useCallback, useEffect, useRef, useState, type MutableRefObject } from "react";
import type { EZUIKitPlayerInstance } from "@/components/VideoPlayer";
import { authHeaders } from "@/lib/authed";
import { ApiError } from "@/lib/http";
import {
  ANALYSIS_FRAME_COUNT,
  ANALYSIS_FRAME_INTERVAL_MS,
  analyzeHamsterImages,
  captureSequentialFrames,
  type HamsterAnalyzeResult,
} from "@/lib/hamster-analysis";

interface HamsterLiveAnalysisProps {
  cameraId: number;
  playerRef: MutableRefObject<EZUIKitPlayerInstance | null>;
  /** 萤石 accessToken（与直播流同源），用于宠物检测 API */
  ezvizAccessToken?: string;
  /** 与左侧视频列等高，避免分析结果撑高外层卡片 */
  maxHeight?: number;
}

const STATUS_LABEL: Record<string, string> = {
  normal: "正常",
  low: "偏低",
  critical: "异常",
};

const STATUS_COLOR: Record<string, string> = {
  normal: "bg-emerald-100 text-emerald-800",
  low: "bg-amber-100 text-amber-800",
  critical: "bg-red-100 text-red-800",
};

/** 阶段一：3s 内 0→42% */
const PROGRESS_PHASE1_MS = 3_000;
const PROGRESS_PHASE1_TARGET = 42;
/** 阶段二：每秒 +5%，上限 72% */
const PROGRESS_PHASE2_RATE_PER_SEC = 5;
const PROGRESS_PHASE2_MAX = 72;

export function HamsterLiveAnalysis({
  cameraId,
  playerRef,
  ezvizAccessToken,
  maxHeight,
}: HamsterLiveAnalysisProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const rampFrameRef = useRef<number | null>(null);
  const progressRef = useRef(0);
  const previewUrlRef = useRef<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  /** 用户手动上传/拖拽的参考图（可多张），优先于直播抓帧 */
  const [uploadedFiles, setUploadedFiles] = useState<File[]>([]);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<HamsterAnalyzeResult | null>(null);
  const [lastAnalyzedAt, setLastAnalyzedAt] = useState<Date | null>(null);
  const [playerReady, setPlayerReady] = useState(false);

  const heightLocked = maxHeight !== undefined && maxHeight > 0;

  const stopProgressRamp = useCallback(() => {
    if (rampFrameRef.current !== null) {
      cancelAnimationFrame(rampFrameRef.current);
      rampFrameRef.current = null;
    }
  }, []);

  useEffect(() => {
    const check = () => {
      const player = playerRef.current;
      setPlayerReady(!!player?.capturePicture || !!player?.id);
    };
    check();
    const id = window.setInterval(check, 500);
    return () => window.clearInterval(id);
  }, [playerRef]);

  useEffect(() => {
    previewUrlRef.current = previewUrl;
  }, [previewUrl]);

  useEffect(() => {
    return () => {
      stopProgressRamp();
      const url = previewUrlRef.current;
      if (url?.startsWith("blob:")) URL.revokeObjectURL(url);
    };
  }, [stopProgressRamp]);

  const setPreviewBlob = useCallback((file: File) => {
    setPreviewUrl((prev) => {
      if (prev?.startsWith("blob:")) URL.revokeObjectURL(prev);
      return URL.createObjectURL(file);
    });
  }, []);

  const pickImageFiles = useCallback((fileList: FileList | File[]) => {
    return Array.from(fileList).filter((f) => f.type.startsWith("image/"));
  }, []);

  const setUploadedReferences = useCallback(
    (files: File[]) => {
      const images = pickImageFiles(files);
      if (images.length === 0) return;
      setUploadedFiles(images);
      setPreviewBlob(images[images.length - 1]!);
      setError(null);
    },
    [pickImageFiles, setPreviewBlob]
  );

  const clearUploadedReferences = useCallback(() => {
    setUploadedFiles([]);
    setPreviewUrl((prev) => {
      if (prev?.startsWith("blob:")) URL.revokeObjectURL(prev);
      return null;
    });
  }, []);

  const startProgressRamp = useCallback(() => {
    stopProgressRamp();
    const startTime = performance.now();
    const tick = (now: number) => {
      const elapsed = now - startTime;
      let value: number;
      if (elapsed <= PROGRESS_PHASE1_MS) {
        value = (elapsed / PROGRESS_PHASE1_MS) * PROGRESS_PHASE1_TARGET;
      } else {
        const phase2Sec = (elapsed - PROGRESS_PHASE1_MS) / 1000;
        value = Math.min(
          PROGRESS_PHASE2_MAX,
          PROGRESS_PHASE1_TARGET + phase2Sec * PROGRESS_PHASE2_RATE_PER_SEC
        );
      }
      progressRef.current = value;
      setProgress(value);
      if (value < PROGRESS_PHASE2_MAX) {
        rampFrameRef.current = requestAnimationFrame(tick);
      }
    };
    rampFrameRef.current = requestAnimationFrame(tick);
  }, [stopProgressRamp]);

  const finishProgress = useCallback(async () => {
    stopProgressRamp();
    progressRef.current = 100;
    setProgress(100);
    await new Promise((r) => setTimeout(r, 220));
  }, [stopProgressRamp]);

  const startAnalysis = useCallback(async () => {
    const player = playerRef.current;
    const useUploadedReference = uploadedFiles.length > 0;
    const useLiveCapture =
      !useUploadedReference && playerReady && !!player && (!!player.capturePicture || !!player.id);

    if (!useUploadedReference && !useLiveCapture) {
      setError("播放器尚未就绪，请先上传图片或等待视频加载");
      return;
    }

    setLoading(true);
    progressRef.current = 0;
    setProgress(0);
    setError(null);
    stopProgressRamp();
    startProgressRamp();

    try {
      let data: HamsterAnalyzeResult;

      const analyzeOptions = ezvizAccessToken
        ? { ezvizAccessToken }
        : undefined;

      if (useUploadedReference) {
        data = await analyzeHamsterImages(
          uploadedFiles,
          cameraId,
          authHeaders(),
          analyzeOptions
        );
      } else {
        const files = await captureSequentialFrames(
          player!,
          ANALYSIS_FRAME_COUNT,
          ANALYSIS_FRAME_INTERVAL_MS,
          (_index, file) => setPreviewBlob(file)
        );
        data = await analyzeHamsterImages(files, cameraId, authHeaders(), analyzeOptions);
      }

      await finishProgress();
      setResult(data);
      setLastAnalyzedAt(new Date());
    } catch (e) {
      stopProgressRamp();
      progressRef.current = 0;
      setProgress(0);
      setResult(null);
      setError(e instanceof ApiError ? e.message : e instanceof Error ? e.message : "分析失败");
    } finally {
      setLoading(false);
    }
  }, [
    cameraId,
    finishProgress,
    playerReady,
    playerRef,
    setPreviewBlob,
    startProgressRamp,
    stopProgressRamp,
    uploadedFiles,
    ezvizAccessToken,
  ]);

  const onFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files;
      if (files?.length) setUploadedReferences(files);
      e.target.value = "";
    },
    [setUploadedReferences]
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const files = pickImageFiles(e.dataTransfer.files);
      if (files.length) setUploadedReferences(files);
    },
    [pickImageFiles, setUploadedReferences]
  );

  const score = result?.activity_score ?? 0;
  const statusKey = result?.activity_status ?? "normal";
  const canAnalyze = !loading && (playerReady || uploadedFiles.length > 0);

  return (
    <div
      className={`w-full lg:w-[360px] shrink-0 flex flex-col gap-2 rounded-lg border border-zinc-200 bg-zinc-50 p-3 min-h-0 ${
        heightLocked ? "overflow-hidden" : ""
      }`}
      style={heightLocked ? { height: maxHeight, maxHeight } : undefined}
    >
      <div className="shrink-0 text-sm font-medium text-zinc-900">仓鼠状态分析</div>

      <div
        className={`relative shrink-0 rounded-md border border-dashed border-zinc-300 bg-white overflow-hidden flex items-center justify-center transition-colors ${
          heightLocked ? "h-20" : "aspect-video"
        } ${loading ? "pointer-events-none opacity-80" : "cursor-pointer hover:border-zinc-400"}`}
        onClick={() => !loading && fileInputRef.current?.click()}
        onDragOver={(e) => !loading && e.preventDefault()}
        onDrop={onDrop}
        role="button"
        tabIndex={loading ? -1 : 0}
        onKeyDown={(e) => e.key === "Enter" && !loading && fileInputRef.current?.click()}
      >
        {previewUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={previewUrl} alt="分析预览" className="w-full h-full object-contain" />
        ) : (
          <span className="text-xs text-zinc-400 px-3 text-center leading-snug">
            点击开始分析后自动采样画面；也可一次选择多张参考图
          </span>
        )}
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          multiple
          className="hidden"
          onChange={onFileChange}
        />
      </div>

      <div className="shrink-0 flex flex-col gap-1.5">
        {uploadedFiles.length > 0 && !loading && (
          <div className="flex items-center justify-between gap-2">
            <span className="text-[10px] text-zinc-500">
              将分析已上传的 {uploadedFiles.length} 张参考图
            </span>
            <button
              type="button"
              className="text-[10px] text-zinc-600 underline hover:text-zinc-900"
              onClick={clearUploadedReferences}
            >
              改用直播抓帧
            </button>
          </div>
        )}
        <button
          type="button"
          disabled={!canAnalyze}
          onClick={startAnalysis}
          className="w-full rounded-md bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-zinc-800 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? "分析中…" : "开始分析"}
        </button>

        {loading && (
          <div className="space-y-1" aria-live="polite" aria-busy="true">
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-zinc-200">
              <div
                className={`h-full rounded-full bg-zinc-900 ease-out ${
                  progress >= 100 ? "transition-[width] duration-200" : ""
                }`}
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        )}
      </div>

      {error && (
        <div className="shrink-0 rounded-md border border-red-200 bg-red-50 px-2 py-1.5 text-xs text-red-700">
          {error}
        </div>
      )}

      <div
        className={`min-h-0 text-sm ${
          heightLocked ? "flex-1 overflow-y-auto overscroll-contain" : ""
        }`}
      >
        {result ? (
          <div className="space-y-2 pr-0.5">
            <div className="flex items-center gap-2">
              <div
                className="relative flex h-11 w-11 shrink-0 items-center justify-center rounded-full border-[3px] border-zinc-200"
                style={{
                  borderTopColor: score >= 70 ? "#10b981" : score >= 40 ? "#f59e0b" : "#ef4444",
                  transform: "rotate(-90deg)",
                }}
              >
                <span className="text-sm font-semibold text-zinc-900" style={{ transform: "rotate(90deg)" }}>
                  {score}
                </span>
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5 flex-wrap">
                  <span className="text-xs font-medium text-zinc-900">活动评分</span>
                  <span
                    className={`rounded-full px-1.5 py-0.5 text-[10px] ${STATUS_COLOR[statusKey] ?? STATUS_COLOR.normal}`}
                  >
                    {STATUS_LABEL[statusKey] ?? statusKey}
                  </span>
                </div>
                <p className="mt-0.5 text-[11px] text-zinc-600 leading-snug">{result.description}</p>
              </div>
            </div>

            <p className="rounded-md bg-white border border-zinc-200 px-2 py-1.5 text-[11px] text-zinc-800 leading-snug">
              {result.analysis_result}
            </p>

            <dl className="grid grid-cols-2 gap-x-2 gap-y-1 text-[11px]">
              <dt className="text-zinc-500">检测到仓鼠</dt>
              <dd className="text-zinc-900">{result.has_pet ? "是" : "否"}</dd>
              <dt className="text-zinc-500">运动状态</dt>
              <dd className="text-zinc-900">{result.is_moving ? "活动中" : "静止"}</dd>
              <dt className="text-zinc-500">进食状态</dt>
              <dd className="text-zinc-900">{result.is_eating ? "进食中" : "未在食盆"}</dd>
              <dt className="text-zinc-500">食盆</dt>
              <dd className="text-zinc-900">{result.food_status || "未知"}</dd>
              <dt className="text-zinc-500">置信度</dt>
              <dd className="text-zinc-900">{(result.confidence * 100).toFixed(1)}%</dd>
            </dl>

            {(result.anomaly.long_stationary || result.anomaly.no_eating) && (
              <div className="rounded-md border border-amber-200 bg-amber-50 px-2 py-1.5 text-[11px] text-amber-900 space-y-0.5">
                {result.anomaly.long_stationary && <p>长时间未移动</p>}
                {result.anomaly.no_eating && <p>长时间未到食盆进食</p>}
              </div>
            )}
          </div>
        ) : (
          !loading &&
          !error && (
            <p className="text-[11px] text-zinc-400 leading-snug">
              点击「开始分析」即可自动采样并得出活动与进食结论
            </p>
          )
        )}
      </div>

      {lastAnalyzedAt && (
        <p className="shrink-0 text-[10px] text-zinc-400 pt-0.5 border-t border-zinc-200/80">
          上次分析：{lastAnalyzedAt.toLocaleString("zh-CN")}
        </p>
      )}
    </div>
  );
}
