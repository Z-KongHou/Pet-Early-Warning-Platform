# yingshi 优化思路（轻量务实版）

> 基于与 AGI-saber 对比分析后，结合 yingshi 实际场景（739 chunks / 仓鼠兽医 / 单机部署）做的减法优化方案。  
> 核心原则：**不引入重型基础设施，每项改动都能独立交付、立即可用。**

---

## 一、场景定界

在决定"做什么"之前，先明确**不做什么**：

```
当前场景画像：
  - 文档量：12 个 PDF/HTML/TXT，739 个 chunk
  - 领域：仓鼠兽医，术语不超过 200 个
  - 部署：单机，Ollama + FastAPI + Next.js
  - 用户：单人使用（非 SaaS）
  - QPS：< 1（手工问答，非高并发）

这个场景下，以下基础设施是过度设计：
  ❌ Elasticsearch  — 739 chunk，rank-bm25 内存检索 < 10ms，完全够用
  ❌ Neo4j 知识图谱  — 仓鼠疾病关系不超过 100 条，杀鸡用牛刀
  ❌ Milvus          — Chroma 在当前数据量下完全够用
  ❌ Kafka / 消息队列 — 单服务不需要异步解耦
  ❌ 微服务拆分       — 单进程 QPS < 1，没有拆分理由
```

---

## 二、当前 RAG 已有能力（已完成的 3 天优化）

```
用户问题 + history
    ↓
QueryRewriter（DeepSeek：指代消解 + 多 query + keywords）
    ↓
┌──────────────────┬─────────────────┐
│ 向量 (Chroma)     │ BM25 (rank-bm25) │
│ Top-20           │ Top-20          │
└────────┬─────────┴────────┬────────┘
         ↓     RRF (k=60)    ↓
                  ↓
         LLM Reranker → Top-5
                  ↓
         结构化生成（结论/细节/建议/就医 + [N] 引用）
                  ↓
         AnswerValidator（引用校验）
```

**已经比较完善的部分**：检索管线、提问改写、精排、引用校验、feature flag、eval 体系。

**真正缺的部分**：

| 缺口 | 表现 |
|------|------|
| 部署复杂 | 手工启动 Ollama + AI 服务 + 前端三个进程 |
| 分词不专业 | jieba 不认识"湿尾症""颊囊""合笼"等术语 |
| 精准事实查询弱 | "湿尾症用什么药"仍靠向量语义匹配，不直接命中 |
| 无个性化 | 每次都是从零回答，不记得用户的宠物信息 |
| 无 Agent 能力 | 单次问答，不能多步推理或多次调用 RAG |

---

## 三、优化路线（2 周）

```
第 1 周：地基加固（零新依赖）
  Mon: Docker Compose 一键部署
  Tue: jieba 仓鼠兽医自定义词典
  Wed-Thu: SQLite 结构化事实表
  Fri: Health check + 部署验证

第 2 周：智能增强（渐进式）
  Mon-Tue: 用户偏好 + 宠物档案
  Wed-Thu: Agent 路由（RAG as Tool）
  Fri: 全链路验证 + 文档更新
```

---

## 四、第 1 周：地基加固

### 4.1 Docker Compose 一键部署

**现状**：手工开三个终端，分别启动 Ollama、AI 服务、前端。

**方案**：项目根目录加一个 `docker-compose.yml`：

```yaml
services:
  ollama:
    image: ollama/ollama:latest
    ports: ["11434:11434"]
    volumes:
      - ollama_data:/root/.ollama
    # 启动后需手动: docker exec ollama ollama pull nomic-embed-text

  ai:
    build: ./ai
    ports: ["8000:8000"]
    depends_on: [ollama]
    env_file: ./ai/.env
    volumes:
      - ./ai/data:/app/data
      - ./ai/chroma_db:/app/chroma_db

  frontend:
    build: ./frontend
    ports: ["3000:3000"]
    depends_on: [ai]
    environment:
      - AI_SERVICE_URL=http://ai:8000

volumes:
  ollama_data:
```

**产出**：
- `docker-compose.yml`（项目根目录）
- `ai/Dockerfile`（Poetry + uvicorn）
- `frontend/Dockerfile`（Next.js）

**收益**：`docker compose up -d` 一行命令拉起全家桶。新环境不再需要手动配 Python 虚拟环境、Node.js、Ollama。

**工期**：1 天。核心工作就是写 3 个 Dockerfile + 1 个 compose 文件。

### 4.2 jieba 仓鼠兽医自定义词典

**现状问题**：

