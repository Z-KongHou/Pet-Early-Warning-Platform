/**
 * SSE connection manager for real-time alert notifications.
 *
 * Uses browser EventSource to subscribe to backend SSE endpoint.
 * Includes exponential-backoff reconnection and event dispatch.
 */

import { getToken } from "@/lib/auth-client";

export type AlertPayload = {
  alertId: number;
  messageId: number;
  hamsterId: number;
  activityStatus: string;
  activityScore: number;
  title: string;
  content: string;
  createdAt: string;
};

export type SseHandlers = {
  onAlert?: (payload: AlertPayload) => void;
  onConnected?: () => void;
  onError?: (message: string) => void;
};

/**
 * SSE must connect directly to the backend (browser EventSource cannot
 * go through Next.js API route proxy for long-lived connections).
 * Uses NEXT_PUBLIC_API_BASE_URL if set, otherwise defaults to the
 * Spring Boot port (same default as backend-proxy.ts).
 */
function backendBase(): string {
  if (process.env.NEXT_PUBLIC_API_BASE_URL) {
    return process.env.NEXT_PUBLIC_API_BASE_URL.replace(/\/$/, "");
  }
  return "http://127.0.0.1:8081";
}

/**
 * Managed SSE connection with auto-reconnect.
 *
 * Usage:
 *   const sse = connectAlertSse({
 *     onAlert: (p) => console.log("New alert:", p),
 *   });
 *   // later: sse.close();
 */
export function connectAlertSse(handlers: SseHandlers) {
  const token = getToken();
  if (!token) {
    console.warn("SSE: no token, skipping connection");
    return { close: () => {} };
  }

  const baseUrl = backendBase();
  const url = `${baseUrl}/api/notifications/subscribe?token=${encodeURIComponent(token)}`;

  let es: EventSource | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let retries = 0;
  const MAX_RETRIES = 8;
  const MAX_BACKOFF = 30_000; // 30 seconds max

  function scheduleReconnect() {
    if (reconnectTimer) clearTimeout(reconnectTimer);
    if (retries >= MAX_RETRIES) {
      handlers.onError?.("SSE connection failed after max retries (giving up)");
      return;
    }
    const delay = Math.min(1000 * Math.pow(2, retries), MAX_BACKOFF);
    reconnectTimer = setTimeout(connect, delay);
    retries++;
  }

  function connect() {
    if (es) {
      es.close();
      es = null;
    }

    es = new EventSource(url);

    es.addEventListener("connected", () => {
      retries = 0;
      handlers.onConnected?.();
    });

    es.addEventListener("alert", (event: MessageEvent) => {
      try {
        const payload = JSON.parse(event.data) as AlertPayload;
        handlers.onAlert?.(payload);
      } catch (e) {
        console.error("SSE: failed to parse alert payload", e);
      }
    });

    es.addEventListener("heartbeat", () => {
      // keep-alive, no action needed
    });

    es.onerror = () => {
      es?.close();
      es = null;
      if (retries < MAX_RETRIES) {
        handlers.onError?.("SSE connection lost, reconnecting...");
      }
      scheduleReconnect();
    };
  }

  connect();

  return {
    close() {
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (es) {
        es.close();
        es = null;
      }
    },
  };
}
