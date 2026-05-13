import type { Alert, Camera, Hamster, Message, Setting, User } from "@/lib/types";

type UserCamera = { id: number; userId: number; cameraId: number; isDeleted: 0 | 1 };

function isoNow() {
  return new Date().toISOString();
}

type Store = {
  user: User;
  token: string;
  nextIds: {
    hamster: number;
    camera: number;
    alert: number;
    message: number;
    userCamera: number;
    activity: number;
  };
  hamsters: (Hamster & { isDeleted: 0 | 1 })[];
  cameras: (Camera & {
    isDeleted: 0 | 1;
    accessToken?: string;
    tokenExpires?: string;
    updatedAt?: string;
    deletedAt?: string;
  })[];
  alerts: (Alert & { isDeleted: 0 | 1 })[];
  messages: (Message & { isDeleted: 0 | 1 })[];
  activityHistory: ({
    id: number;
    hamsterId: number;
    cameraId: number;
    activityScore: number;
    status: "normal" | "low" | "high";
    analysisResult?: string;
    imageUrl?: string;
    createdAt: string;
  } & { isDeleted: 0 | 1 })[];
  settings: Setting[];
  userCameras: UserCamera[];
};

const g = globalThis as unknown as { __PEWP_STORE__?: Store };

export function getStore(): Store {
  if (g.__PEWP_STORE__) return g.__PEWP_STORE__;

  const store: Store = {
    user: { id: 1, username: "admin", email: "admin@example.com" },
    token: "demo-token",
    nextIds: { hamster: 2, camera: 2, alert: 2, message: 2, userCamera: 2, activity: 2 },
    hamsters: [
      {
        id: 1,
        name: "小黄",
        breed: "金丝熊",
        birthDate: "2024-01-01",
        gender: 1,
        weight: 120.5,
        remark: "活泼可爱",
        healthStatus: 0,
        createdAt: isoNow(),
        isDeleted: 0,
      },
    ],
    cameras: [
      {
        id: 1,
        hamsterId: 1,
        name: "卧室摄像头",
        deviceKey: "C868012345",
        channelNo: 1,
        onlineStatus: 1,
        lastOnlineTime: isoNow(),
        accessToken: "demo-camera-token",
        tokenExpires: new Date(Date.now() + 7 * 86400_000).toISOString(),
        isDeleted: 0,
      },
    ],
    alerts: [
      {
        id: 1,
        hamsterId: 1,
        activityStatus: "low",
        activityScore: 15,
        threshold: 30,
        status: 0,
        imageUrl: "https://example.com/snapshots/1.jpg",
        createdAt: isoNow(),
        isDeleted: 0,
      },
    ],
    messages: [
      {
        id: 1,
        hamsterId: 1,
        alertId: 1,
        title: "⚠️ 低活动量预警",
        content: "检测到小黄活动量异常低...",
        isRead: 0,
        createdAt: isoNow(),
        isDeleted: 0,
      },
    ],
    activityHistory: [
      {
        id: 1,
        hamsterId: 1,
        cameraId: 1,
        activityScore: 15,
        status: "low",
        analysisResult: "仓鼠活动较少，建议观察是否进食/饮水。",
        imageUrl: "https://example.com/snapshots/1.jpg",
        createdAt: isoNow(),
        isDeleted: 0,
      },
    ],
    settings: [
      { keyName: "activity_interval", keyValue: "300", description: "采样间隔（秒）" },
      { keyName: "low_activity_threshold", keyValue: "30", description: "低活动阈值" },
      { keyName: "high_activity_threshold", keyValue: "80", description: "高活动阈值" },
      { keyName: "deepseek_api_key", keyValue: "***", description: "API密钥（加密存储）" },
    ],
    userCameras: [{ id: 1, userId: 1, cameraId: 1, isDeleted: 0 }],
  };

  g.__PEWP_STORE__ = store;
  return store;
}

export function requireAuth(req: Request): User {
  const auth = req.headers.get("authorization") ?? "";
  if (!auth.startsWith("Bearer ")) throw new Error("UNAUTHORIZED");
  const token = auth.slice("Bearer ".length).trim();
  const store = getStore();
  if (token !== store.token) throw new Error("UNAUTHORIZED");
  return store.user;
}

export function softDelete<T extends { isDeleted: 0 | 1 }>(obj: T) {
  obj.isDeleted = 1;
}

export function paginate<T>(items: T[], page?: number, size?: number) {
  const p = page && page > 0 ? page : 1;
  const s = size && size > 0 ? size : 20;
  const start = (p - 1) * s;
  return { list: items.slice(start, start + s), total: items.length, page: p, size: s };
}
