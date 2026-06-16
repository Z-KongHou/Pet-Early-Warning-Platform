"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  fetchRagStats,
  queryRagStream,
  type RagChatHistoryMessage,
} from "@/lib/rag";
import { useChatStore, type ChatMessage } from "@/lib/store";

export default function ChatPage() {
  const { messages, addMessage, updateMessage, removeMessage, clearMessages } =
    useChatStore();
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [docCount, setDocCount] = useState<number | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const stats = await fetchRagStats();
        setDocCount(stats.document_count);
      } catch {
        setDocCount(null);
      }
    })();
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  const patchAssistant = useCallback(
    (assistantId: string, patch: Partial<ChatMessage>) => {
      updateMessage(assistantId, patch);
    },
    [updateMessage]
  );

  const send = useCallback(async () => {
    const question = input.trim();
    if (!question || loading) return;

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setErr(null);
    setInput("");
    const history: RagChatHistoryMessage[] = messages
      .filter((m) => m.content.trim() && !m.streaming)
      .map((m) => ({ role: m.role, content: m.content }));
    const assistantId = crypto.randomUUID();
    addMessage({ id: crypto.randomUUID(), role: "user", content: question });
    addMessage({
      id: assistantId,
      role: "assistant",
      content: "",
      streaming: true,
    });
    setLoading(true);

    await queryRagStream(
      question,
      {
        onMeta: (meta) => {
          patchAssistant(assistantId, {
            meta: {
              llm_model: meta.llm_model,
              detected_language: meta.detected_language,
              english_question: meta.english_question,
            },
          });
        },
        onDelta: (text) => {
          // streaming append via store
          const current = useChatStore.getState().messages.find((m) => m.id === assistantId);
          if (current) {
            updateMessage(assistantId, { content: current.content + text });
          }
        },
        onDone: (result) => {
          patchAssistant(assistantId, {
            content: result.answer,
            streaming: false,
            meta: {
              llm_model: result.llm_model,
              detected_language: result.detected_language,
              english_question: result.english_question,
            },
          });
        },
        onError: (message) => {
          setErr(message);
          removeMessage(assistantId);
        },
      },
      { history, signal: controller.signal }
    );

    setLoading(false);
    textareaRef.current?.focus();
  }, [input, loading, messages, patchAssistant]);

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void send();
    }
  };

  return (
    <div className="flex h-[calc(100dvh-3.5rem-3rem)] min-h-[420px] flex-col gap-4">
      <div className="shrink-0">
        <h1 className="text-xl font-semibold">知识库问答</h1>
        <p className="text-sm text-zinc-500">
          基于 RAG 检索仓鼠饲养文档，回答以流式输出；
          {docCount != null ? (
            <>
              向量库约 <span className="font-medium text-zinc-700">{docCount}</span> 条片段。
            </>
          ) : (
            <>未连接 ai 服务或尚未入库。</>
          )}
        </p>
      </div>

      {err ? (
        <div className="shrink-0 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {err}
        </div>
      ) : null}

      <div className="min-h-0 flex-1 overflow-y-auto rounded-xl border border-zinc-200 bg-white p-4">
        {messages.length === 0 ? (
          <div className="flex h-full min-h-[200px] flex-col items-center justify-center text-center text-sm text-zinc-500">
            <p>例如：仓鼠一天需要喝多少水？</p>
            <p className="mt-1">仓鼠突然不爱动可能是什么原因？</p>
          </div>
        ) : (
          <div className="space-y-4">
            {messages.map((m) => (
              <div
                key={m.id}
                className={m.role === "user" ? "flex justify-end" : "flex justify-start"}
              >
                <div
                  className={[
                    "max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap",
                    m.role === "user"
                      ? "bg-zinc-900 text-white"
                      : "border border-zinc-200 bg-zinc-50 text-zinc-900",
                  ].join(" ")}
                >
                  {m.role === "assistant" && m.streaming && !m.content ? (
                    <span className="text-zinc-500">正在生成回答…</span>
                  ) : (
                    <div className="prose prose-sm max-w-none prose-zinc dark:prose-invert">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {m.content}
                      </ReactMarkdown>
                      {m.streaming ? (
                        <span className="ml-0.5 inline-block h-4 w-0.5 animate-pulse bg-zinc-400 align-middle" />
                      ) : null}
                    </div>
                  )}
                  {m.role === "assistant" && !m.streaming && m.meta?.llm_model ? (
                    <p className="mt-2 text-[11px] text-zinc-400">
                      {m.meta.llm_model}
                    </p>
                  ) : null}
                </div>
              </div>
            ))}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      <div className="shrink-0 rounded-xl border border-zinc-200 bg-white p-3">
        <div className="flex gap-2">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            rows={2}
            placeholder="输入问题，Enter 发送，Shift+Enter 换行"
            disabled={loading}
            className="min-h-[52px] flex-1 resize-none rounded-md border border-zinc-200 px-3 py-2 text-sm outline-none focus:border-zinc-400 disabled:bg-zinc-50"
          />
          <button
            type="button"
            onClick={() => void send()}
            disabled={loading || !input.trim()}
            className="shrink-0 self-end rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            发送
          </button>
        </div>
      </div>
    </div>
  );
}