```python
# jieba 默认分词
list(jieba.cut("仓鼠湿尾症怎么治疗"))
# → ['仓鼠', '湿', '尾症', '怎么', '治疗']   ❌ "湿尾症"被切碎了

list(jieba.cut("仓鼠颊囊发炎"))
# → ['仓鼠', '颊', '囊', '发炎']             ❌ "颊囊"被切碎了
```

BM25 的召回能力直接依赖分词质量。术语被切碎后，关键词匹配失效。

**方案**：在 `ai/data/` 下放一个 `hamster_dict.txt`，增加仓鼠领域术语：

```
# ai/data/hamster_dict.txt
# 每个词一行，格式：词 词频 词性（后两项可选）
湿尾症 5
颊囊 5
合笼 5
木屑垫料 5
叙利亚仓鼠 5
一线仓鼠 5
三线仓鼠 5
熊仔仓鼠 5
纸棉垫料 5
浴沙 5
跑轮 5
磨牙 5
脱肛 5
香腺 5
囤食 5
伪冬眠 5
颊囊炎 5
增生性肠炎 5
Lawsonia intracellularis 5
Clostridioides difficile 5
proliferative ileitis 5
wet tail 5
```

**代码改动**（`bm25_index.py`，加 3 行）：

```python
import jieba

# 启动时加载自定义词典
_dict_path = Path(__file__).resolve().parents[3] / "data" / "hamster_dict.txt"
if _dict_path.exists():
    jieba.load_userdict(str(_dict_path))
```

**验证**：

```python
list(jieba.cut("仓鼠湿尾症怎么治疗"))
# → ['仓鼠', '湿尾症', '怎么', '治疗']   ✅ 术语完整
```

**收益**：BM25 对仓鼠术语的召回精度显著提升。10 分钟见效，零依赖。

**工期**：1 天（整理词典 + 验证分词效果 + 跑 eval 对比）。

### 4.3 SQLite 结构化事实表

**现状问题**：

用户问"湿尾症用什么抗生素"，当前管线是：

```
"湿尾症用什么抗生素" → 译英 → 向量检索 → BM25 → RRF → rerank → 生成
```

这条路靠语义匹配可能找到正确 chunk，但也可能被相似但不相关的 chunk 干扰。精准事实查询（症状→疾病→药物→剂量）应该**直接命中**，不需要绕一圈向量检索。

**方案**：建一张 SQLite 表，ingest 时用 LLM 一次性抽取出结构化事实：

```sql
CREATE TABLE IF NOT EXISTS hamster_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    disease TEXT,
    symptom TEXT,
    pathogen TEXT,
    drug TEXT,
    dosage TEXT,
    source_chunk_id TEXT,
    source_file TEXT,
    confidence REAL DEFAULT 1.0
);

CREATE INDEX IF NOT EXISTS idx_facts_disease ON hamster_facts(disease);
CREATE INDEX IF NOT EXISTS idx_facts_symptom ON hamster_facts(symptom);
```

**数据示例**：

```sql
INSERT INTO hamster_facts (disease, symptom, pathogen, drug, dosage, source_file)
VALUES
  ('湿尾症', '水样腹泻', 'Lawsonia intracellularis', '四环素', '10mg/kg PO q12h 5-7天', 'main.pdf'),
  ('湿尾症', '水样腹泻', 'Clostridioides difficile', '恩诺沙星', '10mg/kg PO', 'Merck.pdf'),
  ('颊囊炎', '颊囊肿胀', NULL, '氯己定冲洗', NULL, 'LafeberVet.pdf'),
  ('脱毛症', '毛发脱落', '蠕形螨', '伊维菌素', NULL, 'MSD.pdf');
```

**抽取流程**（ingest 时异步执行，不阻塞入库）：

```python
# services/rag/fact_extractor.py

FACT_EXTRACTION_PROMPT = """
你是一个仓鼠兽医知识抽取器。从以下文本中提取所有疾病-症状-病原体-药物-剂量关系。
没有的信息留 null。输出 JSON 数组，每个对象一个事实。

文本：
{chunk_text}

输出格式（只输出 JSON）：
[
  {{
    "disease": "疾病名或null",
    "symptom": "症状或null", 
    "pathogen": "病原体或null",
    "drug": "药物或null",
    "dosage": "剂量用法或null"
  }}
]
"""

class FactExtractor:
    def extract(self, chunks: list[Document]) -> list[dict]:
        """批量抽取，一次 LLM 调用处理多个 chunk。"""
        # 拼接 chunks → DeepSeek → 解析 JSON → 写入 SQLite
```

