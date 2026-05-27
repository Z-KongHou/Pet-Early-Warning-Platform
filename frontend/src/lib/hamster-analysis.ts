import type { EZUIKitPlayerInstance } from "@/components/VideoPlayer";
import { apiFetch } from "@/lib/http";

export type HamsterAnomaly = {
  long_stationary: boolean;
  no_eating: boolean;
};

export type HamsterAnalyzeResult = {
  has_pet: boolean;
  pet_type: string;
  position: { x: number; y: number; width: number; height: number } | null;
  is_moving: boolean;
  is_eating: boolean;
  food_status: string;
  blue_ratio: number | null;
  anomaly: HamsterAnomaly;
  confidence: number;
  image_time: string | null;
  activity_score: number;
  activity_status: string;
  description: string;
  analysis_result: string;
  camera_id: string;
};

/** 连续抓帧数量与间隔（秒），用于一次分析内建立运动检测所需的历史帧 */
export const ANALYSIS_FRAME_COUNT = 3;
export const ANALYSIS_FRAME_INTERVAL_MS = 1000;
/** 与后端 MAX_BATCH_IMAGES 一致 */
export const ANALYSIS_MAX_UPLOAD_IMAGES = 20;

export type HamsterBatchAnalyzeResponse = {
  results: Array<{
    index: number;
    success: boolean;
    has_pet?: boolean;
    is_moving?: boolean;
    is_in_food_bowl?: boolean;
    food_status?: string;
    anomaly?: HamsterAnomaly;
    confidence?: number;
    activity_score?: number;
    activity_status?: string;
    analysis_result?: string;
    error?: string;
  }>;
  summary: {
    success_count: number;
    failed_count: number;
  };
};

function activityDescription(score: number): string {
  if (score >= 80) return "仓鼠活动频繁，较为活跃";
  if (score >= 60) return "仓鼠活动正常";
  if (score >= 40) return "仓鼠活动较少，建议关注";
  return "仓鼠活动异常，需要检查";
}

export function pickFinalAnalyzeResult(
  batch: HamsterBatchAnalyzeResponse,
  cameraId: number
): HamsterAnalyzeResult {
  const successful = batch.results.filter((r) => r.success);
  const picked =
    [...successful].reverse().find((r) => r.has_pet) ?? successful.at(-1);
  if (!picked) {
    const failed = batch.results.filter((r) => !r.success);
    const err =
      failed.map((r) => r.error).filter(Boolean).join("；") ||
      "分析失败，未得到有效结果";
    throw new Error(err);
  }
  const score = picked.activity_score ?? 0;
  return {
    has_pet: picked.has_pet ?? false,
    pet_type: "仓鼠",
    position: null,
    is_moving: picked.is_moving ?? false,
    is_eating: picked.is_in_food_bowl ?? false,
    food_status: picked.food_status ?? "未知",
    blue_ratio: null,
    anomaly: picked.anomaly ?? { long_stationary: false, no_eating: false },
    confidence: picked.confidence ?? 0,
    image_time: null,
    activity_score: score,
    activity_status: picked.activity_status ?? "normal",
    description: activityDescription(score),
    analysis_result: picked.analysis_result ?? "",
    camera_id: String(cameraId),
  };
}

export async function analyzeHamsterImages(
  files: File[],
  cameraId: number,
  headers?: Record<string, string>
): Promise<HamsterAnalyzeResult> {
  const form = new FormData();
  for (const file of files) {
    form.append("files", file);
  }
  form.append("camera_id", String(cameraId));

  const batch = await apiFetch<HamsterBatchAnalyzeResponse>("/api/hamster/analyze", {
    method: "POST",
    body: form,
    headers,
  });
  return pickFinalAnalyzeResult(batch, cameraId);
}

export async function analyzeHamsterImage(
  file: File,
  cameraId: number,
  headers?: Record<string, string>
): Promise<HamsterAnalyzeResult> {
  return analyzeHamsterImages([file], cameraId, headers);
}

