# 仓鼠健康预警 AIoT 系统 - 接口设计规范

## 一、接口规范

### 1.1 基础规范

- 基础路径：`/api`
- 通信协议：HTTP/HTTPS
- 数据格式：JSON
- 字符编码：UTF-8
- 认证方式：Bearer Token
- 时间格式：ISO8601 UTC（示例：`2026-04-22T10:00:00Z`）
- 允许方法：`GET` / `POST` / `DELETE`
- **JSON 命名**：请求体与响应 `data` 中的业务字段统一为 **camelCase**（与 Spring Boot / Jackson 默认一致），例如 `hamsterId`、`createdAt`、`expiresIn`、`deviceKey`。

### 1.2 统一响应格式

成功时仅包含 `code`、`message`、`data`（**不含** `requestId` 字段）。

```json
{
  "code": 200,
  "message": "success",
  "data": {}
}
```

### 1.3 错误响应

```json
{
  "code": 40001,
  "message": "参数错误",
  "data": null,
  "requestId": "a4d0f2326e6f4c3a9b8f2d910d5aa0a1"
}
```

与后端 `Result` 一致：`code != 200` 时必有 **`requestId`**（优先采用请求头 **`X-Request-Id`**，否则由服务端生成）。成功时 `code == 200` 的响应体**不包含** `requestId` 字段。

### 1.4 HTTP 状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 401 | 未授权 |
| 403 | 禁止访问 |
| 404 | 资源不存在 |
| 409 | 资源冲突 |
| 500 | 服务器错误 |

### 1.5 业务错误码（示例）

| 错误码 | 说明 |
|--------|------|
| 40001 | 参数错误 |
| 40101 | Token 无效或过期 |
| 40401 | 仓鼠不存在 |
| 40402 | 摄像头不存在 |
| 40403 | 预警不存在 |
| 40901 | 资源已存在 |
| 50001 | AI 分析服务异常 |
| 40301 | 无权限访问该资源 |

### 1.6 审计与幂等建议

1. 所有 `POST` 写操作建议记录 `X-Request-Id`，用于链路追踪和审计。
2. 对于创建类接口，建议支持 `Idempotency-Key` 防止重复提交。
3. `DELETE` 接口统一执行软删除（数据库列 `is_deleted=1`、`deleted_at`；若 API 返回删除结果，见各接口的 `isDeleted` / `deletedAt`）。

### 1.7 统一数据权限规则

1. 当前用户的数据可见范围以数据库表 `user_cameras` 为准，仅可访问 `is_deleted=0` 的绑定关系。
2. 所有基于摄像头 ID 的查询（详情、实时流、截图、凭证）都必须先校验用户绑定关系，再返回数据。
3. 摄像头列表接口先按用户绑定关系过滤，再叠加业务过滤条件（查询参数 **`hamsterId`**）。
4. 对无权限访问的资源，返回 `403`，业务错误码建议使用 `40301`。
5. 用户解绑摄像头时，统一执行 `user_cameras` 软删除（`is_deleted=1`、`deleted_at`），不做物理删除。

---

## 二、用户接口

### 2.1 用户登录

```
POST /api/auth/login
Content-Type: application/json

Request:
{
  "username": "admin",
  "password": "password123"
}

Response:
{
  "code": 200,
  "message": "success",
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIs...",
    "expiresIn": 86400
  }
}
```

### 2.2 用户登出

```
POST /api/auth/logout
Authorization: Bearer <token>
```

### 2.3 获取当前用户信息

```
GET /api/auth/me
Authorization: Bearer <token>

Response:
{
  "code": 200,
  "message": "success",
  "data": {
    "id": 1,
    "username": "admin",
    "email": "admin@example.com"
  }
}
```

### 2.4 绑定摄像头到当前用户

```
POST /api/users/me/cameras/bind
Authorization: Bearer <token>
Content-Type: application/json

Request:
{
  "cameraId": 1
}
```

### 2.5 解绑当前用户摄像头

```
POST /api/users/me/cameras/unbind
Authorization: Bearer <token>
Content-Type: application/json

Request:
{
  "cameraId": 1
}
```

说明：
- 解绑为软删除语义：将 `user_cameras` 对应记录更新为 `is_deleted=1`，并写入 `deleted_at`。
- 若该用户当前未绑定该摄像头，可返回成功（幂等）或返回业务错误，建议在实现中统一约定。

### 2.6 获取当前用户摄像头列表

```
GET /api/users/me/cameras
Authorization: Bearer <token>

Response:
{
  "code": 200,
  "message": "success",
  "data": {
    "list": [
      {
        "cameraId": 1,
        "name": "卧室摄像头",
        "onlineStatus": 1
      }
    ],
    "total": 1
  }
}
```

---

## 三、仓鼠管理接口

### 3.1 添加仓鼠

```
POST /api/hamsters
Authorization: Bearer <token>
Content-Type: application/json

Request:
{
  "name": "小黄",
  "breed": "金丝熊",
  "birthDate": "2024-01-01",
  "gender": 1,
  "weight": 120.5,
  "remark": "活泼可爱"
}
```

