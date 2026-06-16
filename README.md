# Pet-Early-Warning-Platform（yingshi）

仓鼠健康预警 AIoT 平台：用户注册与登录、仓鼠档案、萤石摄像头绑定与实时预览、云录制/云点播回放、定时抓帧 AI 分析、活动历史与预警、站内消息、系统阈值配置，以及基于 Hybrid RAG + ReAct Agent 的仓鼠养护智能问答。

## 系统架构

```
浏览器 (Next.js :3000)
    │  同源 /api/* 代理
    ├──────────────────► Spring Boot 后端 (:8081) ──► MySQL 8
    │                         │ 定时抓帧 / 活动分析
    └─ /api/hamster/* ────────┼─ /api/rag/* ────────► Python AI 服务 (:8000)
                              │                         ├─ 萤石 pet_detection
                              └─ 萤石 Open API           ├─ 食盆 / 运动规则
                              │                         ├─ ChromaDB + BM25 Hybrid RAG
                              │                         ├─ DeepSeek LLM + ReAct Agent
                              │                         └─ 偏好提取（异步）
                              │
                              └─ Ollama (:11434) ──────► 嵌入模型 (nomic-embed-text)
                                                          翻译 / 本地 LLM (qwen2.5)
```

AI 服务通过 `/api/internal/*` 内部接口回写后端 MySQL（帧数据、宠物状态、分析历史），Agent 通过 `execute_sql` 工具经后端安全查询数据库。

