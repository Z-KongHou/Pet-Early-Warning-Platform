export type ApiResponse<T> = {
  code: number;
  message: string;
  data: T;
  requestId?: string;
};

export type Pagination<T> = {
  list: T[];
  total: number;
  page?: number;
  size?: number;
};

export type User = {
  id: number;
  username: string;
  email?: string;
};

export type Hamster = {
  id: number;
  name: string;
  breed?: string;
  birthDate?: string;
  gender?: 0 | 1 | 2;
  weight?: number;
  avatar?: string;
  remark?: string;
  healthStatus: 0 | 1 | 2;
  createdAt?: string;
};

export type Camera = {
  id: number;
  hamsterId: number;
  name: string;
  deviceKey: string;
  channelNo: number;
  onlineStatus: 0 | 1;
  lastOnlineTime?: string;
};

export type UserCameraBinding = {
  cameraId: number;
  name: string;
  onlineStatus: 0 | 1;
};

export type ActivityStatus = "normal" | "low" | "high";

/** 对应表 `activity_history`，与 `GET /api/activity/history` 列表项一致 */
export type ActivityHistory = {
  id: number;
  hamsterId: number;
  cameraId?: number;
  activityScore?: number;
  /** 活动判定，如 normal / low / high */
  status?: string;
  analysisResult?: string;
  imageUrl?: string;
  createdAt?: string;
};

export type Alert = {
  id: number;
  hamsterId: number;
  activityStatus: ActivityStatus;
  activityScore: number;
  threshold: number;
  imageUrl?: string;
  status: 0 | 1 | 2;
  createdAt?: string;
};

export type Message = {
  id: number;
  hamsterId: number;
  alertId: number;
  title: string;
  content: string;
  isRead: 0 | 1;
  createdAt?: string;
};

export type Setting = {
  id?: number;
  keyName: string;
  keyValue: string;
  description?: string | null;
  createdAt?: string;
  updatedAt?: string;
};