### 3.2 获取仓鼠列表

```
GET /api/hamsters
Authorization: Bearer <token>

Response:
{
  "code": 200,
  "message": "success",
  "data": {
    "list": [
      {
        "id": 1,
        "name": "小黄",
        "breed": "金丝熊",
        "healthStatus": 0,
        "createdAt": "2026-04-22T10:00:00Z"
      }
    ],
    "total": 1
  }
}
```

### 3.3 获取仓鼠详情

```
GET /api/hamsters/{id}
Authorization: Bearer <token>
```

### 3.4 更新仓鼠信息

```
POST /api/hamsters/{id}
Authorization: Bearer <token>
Content-Type: application/json

Request:
{
  "weight": 125.0,
  "healthStatus": 0,
  "remark": "体重增加"
}
```

### 3.5 删除仓鼠（软删除）

```
DELETE /api/hamsters/{id}
Authorization: Bearer <token>

Response:
{
  "code": 200,
  "message": "success",
  "data": {
    "id": 1,
    "isDeleted": 1,
    "deletedAt": "2026-04-22T10:05:00Z"
  }
}
```

---

## 四、摄像头管理接口

### 4.1 添加摄像头

```
POST /api/cameras
Authorization: Bearer <token>
Content-Type: application/json

Request:
{
  "hamsterId": 1,
  "name": "摄像头1号",
  "deviceKey": "C868012345",
  "channelNo": 1
}
```

### 4.2 获取摄像头列表

```
GET /api/cameras?hamsterId=1
Authorization: Bearer <token>

Response:
{
  "code": 200,
  "message": "success",
  "data": {
    "list": [
      {
        "id": 1,
        "hamsterId": 1,
        "name": "卧室摄像头",
        "deviceKey": "C868012345",
        "onlineStatus": 1,
        "lastOnlineTime": "2026-04-22T10:00:00Z"
      }
    ],
    "total": 1
  }
}
```

说明：
- 默认仅返回当前登录用户在 `user_cameras` 中有效绑定（`is_deleted=0`）的摄像头数据。
- 当传入 **`hamsterId`** 时，在用户可见范围内进行过滤。

### 4.3 获取摄像头详情

```
GET /api/cameras/{id}
Authorization: Bearer <token>
```

说明：
- 仅允许访问当前登录用户已绑定且未解绑（`user_cameras.is_deleted=0`）的摄像头详情。

### 4.4 更新摄像头信息

```
POST /api/cameras/{id}
Authorization: Bearer <token>
Content-Type: application/json

Request:
{
  "name": "客厅摄像头",
  "channelNo": 1
}
```

### 4.5 删除摄像头（软删除）

```
DELETE /api/cameras/{id}
Authorization: Bearer <token>
```

### 4.6 获取实时视频流

```
GET /api/cameras/{id}/stream
Authorization: Bearer <token>
```

说明：
- 仅允许访问当前登录用户已绑定且未解绑的摄像头。

### 4.7 获取截图

```
GET /api/cameras/{id}/snapshot
Authorization: Bearer <token>
```

说明：
- 仅允许访问当前登录用户已绑定且未解绑的摄像头。

---

## 五、摄像头凭证接口（按摄像头独立维护）

### 5.1 更新摄像头萤石凭证

```
POST /api/cameras/{id}/token
Authorization: Bearer <token>
Content-Type: application/json

Request:
{
  "accessToken": "your_access_token",
  "tokenExpires": "2026-12-31T23:59:59Z"
}
```

### 5.2 获取摄像头萤石凭证状态

```
GET /api/cameras/{id}/token
Authorization: Bearer <token>

Response:
{
  "code": 200,
  "message": "success",
  "data": {
    "cameraId": 1,
    "tokenExpires": "2026-12-31T23:59:59Z"
  }
}
```

---

## 六、AI 分析接口

### 6.1 分析活动量

```
POST /api/analysis/activity
Authorization: Bearer <token>
Content-Type: application/json

Request:
{
  "cameraId": 1,
  "imageUrl": "https://[oss-url]/snapshots/xxx.jpg"
}

Response:
{
  "code": 200,
  "message": "success",
  "data": {
    "cameraId": 1,
    "activityScore": 85,
    "status": "normal",
    "description": "仓鼠活动频繁，较为活跃",
    "analysisResult": "仓鼠正在跑轮运动，动作协调有力..."
  }
}
```

---

## 七、预警接口

### 7.1 创建预警

```
POST /api/alerts
Authorization: Bearer <token>
Content-Type: application/json

Request:
{
  "hamsterId": 1,
  "activityStatus": "low",
  "activityScore": 15,
  "threshold": 30,
  "imageUrl": "https://[oss-url]/snapshots/xxx.jpg"
}
```

### 7.2 查询预警列表