**查询时的使用方式**：

```python
# 在 HybridRetriever 之前加一步：精准事实查询

def retrieve_with_facts(prepared_query):
    # 1. 先查事实表
    facts = fact_repo.search(prepared_query.original)
    
    # 2. 常规 hybrid 检索
    chunks = hybrid_retriever.retrieve(prepared_query)
    
    # 3. 如果有命中的事实，把它们作为"已知事实"前缀注入 prompt
    if facts:
        facts_text = format_facts_as_context(facts)
        # "以下是从知识库中提取的已知事实：\n- 湿尾症常用四环素 10mg/kg...\n"
        prompt = build_rag_prompt_with_facts(query, chunks, facts_text)
    
    return chunks, facts
```

**收益**：
- "湿尾症用什么药" → SQL 直接命中，不走语义检索绕路
- 事实抽取在 ingest 时一次性完成，查询时零延迟
- SQLite 已有依赖，不新增基础设施
- 数据量不超过 100 条，一条 SQL 即可

**工期**：2 天（建表 + FactExtractor + ingest 集成 + prompt 集成 + 验证）。

### 4.4 Health Check 增强

**现状**：`GET /health` 只返回 `{"status": "ok"}`。

**增强**：让 health check 报告各后端状态：

```json
{
  "status": "ok",
  "backends": {
    "chroma": {"ok": true, "chunks": 739},
    "bm25": {"ok": true, "chunks": 739},
    "facts": {"ok": true, "rows": 87},
    "ollama": {"ok": true, "models": ["nomic-embed-text", "qwen2.5:0.5b"]},
    "deepseek": {"ok": true}
  }
}
```

**收益**：一眼看清各组件状态，排错不靠猜。

**工期**：0.5 天。

---

## 五、第 2 周：智能增强

### 5.1 用户偏好 + 宠物档案

**现状**：每次对话从零开始，AI 不知道用户的宠物情况。

**目标**：用户说一次"我有一只 1 岁的叙利亚仓鼠，之前得过湿尾症"，系统记住并注入后续所有回答。

**方案**：SQLite 存偏好，LLM 自动从对话中提取：

```sql
CREATE TABLE IF NOT EXISTS user_preferences (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pet_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    species TEXT,        -- 叙利亚仓鼠 / 一线仓鼠 / ...
    age_months INTEGER,
    sex TEXT,
    notes TEXT,          -- 病史 / 特殊注意事项
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**自动提取**（在每次对话完成后异步执行）：

```python
# services/agent/preference_extractor.py

PREF_EXTRACT_PROMPT = """
从以下对话中提取用户的宠物信息和偏好。输出 JSON：

{
  "preferences": {"key": "value", ...},
  "pets": [{"name": "...", "species": "...", "age_months": N, "sex": "...", "notes": "..."}]
}

已有的宠物档案（用于合并更新，不是覆盖）：
{existing_pets}

最近的对话：
{recent_conversation}
"""
```

**注入 prompt**（生成回答时自动拼接）：

```
你是一个仓鼠兽医知识助手。

关于用户：
- 宠物：豆豆（叙利亚仓鼠，1岁，雌性），小白（一线仓鼠，6个月，雄性）
- 豆豆病史：2个月前患湿尾症，用四环素治愈
- 用户偏好：倾向于了解预防措施，对药物副作用比较关心

...上下文 chunks...

用户问题：豆豆最近不怎么吃东西
```

**收益**：回答从泛泛而谈变成针对具体宠物。比如同一句"仓鼠不吃东西"，对 1 岁仓鼠和 6 个月仓鼠的建议可能不同。

**工期**：2 天。

### 5.2 Agent 路由：RAG 作为可调用工具

**现状**：用户每次提问 → 走 RAG 检索 → 生成回答。这是一个平直的单步管线。

**问题场景**：

```
用户："我的仓鼠不吃东西"
AI：（检索"仓鼠不吃东西"）→ 回答：可能原因有 ABC...

用户："那需要去医院吗"  
AI：（检索"需要去医院"）→ 这个 query 本身信号很弱...

理想行为：Agent 意识到这是追问 → 自动组合前文的"不吃东西"+"什么情况就医" → 重新检索 → 回答
```

**方案**：加一个薄薄的 Agent 路由层，不是完整 ReAct，只是决策"这次该怎么做"：

```python
# services/agent/router.py

