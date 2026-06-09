# Frontend（Next.js）

仓鼠健康预警 AIoT 系统前端：Next.js 16 + TypeScript + Tailwind CSS。页面通过同源 `/api/*` 调用 Route Handlers，由服务端代理至 Spring Boot（8081）或 Python AI 服务（8000）。

## 运行

在 `frontend/` 目录：

```bash
pnpm install
pnpm dev
```

打开 http://localhost:3000。需先启动后端与（可选）AI 服务，见根目录 [`README.md`](../README.md)。

环境变量（可选）：

- `BACKEND_URL` / `API_PROXY_TARGET`：后端地址，默认 `http://127.0.0.1:8081`
- `AI_SERVICE_URL`：AI 服务地址，默认 `http://127.0.0.1:8000`

## 演示账号

- 用户名：`admin`
- 密码：`password123`

也可在登录页注册新账号。

## 页面路由

| 路径 | 说明 |
|------|------|
| `/login` | 登录 / 注册 |
| `/dashboard` | 仪表盘 |
| `/hamsters` | 仓鼠档案 |
| `/cameras` | 摄像头、直播、云录像、实时分析 |
| `/activity` | 活动统计与趋势 |
| `/alerts` | 预警 |
| `/messages` | 站内信 |
| `/chat` | RAG 养护问答 |
| `/settings` | 系统配置 |
| `/users/me/cameras` | 摄像头绑定 |

## API 代理

- **后端业务**：`src/app/api/**/route.ts` 多数通过 `src/lib/backend-proxy.ts` 转发至 Spring Boot 同路径接口。
- **AI 分析**：`src/app/api/hamster/analyze` → AI 服务。
- **RAG 问答**：`src/app/api/rag/query`、`/stream`、`/stats` → AI 服务。

客户端请求使用 `src/lib/http.ts`（`apiFetch`）与 `src/lib/auth-client.ts`（JWT 存储）。

## 关键组件

- `VideoPlayer`：萤石 EZUIKit 直播/回放
- `HamsterLiveAnalysis`：摄像头页实时 AI 分析面板
- `AppShell`：侧边栏布局与导航
- `RequireAuth`：受保护路由鉴权