export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** Extract base64 JPEG from EZUIKit capturePicture result */
export function extractCaptureBase64(data: unknown): string | null {
  if (!data) return null;
  if (typeof data === "string") {
    return data.startsWith("data:") || /^[A-Za-z0-9+/=]+$/.test(data.slice(0, 32)) ? data : null;
  }
  if (typeof data !== "object") return null;

  const obj = data as Record<string, unknown>;
  if (typeof obj.base64 === "string") return obj.base64;

  const nested = obj.data;
  if (typeof nested === "string") return nested;
  if (nested && typeof nested === "object") {
    const inner = nested as Record<string, unknown>;
    if (typeof inner.base64 === "string") return inner.base64;
  }

  return null;
}

/** 从播放器 DOM 内 canvas 截取当前帧，优先取面积最大的渲染画布 */
export function captureFromPlayerCanvas(player: EZUIKitPlayerInstance): string | null {
  if (!player.id) return null;
  const root = document.getElementById(player.id);
  const canvases = root?.querySelectorAll("canvas");
  if (!canvases?.length) return null;

  let best: HTMLCanvasElement | null = null;
  let bestArea = 0;
  for (const node of canvases) {
    if (!(node instanceof HTMLCanvasElement)) continue;
    const area = node.width * node.height;
    if (area > bestArea) {
      bestArea = area;
      best = node;
    }
  }
  if (!best || bestArea === 0) return null;

  try {
    return best.toDataURL("image/jpeg", 0.85);
  } catch {
    return null;
  }
}

/**
 * Capture current frame as base64 via EZUIKit without triggering a browser download.
 * 优先 SDK 内存截图（download=false）；失败时回退到 canvas 截取。
 */
export async function capturePictureBase64(player: EZUIKitPlayerInstance): Promise<string> {
  if (player.capturePicture) {
    try {
      const maybePromise = player.capturePicture(undefined, false, false, false);
      if (maybePromise && typeof maybePromise.then === "function") {
        const payload = await maybePromise;
        const base64 = extractCaptureBase64(payload) ?? extractCaptureBase64(
          payload && typeof payload === "object" && "data" in payload
            ? (payload as { data?: unknown }).data
            : null
        );
        if (base64) return base64;
      }
    } catch {
      /* fallback below */
    }
  }

  const fromCanvas = captureFromPlayerCanvas(player);
  if (fromCanvas) return fromCanvas;

  throw new Error("抓帧失败，未获取到图片数据");
}

export function base64ToFile(base64: string, filename = "capture.jpg"): File {
  const raw = base64.includes(",") ? base64.split(",")[1]! : base64;
  const binary = atob(raw);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return new File([bytes], filename, { type: "image/jpeg" });
}

/** JPEG 魔数 FF D8 FF，且体积合理 */
export function validateJpegBytes(bytes: Uint8Array): boolean {
  if (bytes.length < 512) return false;
  return bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff;
}

export function validateCaptureFile(file: File): boolean {
  return file.type.startsWith("image/") && file.size >= 512;
}

/** 按固定间隔从播放器连续抓帧，供单次分析批量上传 */
export async function captureSequentialFrames(
  player: EZUIKitPlayerInstance,
  count: number,
  intervalMs: number,
  onFrame?: (index: number, file: File) => void
): Promise<File[]> {
  const files: File[] = [];
  for (let i = 0; i < count; i++) {
    if (i > 0) await sleep(intervalMs);
    const base64 = await capturePictureBase64(player);
    if (!base64) throw new Error(`第 ${i + 1} 帧抓图失败`);
    const file = base64ToFile(base64, `capture-${i + 1}.jpg`);
    const buf = new Uint8Array(await file.arrayBuffer());
    if (!validateJpegBytes(buf)) {
      throw new Error(`第 ${i + 1} 帧不是有效 JPEG，请确认视频已正常播放后再分析`);
    }
    files.push(file);
    onFrame?.(i, file);
  }
  return files;
}
