# Pet-Early-Warning-Platform（yingshi）

仓鼠健康预警 AIoT 平台：用户注册与登录、仓鼠档案、萤石摄像头绑定与实时预览、云录制/云点播回放、定时抓帧 AI 分析、活动历史与预警、站内消息、系统阈值配置，以及基于 RAG 的仓鼠养护问答。

## 系统架构

```
浏览器 (Next.js :3000)
    │  同源 /api/* 代理
    ├──────────────────► Spring Boot 后端 (:8081) ──► MySQL 8
    │                         │ 定时抓帧 / 活动分析
    └─ /api/hamster/* ────────┼─ /api/rag/* ────────► Python AI 服务 (:8000)
                              │                         ├─ 萤石 pet_detection
                              └─ 萤石 Open API           ├─ 食盆 / 运动规则
                                                         └─ Chroma RAG + LLM
```

| 服务 | 端口 | 职责 |
|------|------|------|
| `frontend/` | 3000 | Web UI；Route Handlers 将 `/api/*` 转发至后端或 AI 服务 |
| `backend/` | 8081 | 业务 API、JWT 认证、萤石集成、定时抓帧调度 |
| `ai/` | 8000 | 仓鼠图像分析、知识库入库、RAG 多轮问答 |

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | [Next.js](https://nextjs.org/) 16、[React](https://react.dev/) 19、TypeScript、[Tailwind CSS](https://tailwindcss.com/) 4、萤石 EZUIKit |
| 后端 | Spring Boot 2.7、Java 11、[MyBatis-Plus](https://baomidou.com/)、Spring Security、JJWT |
| AI 服务 | Python 3.10+、FastAPI、Poetry、ChromaDB、LangChain |
| 数据 | MySQL 8（库名 `yingshi_database`，逻辑删除字段 `is_deleted`） |
| 外部 | 萤石开放平台（直播、云存储、云点播、pet_detection）、智谱 GLM 等 OpenAI 兼容 API、Ollama 嵌入 |

## 目录结构

| 路径 | 说明 |
|------|------|
| `frontend/` | Next.js 应用；`src/app/api/**` 代理后端；`src/app/api/rag/**`、`hamster/analyze` 代理 AI 服务 |
| `backend/` | Spring Boot 应用，主类 `com.hamster.yingshi.YingshiApplication` |
| `ai/` | FastAPI 仓鼠分析与 RAG 微服务，详见 [`ai/README.md`](ai/README.md) |
| `backend/sql/init.sql` | 建库、建表、默认配置与演示账号 |
| `backend/sql/migrations/` | 增量迁移（多租户 `user_id`、`pet_analysis` 表等） |
| `docs/` | `api-specification.md`、`database-schema.md`、萤石云录制/点播说明 |

## 已实现功能

### 用户与权限

- 登录 / 注册（`POST /api/auth/login`、`POST /api/auth/register`），JWT Bearer 认证
- 多租户数据隔离：业务表均含 `user_id` 外键，按当前用户过滤
- 用户与摄像头绑定（`user_cameras` 映射表，软删除）

### 仓鼠与摄像头

- 仓鼠档案 CRUD（`/api/hamsters`）
- 摄像头 CRUD、令牌刷新、实时流地址、快照（`/api/cameras`）
- 实时预览与云点播回放（EZUIKit + 萤石云存储 API）
- 云录制启停、录像日历、云端文件列表与播放

### 健康监测

- **定时抓帧分析**：`FrameCaptureService` 每 5 分钟抓取在线摄像头画面，调用 AI 服务分析，结果写入 `pet_analysis` 与 `activity_history`
- **手动实时分析**：摄像头页 `HamsterLiveAnalysis` 组件，前端直连 AI `/api/hamster/analyze`
- 活动统计、历史、趋势（`/api/activity`）
- 预警记录与处理状态（`/api/alerts`）
- 站内消息通知（`/api/messages`）

### AI 与问答

- Python 服务：萤石 `pet_detection` + 本地食盆/运动规则 + 活动评分
- RAG 知识库入库与多轮流式问答（`/api/rag/ingest`、`/api/rag/query`、`/api/rag/query/stream`）
- 前端「AI 问答」页（`/chat`）对接 RAG 流式接口

### 系统配置

- 按用户维度的阈值与采样间隔（`/api/settings`）
- 云录制模板查询（`/api/templates`）

详细请求体与响应见 [`docs/api-specification.md`](docs/api-specification.md)。

## 前端页面

| 路径 | 功能 |
|------|------|
| `/login` | 登录 / 注册 |
| `/dashboard` | 仪表盘概览 |
| `/hamsters` | 仓鼠列表 |
| `/cameras` | 摄像头管理、直播、云录像、实时 AI 分析 |
| `/activity` | 活动量统计与趋势 |
| `/alerts` | 预警列表 |
| `/messages` | 站内信 |
| `/chat` | RAG 养护问答 |
| `/settings` | 系统阈值配置 |
| `/users/me/cameras` | 我的摄像头绑定 |

## 环境要求

- **前端**：Node.js LTS、[pnpm](https://pnpm.io/)
- **后端**：JDK 11、Maven 3.6+
- **AI 服务**：Python 3.10+、[Poetry](https://python-poetry.org/) 2.x；RAG 嵌入需本地 [Ollama](https://ollama.com/)
- **数据库**：MySQL 8

## 数据库初始化

1. 启动 MySQL，使用有建库权限的账号。
2. 全新安装执行 `backend/sql/init.sql`（创建库 `yingshi_database`、表及初始数据）。
3. 已有旧库时，按序执行 `backend/sql/migrations/` 下脚本。
4. 将后端 `spring.datasource.*` 改为你的实例（见下节）。

演示账号（与登录页一致）：用户名 `admin`，密码 `password123`。生产环境请立即修改或删除。

## 本地开发

需同时启动三个服务（顺序不限，但前端依赖后两者）。

### 1. 数据库与后端

```bash
cd backend
mvn spring-boot:run
```

默认 **8081**，数据源见 `backend/src/main/resources/application.yml`。生产环境请通过环境变量或独立配置覆盖数据源、JWT 密钥、萤石与 AI Key，**勿将真实密钥提交到仓库**。

自检：`GET http://127.0.0.1:8081/api/health`

### 2. AI 服务

```bash
cd ai
poetry install
cp .env.example .env   # 按需填写萤石 Token、LLM Key 等
poetry run uvicorn main:app --app-dir src --host 0.0.0.0 --port 8000 --reload
```

文档：http://127.0.0.1:8000/docs

后端通过 `ai.service-url`（默认 `http://127.0.0.1:8000`）调用本服务。

### 3. 前端

```bash
cd frontend
pnpm install
pnpm dev
```

浏览器访问 http://localhost:3000。同源 `/api/...` 由 Next.js 服务端转发。

环境变量（可选）：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `BACKEND_URL` / `API_PROXY_TARGET` | `http://127.0.0.1:8081` | Spring Boot 地址 |
| `AI_SERVICE_URL` | `http://127.0.0.1:8000` | Python AI 服务地址 |

PowerShell 示例：

```powershell
$env:BACKEND_URL = "http://127.0.0.1:8081"
$env:AI_SERVICE_URL = "http://127.0.0.1:8000"
pnpm dev
```

### 4. 生产构建（前端）

```bash
pnpm build
pnpm start
```

## 文档

- 接口规范：[`docs/api-specification.md`](docs/api-specification.md)
- 数据库：[`docs/database-schema.md`](docs/database-schema.md)
- AI 服务：[`ai/README.md`](ai/README.md)
- 前端：[`frontend/README.md`](frontend/README.md)
- 萤石云录制/点播：[`docs/云录制说明.txt`](docs/云录制说明.txt)、[`docs/云点播说明.txt`](docs/云点播说明.txt)
