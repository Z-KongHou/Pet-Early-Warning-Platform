"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { connectAlertSse, type AlertPayload } from "@/lib/sse";
import { apiFetch } from "@/lib/http";
import { authHeaders } from "@/lib/authed";

type NotificationContextValue = {
  /** Current unread message count */
  unreadCount: number;
  /** Manually refresh unread count from API */
  refreshUnread: () => Promise<void>;
  /** Latest alert payload received via SSE (null if none yet) */
  lastAlert: AlertPayload | null;
  /** Timestamp of the last SSE alert, used to trigger list refresh */
  alertVersion: number;
};

const NotificationContext = createContext<NotificationContextValue>({
  unreadCount: 0,
  refreshUnread: async () => {},
  lastAlert: null,
  alertVersion: 0,
});

export function useNotifications() {
  return useContext(NotificationContext);
}

export function NotificationProvider({ children }: { children: ReactNode }) {
  const [unreadCount, setUnreadCount] = useState(0);
  const [lastAlert, setLastAlert] = useState<AlertPayload | null>(null);
  const [alertVersion, setAlertVersion] = useState(0);
  const sseRef = useRef<ReturnType<typeof connectAlertSse> | null>(null);

  const refreshUnread = useCallback(async () => {
    try {
      const data = await apiFetch<{ count: number }>(
        "/api/messages/unread-count",
        { headers: authHeaders() }
      );
      setUnreadCount(data.count);
    } catch {
      // Silently ignore — component handles error display
    }
  }, []);

  // Initial unread count fetch
  useEffect(() => {
    refreshUnread();
  }, [refreshUnread]);

  // SSE connection lifecycle
  useEffect(() => {
    const sse = connectAlertSse({
      onConnected: () => {
        console.log("Notification SSE connected");
      },
      onAlert: (payload: AlertPayload) => {
        setLastAlert(payload);
        setUnreadCount((prev) => prev + 1);
        setAlertVersion((v) => v + 1);
      },
      onError: (msg: string) => {
        console.warn("Notification SSE:", msg);
      },
    });
    sseRef.current = sse;

    return () => {
      sse.close();
      sseRef.current = null;
    };
  }, []);

  return (
    <NotificationContext.Provider
      value={{ unreadCount, refreshUnread, lastAlert, alertVersion }}
    >
      {children}
    </NotificationContext.Provider>
  );
}
