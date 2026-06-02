# yingshi-ai

仓鼠健康监测微服务：调用萤石 `pet_detection` API，结合本地食盆与运动规则分析。

默认端口 **8000**，主接口：

- `GET /health`
- `POST /api/hamster/analyze`（仓鼠健康分析）

RAG 相关模块已预留目录，接口暂未挂载（见 `interfaces/api/routes/rag.py`）。

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

复制 `.env.example` 为 `.env` 并填写（可选；未设置时使用 `src/shared/config.py` 内默认值）：

- `EZVIZ_ACCESS_TOKEN`

Poetry 不会自动加载 `.env`；可在 shell 中 `export`/`$env:` 设置。

## 项目结构（第一阶段）

```
ai/src/
  bootstrap/
    settings.py                     # 配置
    container.py                    # 依赖组装
  main.py                         # FastAPI 入口
  domain/
    models.py                     # 领域模型约定
    repositories.py               # 仓储接口
    services/                     # 领域服务
  application/                    # 应用用例
  infrastructure/
    persistence/                  # 状态仓储、SQLite帧仓储、向量仓储
    external_services/            # 萤石、图像处理、OCR、Embedding、LLM
  interfaces/
    api/routes/                   # HTTP 路由
    api/schemas/                  # 响应封装
    api/dependencies/             # FastAPI Depends
    middlewares/
    ioc/                          # 依赖组装
```

## 与主仓库关系

本服务独立于 Spring Boot（8081）。主项目 `backend` 的 `/api/analysis` 使用智谱 GLM，与本服务未默认打通。

前端通过 Next.js 代理 `frontend/src/app/api/hamster/analyze/route.ts` 转发到本服务 `POST /api/hamster/analyze`（默认 `http://127.0.0.1:8000`，可用环境变量 `AI_SERVICE_URL` 覆盖）。

原 `ai-old/` 已合并进本目录并移除，请统一使用 `ai/` 服务（端口 8000）。
