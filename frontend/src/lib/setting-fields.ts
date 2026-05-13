/** 与后端 `settings` 表初始数据及业务含义对齐，用于表单控件与展示顺序 */
export type SettingFieldKind = "seconds" | "score0_100" | "secret" | "text";

export type SettingFieldMeta = {
  label: string;
  kind: SettingFieldKind;
  /** 展示在标题下的补充说明（可与库里的 description 并存） */
  hint?: string;
};

export const SETTING_KNOWN_ORDER: string[] = [
  "activity_interval",
  "low_activity_threshold",
  "high_activity_threshold",
  "deepseek_api_key",
];

export const SETTING_FIELD_META: Record<string, SettingFieldMeta> = {
  activity_interval: {
    label: "采样间隔",
    kind: "seconds",
    hint: "活动分析请求之间的间隔，单位：秒。",
  },
  low_activity_threshold: {
    label: "低活动阈值",
    kind: "score0_100",
    hint: "活动评分低于该值时判定为低活动。",
  },
  high_activity_threshold: {
    label: "高活动阈值",
    kind: "score0_100",
    hint: "活动评分高于该值时判定为高活动。",
  },
  deepseek_api_key: {
    label: "DeepSeek API 密钥",
    kind: "secret",
    hint: "用于 AI 分析接口调用，请妥善保管。",
  },
};

export function sortSettingsByKnownOrder<T extends { keyName: string }>(list: T[]): T[] {
  const rank = new Map(SETTING_KNOWN_ORDER.map((k, i) => [k, i]));
  return [...list].sort((a, b) => {
    const ra = rank.get(a.keyName);
    const rb = rank.get(b.keyName);
    if (ra !== undefined && rb !== undefined) return ra - rb;
    if (ra !== undefined) return -1;
    if (rb !== undefined) return 1;
    return a.keyName.localeCompare(b.keyName);
  });
}
