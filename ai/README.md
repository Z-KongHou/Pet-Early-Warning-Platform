# yingshi-ai

仓鼠健康监测微服务：调用萤石 `pet_detection` API，结合本地食盆与运动规则分析。

默认端口 **8000**，主接口：

- `GET /health`
- `POST /api/hamster/analyze`（仓鼠健康分析）
- `POST /api/rag/ingest`（知识库入库）
- `POST /api/rag/query` / `POST /api/rag/query/stream`（RAG 问答，支持多轮 history）
- `GET /api/rag/stats`（向量库统计）

## 环境要求

- Python 3.10+
- [Poetry](https://python-poetry.org/docs/#installation) 2.x

## 安装与运行

```powershell
cd ai
poetry install
```

开发（热重载，推荐）：

```powershell
poetry run uvicorn main:app --app-dir src --host 0.0.0.0 --port 8000 --reload
```

或使用脚本入口：

```powershell
poetry run yingshi-ai
```

文档：http://127.0.0.1:8000/docs

## 配置

复制 `.env.example` 为 `.env` 并填写（可选；未设置时使用 `src/config.py` 内默认值）：

- `EZVIZ_ACCESS_TOKEN`
- `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL`（RAG 问答）
- `OLLAMA_BASE_URL` / `OLLAMA_EMBED_MODEL`（向量嵌入，需本地 Ollama）
- `RAG_CHAT_MAX_TURNS` / `RAG_CHAT_MAX_HISTORY_TOKENS`（多轮对话历史上限）

服务启动时会自动加载 `ai/.env`（见 `src/config.py`）。

## 项目结构

```
ai/src/
  main.py
  config.py
  api/                   # 路由、schema、deps、middleware
  services/
    hamster/             # 分析编排 + bowl/movement/scoring 等
    rag/                 # ingest、query、chat_history、retriever…
  repositories/          # sqlite frame、memory state、chroma vector
  clients/               # ezviz、embedding、llm、image、timestamp
  utils/                 # response、sse
```

## 与主仓库关系

本服务独立于 Spring Boot（8081）。前端通过 Next.js 代理转发到本服务（默认 `http://127.0.0.1:8000`，可用 `AI_SERVICE_URL` 覆盖）。
