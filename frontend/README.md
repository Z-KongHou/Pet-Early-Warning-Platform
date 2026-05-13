# Frontend (Next.js) Demo

仓鼠健康预警 AIoT 系统前端 demo（Next.js + TypeScript + Tailwind）。内置 mock API（基于 Next.js `app/api` 路由），用于快速演示页面骨架与接口联调方式。

## 运行

在 `frontend/` 目录执行：

```bash
pnpm dev
```

打开 `http://localhost:3000`。

## Demo 账号

- username: `admin`
- password: `password123`

## 已实现页面

- `/login`：登录（调用 `POST /api/auth/login`）
- `/dashboard`：仪表盘（调用 `GET /api/auth/me`）
- `/hamsters`：仓鼠列表（调用 `GET /api/hamsters`）
- `/cameras`：摄像头列表（调用 `GET /api/cameras`）
- `/users/me/cameras`：我的摄像头（绑定/解绑/列表，对应 `user_cameras` 映射）

## mock API 说明

- **mock 数据**：`src/lib/mock/store.ts`（进程内存态）
- **mock 接口**：`src/app/api/**/route.ts`