```
GET /api/alerts?hamsterId=1&status=0&page=1&size=20
Authorization: Bearer <token>

Response:
{
  "code": 200,
  "message": "success",
  "data": {
    "list": [
      {
        "id": 1,
        "hamsterId": 1,
        "activityStatus": "low",
        "activityScore": 15,
        "threshold": 30,
        "status": 0,
        "createdAt": "2026-04-22T10:00:00Z"
      }
    ],
    "total": 1,
    "page": 1,
    "size": 20
  }
}
```

### 7.3 获取预警详情

```
GET /api/alerts/{id}
Authorization: Bearer <token>
```

### 7.4 更新预警状态

```
POST /api/alerts/{id}/status
Authorization: Bearer <token>
Content-Type: application/json

Request:
{
  "status": 2,
  "handleRemark": "已观察，仓鼠正常进食"
}
```

### 7.5 删除预警（软删除）

```
DELETE /api/alerts/{id}
Authorization: Bearer <token>
```

---

## 八、站内信接口

### 8.1 获取站内信列表

```
GET /api/messages?page=1&size=20&isRead=0
Authorization: Bearer <token>
```

### 8.2 获取站内信详情

```
GET /api/messages/{id}
Authorization: Bearer <token>
```

### 8.3 标记已读

```
POST /api/messages/{id}/read
Authorization: Bearer <token>
```

### 8.4 标记全部已读

```
POST /api/messages/read-all
Authorization: Bearer <token>
```

### 8.5 删除站内信（软删除）

```
DELETE /api/messages/{id}
Authorization: Bearer <token>
```

### 8.6 获取未读消息数

```
GET /api/messages/unread-count
Authorization: Bearer <token>
```

---

## 九、活动量历史接口

### 9.1 查询活动量历史

```
GET /api/activity/history?hamsterId=1&startDate=2024-01-01&endDate=2024-01-07&page=1&size=100
Authorization: Bearer <token>

Response:
{
  "code": 200,
  "message": "success",
  "data": {
    "list": [
      {
        "id": 1,
        "hamsterId": 1,
        "cameraId": 1,
        "activityScore": 65,
        "status": "normal",
        "analysisResult": "…",
        "imageUrl": "https://example.com/snap.jpg",
        "createdAt": "2026-04-22T10:00:00Z"
      }
    ],
    "total": 100,
    "page": 1,
    "size": 100
  }
}
```

### 9.2 获取活动量统计

```
GET /api/activity/statistics?hamsterId=1&period=week
Authorization: Bearer <token>
```

### 9.3 获取活动量趋势

```
GET /api/activity/trend?hamsterId=1&period=day&days=7
Authorization: Bearer <token>
```

---

## 十、系统配置接口

### 10.1 获取配置

```
GET /api/settings/{keyName}
Authorization: Bearer <token>
```

### 10.2 获取所有配置

```
GET /api/settings
Authorization: Bearer <token>
```

### 10.3 更新配置

```
POST /api/settings/{keyName}
Authorization: Bearer <token>
Content-Type: application/json

Request:
{
  "keyValue": "600",
  "description": "采样间隔（秒）"
}
```

---

## 十一、通用分页参数

| 参数 | 类型 | 说明 |
|------|------|------|
| page | INT | 页码，默认1 |
| size | INT | 每页数量，默认20 |

---

## 十二、字段字典与枚举定义

### 12.1 API JSON 与数据库列

- **HTTP JSON**（请求体、`data` 内对象）：字段名一律 **camelCase**（本文档各节示例已对齐）。
- **关系型数据库**（`init.sql` / 表结构）：列名仍为 **snake_case**（如 `hamster_id`、`is_deleted`），与 MyBatis 映射到 Java 实体字段（camelCase）不冲突。

### 12.2 活动状态（统一口径）

| 字段（JSON） | 可选值 | 说明 |
|------|--------|------|
| `activityStatus` / `status` | `normal` / `low` / `high` | 活动状态 |

### 12.3 预警处理状态

| 字段（JSON） | 可选值 | 说明 |
|------|--------|------|
| `alerts.status` | `0`/`1`/`2` | 0未处理，1已读，2已处理 |

### 12.4 软删除（API 返回）

| 字段（JSON） | 可选值 | 说明 |
|------|--------|------|
| `isDeleted` | `0`/`1` | 0未删除，1已删除（若接口返回） |

### 12.5 用户摄像头映射（数据库表 `user_cameras`）

| 列名 | 类型 | 说明 |
|------|------|------|
| `user_id` | INT | 绑定用户ID |
| `camera_id` | INT | 绑定摄像头ID |
| `is_deleted` | TINYINT | 软删除标记，0未删除/1已删除 |

---

## 十三、安全要求

1. 所有接口（除登录外）需携带有效 Token。
2. 密码使用 BCrypt 加密存储。
3. 敏感配置（如 API Key、摄像头 token）需加密存储。
4. 接口请求需记录审计日志（建议包含 `requestId`、用户ID、操作对象、前后值）。
5. 防止 SQL 注入和 XSS 攻击。