| 服务 | 端口 | 职责 |
|------|------|------|
| `frontend/` | 3000 | Web UI；Next.js Route Handlers 将 `/api/*` 转发至后端或 AI 服务 |
| `backend/` | 8081 | 业务 API、JWT 认证、萤石集成、定时抓帧调度、帧/状态数据管理、Agent SQL 安全执行 |
| `ai/` | 8000 | 仓鼠图像分析、Hybrid RAG（向量+BM25 RRF 融合+LLM 重排序）、ReAct Agent、流式问答 |
| `ollama` | 11434 | 嵌入向量生成 (`nomic-embed-text`)、翻译与可选本地 LLM (`qwen2.5`) |
| `mysql` | 3306 | MySQL 8 主数据库（库名 `yingshi_database`） |

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | [Next.js](https://nextjs.org/) 16、[React](https://react.dev/) 19、TypeScript、[Tailwind CSS](https://tailwindcss.com/) 4、[recharts](https://recharts.org/) 3、react-markdown、萤石 EZUIKit 9 |
| 后端 | Spring Boot 2.7.18、Java 17、[MyBatis-Plus](https://baomidou.com/) 3.5.3、Spring Security、JJWT 0.11.5 |
| AI 服务 | Python 3.10+、FastAPI 0.104、Poetry、ChromaDB 0.6、LangChain（core + community + Ollama）、jieba + rank-bm25、httpx |
| 数据 | MySQL 8（库名 `yingshi_database`，逻辑删除字段 `is_deleted`） |
| 外部 | 萤石开放平台（直播、云存储、云点播、pet_detection）、DeepSeek API（LLM）、Ollama（嵌入） |

## 目录结构

| 路径 | 说明 |
|------|------|
| `frontend/` | Next.js 16 应用；`src/app/api/**` Route Handlers 代理后端与 AI 服务 |
| `backend/` | Spring Boot 应用，主类 `com.hamster.yingshi.YingshiApplication` |
| `ai/` | FastAPI 仓鼠分析与 Hybrid RAG 微服务，详见 [`ai/README.md`](ai/README.md) |
| `backend/sql/init.sql` | 建库、建表（11 张表）、默认配置与演示账号 |
| `backend/sql/migrations/` | 增量迁移脚本（多租户 `user_id`、`pet_analysis`、`frame_images`、`pet_state`） |
| `docs/` | API 规范、数据库 Schema、RAG 优化历程与实施文档、萤石云录制/点播说明 |

### AI 服务子结构

```
ai/src/
  main.py              FastAPI 应用入口
  config.py            全量配置（环境变量 + 默认值 + LLM 别名映射）
  api/
    routes/            hamster (仓鼠分析)、rag (入库/问答/流式/统计)、health
    schemas/           Pydantic 请求/响应模型
    deps.py            FastAPI 依赖注入（全部服务懒初始化）
    middleware/        请求体大小限制
  clients/
    llm/               DeepSeek OpenAI-compatible 客户端、Ollama 本地 LLM
    backend_client.py  HTTP 客户端，调用后端 /api/internal/* 读写数据
    ezviz_client.py    萤石 pet_detection API
    embedding_client.py Ollama 嵌入向量生成
    image_processor.py 图像压缩
    timestamp_extractor.py EXIF 时间戳提取
  repositories/
    vector_store.py    ChromaDB 向量存储封装
    bm25_index.py      BM25 关键词索引（jieba + rank-bm25）
    frame_repository.py  帧图像存储（通过 BackendClient → MySQL）
    state_repository.py  宠物状态追踪（通过 BackendClient → MySQL pet_state）
    facts_repository.py  结构化兽医知识库
    preference_repository.py  用户偏好与宠物档案存储
    protocols.py       仓储接口协议
  services/
    hamster/           仓鼠检测、食盆分析、运动评分、活动评分、编排用例
    rag/
      agent/           ReAct Agent 循环 + 工具注册表 + 4 个工具
        tools/         execute_sql、search_knowledge_base、lookup_structured_facts、get_user_context
      extraction/      结构化事实提取、用户偏好提取
      generation/      提示构建（含 facts/prefs 注入）、答案验证
      ingest/          文档加载（PDF/HTML/TXT/DOCX）、清洗、分块
      orchestration/   入库管道（ingest）、3 层查询管道（query）
      retrieval/       向量检索、Hybrid 检索（向量+BM25 RRF 融合）、LLM 重排序、查询改写、查询翻译
      routing/         意图路由（问候快速路径）
      utils/           对话历史管理、语言检测
  utils/               SSE 流式输出、统一响应格式、JWT 转发认证、JSON 解析
```

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

- **定时抓帧分析**：`FrameCaptureService` 每 5 分钟抓取在线摄像头画面（ffmpeg 取流 → 单帧 JPEG），调用 AI `/api/hamster/analyze` 分析，结果写入 `pet_analysis` 与 `activity_history`，并通过 Spring 事件机制触发预警与消息通知
- **帧数据管理**：`FrameDataService` 管理帧图像存储（`frame_images` 表），按摄像头 LRU 淘汰（最多 500 帧/摄像头），跟踪检测状态（stored → sampled → analyzed）
- **宠物状态追踪**：`pet_state` 表维护每摄像头维度的宠物位置、静止时长、进食时间、食盆位置等持久化状态；AI 服务通过 BackendClient → `/api/internal/pet-state` 读写
- **手动实时分析**：摄像头页 `HamsterLiveAnalysis` 组件，前端直连 AI `/api/hamster/analyze`，上传多图，AI 在 3 分钟时间窗口内对比帧间位移与食盆状态
- 活动统计、历史、趋势（`/api/activity`）
- 预警记录与处理状态（`/api/alerts`）
- 站内消息通知（`/api/messages`）

### AI 与问答

- **仓鼠图像分析**：萤石 `pet_detection` + 本地食盆分析（蓝色占比检测）+ 帧间运动位移对比 + 加权活动评分（movement 40% / food 25% / presence 20% / anomaly 15%）
- **Hybrid RAG 问答 — 3 层查询架构**：
  1. **问候快速路径**：正则匹配问候语，0 次检索，直接 LLM 回复
  2. **Agent 模式**（`RAG_AGENT_ENABLED=true` 时优先）：LLM 自主决策调用 4 个工具（`execute_sql` 查库、`search_knowledge_base` 搜知识库、`lookup_structured_facts` 查医学事实、`get_user_context` 取用户偏好），最多 5 轮工具调用后生成最终回答
  3. **固定管道**（Agent 关闭或失败时回退）：查询改写（指代消解+多查询+关键词提取）→ 混合检索（向量 ChromaDB + BM25 jieba → RRF 融合）→ LLM 重排序 → 答案生成（含结构化事实注入、偏好注入、答案验证）
- **查询优化**：DeepSeek 驱动的指代消解与多查询改写、多语言翻译（中↔英，Ollama qwen2.5）
- **知识库入库**：支持 PDF / HTML / TXT / DOCX 文档的加载、HTML 清洗、递归分块（512 chars / 100 overlap）、向量化（Ollama nomic-embed-text）+ BM25 索引同步
- **用户偏好学习**：异步线程从每轮对话中提取用户偏好与宠物档案（名称、品种、年龄、病史），注入后续回答
- **流式问答**：`/api/rag/query/stream` SSE 流式输出（先推 meta+来源，再逐片推 delta）
- 前端「AI 问答」页（`/chat`）对接 RAG 流式接口，支持 Markdown 渲染

### 系统配置

- 按用户维度的阈值与采样间隔（`/api/settings`）
- 云录制模板查询（`/api/templates`）

### 后端内部接口（AI 服务专用）

后端暴露 `/api/internal/*` 接口供 AI 服务调用，不走前端代理：

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/internal/frames` | POST/GET | 帧记录增删查、时间窗口查询、LRU 淘汰 |
| `/api/internal/frames/{id}/detection` | PUT | 更新帧检测结果 |
| `/api/internal/frames/batch-status` | PUT | 批量更新帧状态 |
| `/api/internal/frames/batch-touch` | PUT | 批量更新最后访问时间 |
| `/api/internal/pet-state` | GET/PUT | 宠物持久化状态读写 |
| `/api/internal/pet-analysis/history` | GET | 分析历史查询 |
| `/api/internal/query` | POST | Agent SQL 安全执行（仅 SELECT，表白名单，最多 100 行） |
| `/api/internal/agent-context` | GET | 聚合仓鼠/摄像头/设置上下文 |

详细请求体与响应见 [`docs/api-specification.md`](docs/api-specification.md)。

## 前端页面

| 路径 | 功能 |
|------|------|
| `/login` | 登录 / 注册 |
| `/dashboard` | 仪表盘概览 |
| `/hamsters` | 仓鼠列表与档案管理 |
| `/cameras` | 摄像头管理、直播预览、云录像回放、实时 AI 分析 |
| `/activity` | 活动量统计与趋势图表 |
| `/alerts` | 预警列表与处理 |
| `/messages` | 站内信（已读/未读） |
| `/chat` | RAG 养护智能问答 |
| `/settings` | 系统阈值配置 |
| `/users/me/cameras` | 我的摄像头绑定管理 |

## 数据库

共 11 张业务表：

| 表 | 说明 |
|------|------|
| `users` | 用户账户（BCrypt 密码哈希） |
| `hamsters` | 仓鼠档案（品种、体重、性别、健康状态，软删除） |
| `cameras` | 摄像头信息（萤石设备序列号、令牌、通道、在线状态、录制开关） |
| `user_cameras` | 用户-摄像头绑定映射（软删除，唯一约束） |
| `alerts` | 预警记录（活动状态、分数、阈值、处理状态与备注） |
| `messages` | 站内消息通知（关联仓鼠与预警，已读状态） |
| `activity_history` | 活动量历史记录（分数、状态、AI 分析详情） |
| `settings` | 用户系统阈值与采样间隔配置（key-value，按 user_id 唯一） |
| `pet_analysis` | 定时 AI 分析结果（宠物检测、运动状态、食盆状态、位置、置信度） |
| `frame_images` | 帧图像存储（按摄像头 LRU 淘汰，含检测结果与状态流转） |
| `pet_state` | 每摄像头宠物持久化状态（位置、进食时间、静止起始、食盆 ROI、分析计数） |

所有业务表均通过 `user_id` 外键实现多租户隔离，并使用 MyBatis-Plus 逻辑删除（`is_deleted`）。

## 环境要求

- **前端**：Node.js 20 LTS、[pnpm](https://pnpm.io/)
- **后端**：JDK 17、Maven 3.6+
- **AI 服务**：Python 3.10+、[Poetry](https://python-poetry.org/) 2.x；RAG 嵌入需本地 [Ollama](https://ollama.com/)（模型 `nomic-embed-text`）
- **数据库**：MySQL 8

## 数据库初始化

1. 启动 MySQL，使用有建库权限的账号。
2. 全新安装执行 `backend/sql/init.sql`（创建库 `yingshi_database`、11 张表及初始数据）。
3. 已有旧库时，按序执行 `backend/sql/migrations/` 下脚本：
   - `001_user_id_multi_tenant.sql` — 多租户 user_id 改造
   - `002_pet_analysis.sql` — 定时分析结果表
   - `003_frame_images_and_pet_state.sql` — 帧图像与宠物状态表
4. 将后端 `spring.datasource.*` 改为你的实例（见下节）。

演示账号（与登录页一致）：用户名 `admin`，密码 `password123`。**生产环境请立即修改或删除。**

## 本地开发

需同时启动三个服务（顺序不限，但前端依赖后两者）。Ollama 需单独安装并拉取模型。

### 0. Ollama（RAG 嵌入必需）

```bash
ollama serve                      # 默认 :11434
ollama pull nomic-embed-text      # 嵌入模型（必需）
ollama pull qwen2.5:0.5b          # 翻译与本地 LLM（可选）
```

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
cp .env.example .env   # 按需填写 DeepSeek API Key、萤石 Token 等
poetry run uvicorn main:app --app-dir src --host 0.0.0.0 --port 8000 --reload
```

文档：http://127.0.0.1:8000/docs

后端通过 `ai.service-url`（默认 `http://127.0.0.1:8000`）调用本服务。

关键环境变量（完整列表见 `ai/.env.example`）：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `LLM_API_KEY` | (空) | DeepSeek API Key（问答/改写/重排序必需） |
| `LLM_MODEL` | `dsv4` | DeepSeek 模型名（别名映射：`dsv4`→`deepseek-v4-flash`，`dsv4-pro`→`deepseek-v4-pro`） |
| `LLM_BASE_URL` | `https://api.deepseek.com/v1` | LLM API 地址（OpenAI 兼容） |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Ollama 地址 |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text` | 嵌入模型名 |
| `EZVIZ_ACCESS_TOKEN` | (空) | 萤石开放平台令牌 |
| `BACKEND_URL` | `http://127.0.0.1:8081` | 后端 REST 地址 |
| `RAG_HYBRID_ENABLED` | `true` | 启用 BM25+向量混合检索（RRF 融合） |
| `RAG_RERANK_ENABLED` | `true` | 启用 LLM 重排序 |
| `RAG_QUERY_REWRITE_ENABLED` | `true` | 启用查询改写（指代消解+多查询+关键词） |
| `RAG_AGENT_ENABLED` | `false` | 启用 Agent 工具调用模式（需 DeepSeek API） |
| `RAG_TOP_K` | `12` | 最终返回给 LLM 的检索结果数 |
| `RAG_RRF_K` | `60` | RRF 融合常数 |

### 3. 前端

```bash
cd frontend
pnpm install
pnpm dev
```

浏览器访问 http://localhost:3000。同源 `/api/...` 由 Next.js Route Handlers 服务端转发。

环境变量（可选）：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `BACKEND_URL` | `http://127.0.0.1:8081` | Spring Boot 地址 |
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
- RAG 优化历程：[`docs/hybrid-rag-optimization-journey.md`](docs/hybrid-rag-optimization-journey.md)
- RAG 3 天实施计划：[`docs/hybrid-rag-3day-plan.md`](docs/hybrid-rag-3day-plan.md)
- RAG 实施博客：[`docs/hybrid-rag-3day-implementation-blog.md`](docs/hybrid-rag-3day-implementation-blog.md)
- ChromaDB 调试记录：[`docs/debugging-chromadb-hybrid-rag.md`](docs/debugging-chromadb-hybrid-rag.md)
- 基础设施优化：[`docs/infrastructure-optimization-plan.md`](docs/infrastructure-optimization-plan.md)
- EZUIKit 已知问题：[`docs/ezuikit-known-issues.md`](docs/ezuikit-known-issues.md)
- 萤石云录制/点播：[`docs/云录制说明.txt`](docs/云录制说明.txt)、[`docs/云点播说明.txt`](docs/云点播说明.txt)
