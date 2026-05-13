# Pet-Early-Warning-Platform（yingshi）

仓鼠健康预警 AIoT 平台：用户、仓鼠档案、萤石类摄像头绑定与令牌、活动采样与历史、预警与站内消息、系统阈值配置，以及基于大模型的活动分析（智谱 Chat Completions）。仓库按前后端分目录，前端通过 Next.js Route Handlers 将浏览器请求代理到 Spring Boot。

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | [Next.js](https://nextjs.org/) 16、[React](https://react.dev/) 19、TypeScript、[Tailwind CSS](https://tailwindcss.com/) 4 |
| 后端 | Spring Boot 2.7、Java 11、[MyBatis-Plus](https://baomidou.com/)、Spring Security、JJWT |
| 数据 | MySQL 8（库名默认 `yingshi_database`，逻辑删除字段 `is_deleted`） |
| 其他 | 可配置智谱 GLM 等 OpenAI 兼容 Chat API（见后端 `application.yml` 中 `ai` 段） |

## 目录结构

| 路径 | 说明 |
|------|------|
| `frontend/` | Next.js 应用；`src/app/api/**` 将同源 `/api/*` 转发至后端（见 `src/lib/backend-proxy.ts`） |
| `backend/` | Spring Boot 应用，主类 `com.hamster.yingshi.YingshiApplication`，默认监听 **8081** |
| `backend/sql/init.sql` | 建库、建表、默认配置与演示账号 |
| `docs/` | `api-specification.md`（接口说明）、`database-schema.md`（表结构说明）等 |

## 功能模块（后端路由前缀）

- `/api/auth`：登录等认证
- `/api/health`：健康检查（`GET /api/health`）
- `/api/hamsters`：仓鼠档案
- `/api/cameras`：摄像头 CRUD、令牌、快照、流地址等
- `/api/users/me/cameras`：当前用户与摄像头绑定关系
- `/api/alerts`、`/api/messages`：预警与消息
- `/api/activity`：活动统计、历史、趋势
- `/api/analysis`：活动分析（调用配置的 AI 服务）
- `/api/settings`：系统配置项

详细请求体与响应见 `docs/api-specification.md`。

## 环境要求

- **前端**：Node.js（建议 LTS）、[pnpm](https://pnpm.io/)
- **后端**：JDK 11、Maven 3.6+
- **数据库**：MySQL 8，可本地或远程实例

## 数据库初始化

1. 启动 MySQL，使用有建库权限的账号。
2. 执行 `backend/sql/init.sql`（会创建库 `yingshi_database`、表及初始 `settings` 数据）。
3. 将后端 `spring.datasource.url` / `username` / `password` 改成你的实例（见下节）。

初始化脚本中的**演示账号**（与前端登录页 Demo 一致）：用户名 `admin`，密码 `password123`。生产环境请立即修改密码或删除该用户。

## 本地开发

### 1. 后端

在 `backend/` 目录：

```bash
mvn spring-boot:run
```

默认端口与数据源见 `backend/src/main/resources/application.yml`（当前为 **8081**、`jdbc:mysql://localhost:3306/yingshi_database`）。生产或协作时请通过环境变量或独立配置文件覆盖数据源、JWT 密钥与 AI Key，**勿将真实密钥提交到仓库**。

连通性自检：`GET http://127.0.0.1:8081/api/health`。

### 2. 前端

在 `frontend/` 目录：

```bash
pnpm install
pnpm dev
```

开发时 Next 默认 `http://localhost:3000`。浏览器调用同源 `/api/...`，由服务端转发到后端。

若后端不在 `http://127.0.0.1:8081`，可在前端环境变量中设置 **`BACKEND_URL`** 或 **`API_PROXY_TARGET`**（二者等价，优先 `BACKEND_URL`），例如：

```bash
set BACKEND_URL=http://127.0.0.1:8081
pnpm dev
```

（Linux/macOS 使用 `export BACKEND_URL=...`。）

### 3. 构建与生产启动（前端）

```bash
pnpm build
pnpm start
```

## 文档

- 接口：`docs/api-specification.md`
- 数据库：`docs/database-schema.md`
