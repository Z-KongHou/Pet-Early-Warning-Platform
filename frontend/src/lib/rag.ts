import { apiFetch } from "@/lib/http";

export type RagSource = {
  source: string;
  filename: string;
  chunk_index: number | null;
  excerpt: string;
  score: number;
};

export type RagChatHistoryMessage = {
  role: "user" | "assistant";
  content: string;
};

export type RagQueryResult = {
  question: string;
  answer: string;
  sources: RagSource[];
  llm_model: string;
  detected_language: string;
  english_question?: string | null;
};

export type RagStreamMeta = {
  question: string;
  sources: RagSource[];
  llm_model: string;
  detected_language: string;
  english_question?: string | null;
};

export type RagStreamHandlers = {
  onMeta?: (meta: RagStreamMeta) => void;
  onDelta?: (text: string) => void;
  onStatus?: (phase: string) => void;
  onReplace?: (text: string) => void;
  onDone?: (result: RagQueryResult) => void;
  onError?: (message: string, code?: number) => void;
};

export type RagCollectionStats = {
  collection: string;
  document_count: number;
  persist_dir: string;
};

function apiBase(): string {
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? "";
}

function parseSseBlock(block: string): { event: string; data: string } | null {
  const lines = block.split("\n").filter((l) => l.length > 0);
  if (!lines.length) return null;
  let event = "message";
  const dataLines: string[] = [];
  for (const line of lines) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
  }
  if (!dataLines.length) return null;
  return { event, data: dataLines.join("\n") };
}

function dispatchStreamEvent(
  event: string,
  raw: string,
  handlers: RagStreamHandlers
): void {
  let payload: Record<string, unknown> = {};
  try {
    payload = JSON.parse(raw) as Record<string, unknown>;
  } catch {
    handlers.onError?.("流式响应解析失败");
    return;
  }

  switch (event) {
    case "meta":
      handlers.onMeta?.(payload as unknown as RagStreamMeta);
      break;
    case "delta":
      if (typeof payload.text === "string") handlers.onDelta?.(payload.text);
      break;
    case "status":
      if (typeof payload.phase === "string") handlers.onStatus?.(payload.phase);
      break;
    case "replace":
      if (typeof payload.text === "string") handlers.onReplace?.(payload.text);
      break;
    case "done":
      handlers.onDone?.(payload as unknown as RagQueryResult);
      break;
    case "error":
      handlers.onError?.(
        typeof payload.message === "string" ? payload.message : "问答失败",
        typeof payload.code === "number" ? payload.code : undefined
      );
      break;
    default:
      break;
  }
}

export async function queryRagStream(
  question: string,
  handlers: RagStreamHandlers,
  options?: { topK?: number; history?: RagChatHistoryMessage[]; signal?: AbortSignal }
): Promise<void> {
  const url = `${apiBase()}/api/rag/query/stream`;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Request-Id": crypto.randomUUID(),
  };

  const res = await fetch(url, {
    method: "POST",
    headers,
    body: JSON.stringify({
      question,
      ...(options?.topK != null ? { top_k: options.topK } : {}),
      ...(options?.history?.length ? { history: options.history } : {}),
    }),
    cache: "no-store",
    signal: options?.signal,
  });

  if (!res.ok) {
    const text = await res.text();
    let message = `HTTP ${res.status}`;
    try {
      const body = JSON.parse(text) as { message?: string };
      if (body.message) message = body.message;
    } catch {
      /* non-json error body */
    }
    handlers.onError?.(message);
    return;
  }

  if (!res.body) {
    handlers.onError?.("流式响应为空");
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const blocks = buffer.split("\n\n");
      buffer = blocks.pop() ?? "";
      for (const block of blocks) {
        const parsed = parseSseBlock(block);
        if (parsed) dispatchStreamEvent(parsed.event, parsed.data, handlers);
      }
    }
    if (buffer.trim()) {
      const parsed = parseSseBlock(buffer);
      if (parsed) dispatchStreamEvent(parsed.event, parsed.data, handlers);
    }
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") return;
    handlers.onError?.(e instanceof Error ? e.message : "流式连接中断");
  }
}

export async function fetchRagStats(): Promise<RagCollectionStats> {
  return apiFetch<RagCollectionStats>("/api/rag/stats");
}