class AgentRouter:
    """轻量路由器：决定当前请求走哪条路径。"""
    
    def route(self, query: str, history: list[ChatTurn]) -> AgentAction:
        """
        返回 AgentAction:
          - action="rag_search"   → 需要检索知识库
          - action="rag_followup" → 追问，用前文上下文重新组装检索 query
          - action="direct_reply" → 简单回复，不需要检索
          - action="multi_step"   → 需要多次检索（复杂问题拆解）
        """
```

**不引入 LangChain / LlamaIndex**。自己写 ~100 行路由逻辑，核心是：

```
if 是追问（"那""它""这个"等指代词 + history 非空）:
    → 组装上下文后走 rag_followup（query = 前文主题 + 当前追问）
elif 是简单闲聊（"你好""谢谢"）:
    → direct_reply，节省一次 RAG 检索
elif 是复杂问题（含"比较""区别""所有"等多维度词）:
    → multi_step，拆成 2-3 个子问题，各自检索后合并回答
else:
    → rag_search（正常单步 RAG）
```

**收益**：
- 追问场景不再丢失上下文
- 简单闲聊省掉不必要的检索
- 不增加 LLM 调用次数（路由本身是规则为主 + 少量 LLM 判断）

**工期**：2 天。

---

## 六、完整优化后的架构

```
用户问题 + history
    ↓
AgentRouter（规则 + 轻量 LLM 路由）
    ↓
    ├── direct_reply → 直接 LLM 回答（不检索）
    ├── rag_followup → 上下文重组 → 走 RAG
    ├── multi_step  → 拆分子问题 → 多次 RAG → 合并
    └── rag_search  → 正常 RAG
                        ↓
              QueryRewriter（指代消解 + 多 query + keywords）
                        ↓
              ┌─────────────────┬──────────────────┬────────────────┐
              │ 向量 (Chroma)    │ BM25 (rank-bm25)  │ 事实表 (SQLite) │
              │ Top-20          │ Top-20 + 自定义词典│ 精准匹配         │
              └────────┬────────┴────────┬─────────┴───────┬────────┘
                       ↓     RRF (k=60)  │                 │
                                ↓         │                 │
                          Reranker → Top-5                │
                                ↓                          │
                     Prompt 组装（偏好 + 宠物档案 + 事实 + chunks）
                                ↓
                     DeepSeek 生成（结构化 + [N] 引用）
                                ↓
                     AnswerValidator（引用校验）
```

## 七、任务总览

| 优先级 | 任务 | 工期 | 新增依赖 | 收益 |
|--------|------|------|---------|------|
| **P0** | Docker Compose | 1 天 | Docker | 一键部署 |
| **P0** | jieba 自定义词典 | 1 天 | 无 | BM25 分词精度 |
| **P0** | Health Check 增强 | 0.5 天 | 无 | 排错效率 |
| **P1** | 结构化事实表 | 2 天 | 无（SQLite 已有） | 精准事实查询 |
| **P1** | 用户偏好 + 宠物档案 | 2 天 | 无（SQLite 已有） | 个性化回答 |
| **P2** | Agent 路由 | 2 天 | 无 | 追问处理 + 多步检索 |

**总工期：约 8.5 天，零新基础设施依赖。**

---

## 八、明确不做

| 事项 | 原因 |
|------|------|
| Elasticsearch | 739 chunk，rank-bm25 内存检索 < 10ms，足够 |
| Neo4j 知识图谱 | 仓鼠疾病关系 < 100 条，事实表更直接 |
| Milvus | Chroma 在当前规模完全够用 |
| Kafka / 消息队列 | 单服务 QPS < 1，无异步解耦需求 |
| 微服务拆分 | 单进程够用，拆了只会增加延迟和排查难度 |
| LangChain / LlamaIndex Agent | 手写路由 100 行更轻、更可控 |
| 多模态 Embedding | 当前知识库全是文本，无图片 |

---

## 九、判断标准：什么时候该上重型基础设施

保留这个判断表，未来数据量变化时参考：

| 触发条件 | 该上的方案 |
|---------|-----------|
| 文档 > 500 个，chunk > 5 万 | 考虑 ES 替换 rank-bm25 |
| 事实表 > 1000 行，跨实体查询复杂 | 考虑 Neo4j |
| QPS > 50，Chroma 延迟 > 200ms | 考虑 Milvus |
| 需要异步任务（批量 ingest、定时 eval） | 考虑 Redis Queue |
| 多用户，需要持久化用户状态 | PG 替换 SQLite |

**当前状态：一个条件都没触发。保持现状。**

---

*文档版本：v2.0 | 创建日期：2026-06-12 | 修正：砍掉所有重型基础设施，聚焦轻量务实优化*
