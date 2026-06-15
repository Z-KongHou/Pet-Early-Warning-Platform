# 仓鼠兽医 RAG 优化：从纯向量到混合检索的架构演进

> 目标：在 739 chunks、单机部署、零新基础设施的前提下，把仓鼠兽医领域 RAG 的检索精度从"还行"推到"精准"，并让系统具备追问理解、事实直查、个性化回答的能力。

---

## 一、为什么要优化

这个 RAG 系统服务于仓鼠兽医知识问答。数据量很小——12 个文档、739 个 chunk、术语不过 200 个。但小数据量并不等于简单：仓鼠兽医学有大量专有名词（"湿尾症""颊囊炎""增生性肠炎"），用户提问常常是追问链（"它严重吗""那要吃什么药"），而且很多问题是精准事实查询（"湿尾症用什么抗生素，剂量多少"），不是泛化的语义匹配能解决的。

初始系统是一个标准 RAG 骨架——Chroma 向量检索 + LLM 生成——能跑，但几个关键场景表现不稳定：中文术语被 embedding 模型模糊匹配到不相关的英文段落；追问丢失上下文；精准事实查询依赖语义检索绕了一圈却没命中。

优化目标很明确：**不引入任何重型基础设施**（没有 ES，没有 Neo4j，没有 Milvus，没有 LangChain Agent），在已有依赖范围内（SQLite、rank-bm25、jieba、Ollama、DeepSeek API）把检索精度推到极限。

---

## 二、最终架构

```
用户问题 + history
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  AgentRouter（规则路由，~100 行）                              │
│                                                             │
│  分析输入特征，决定四种路径之一：                                │
│  • direct_reply  — "你好""谢谢"，跳过检索，直接 LLM 回复       │
│  • rag_followup  — "它严重吗"→ 拼接前文主题 → 重新检索         │
│  • multi_step    — "比较湿尾症和颊囊炎"→ 拆子问题多次检索       │
│  • rag_search    — 标准单步 RAG                               │
└────────────────────────┬────────────────────────────────────┘
                         │  (非 direct_reply)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  QueryRewriter（DeepSeek）                                    │
│                                                             │
│  输入："它严重吗" + history[仓鼠湿尾症怎么治疗]                  │
│  输出：primary_query="hamster wet tail severity prognosis"    │
│        alt_queries=["is wet tail fatal in hamsters"]         │
│        keywords=["wet tail","proliferative ileitis","fatal"] │
│                                                             │
│  指代消解 + 多 query 扩展 + 关键词提取，一次 LLM 调用完成        │
└────────────────────────┬────────────────────────────────────┘
                         │
            ┌────────────┼────────────┐
            ▼            ▼            ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────────┐
│ Chroma       │ │ BM25         │ │ Facts (SQLite)   │
│ 向量语义检索  │ │ 关键词检索    │ │ 结构化事实直查    │
│ Top-20       │ │ Top-20       │ │                  │
│              │ │              │ │ 疾病/症状/病原体   │
│ nomic-embed  │ │ jieba 分词   │ │ /药物/剂量        │
│ -text        │ │ + 自定义词典  │ │ 精准 LIKE 匹配    │
└──────┬───────┘ └──────┬───────┘ └────────┬─────────┘
       │                │                  │
       └────────┬───────┘                  │
                ▼                          │
┌─────────────────────────────┐            │
│  RRF 融合 (k=60)             │            │
│  对两路结果做倒数排名融合     │            │
│  消除单一召回的排序偏差      │            │
└─────────────┬───────────────┘            │
              ▼                            │
┌─────────────────────────────┐            │
│  LLM Reranker (DeepSeek)    │            │
│  对融合后的候选集逐条打分     │            │
│  输出 Top-5                  │            │
└─────────────┬───────────────┘            │
              └──────────┬─────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Prompt 组装                                                  │
│                                                              │
│  按优先级拼接：                                                │
│  1. 用户偏好 + 宠物档案（"豆豆，叙利亚仓鼠，1岁，曾患湿尾症"）    │
│  2. 对话历史（最近 6 轮）                                      │
│  3. 已知事实（"湿尾症 → 四环素 10mg/kg PO q12h 5-7天"）        │
│  4. 检索上下文（5 个带 [N] 编号的 chunk）                       │
│  5. 用户问题                                                  │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  DeepSeek 生成                                                │
│                                                              │
│  结构化输出：                                                  │
│  1) 结论/摘要                                                 │
│  2) 支持性细节 [N] 引用                                        │
│  3) 实用建议                                                  │
│  4) 何时就医                                                  │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  AnswerValidator                                             │
│  校验所有 [N] 引用编号是否在合法范围内                            │
│  检测到幻觉引用 → 日志告警（不打断响应）                          │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  PreferenceExtractor（daemon thread，异步）                    │
│  从对话中提取宠物信息和个人偏好，写入 SQLite                      │
│  不阻塞用户响应                                                │
└─────────────────────────────────────────────────────────────┘
```

---

## 三、各环节的设计考量

### 3.1 AgentRouter：值不值得为路由加一次 LLM 调用？

最初考虑用 LLM 做路由判断——把用户问题扔给 DeepSeek，让它分类。实测后发现完全没必要：规则匹配的准确率已经足够高。

```
规则优先级：
1. 空输入 / 问候语 / 感谢 / 再见 → direct_reply（正则匹配，0ms）
2. 含"比较""区别""所有"等多维度标记且 >=2 个 → multi_step
3. 含"它""这个""严重吗"等指代标记 + 有历史 → rag_followup
4. 其他 → rag_search
```

约 50 个中文 + 英文的标记词覆盖了所有实测场景。规则匹配 0 延迟，不额外消耗 token。第 2 条的多标记阈值（>=2）避免了单标记误判。

### 3.2 QueryRewriter：指代消解为什么必须放在检索前面

一个典型的错误设计是将对话历史直接拼接到检索 query 中：

```
"仓鼠湿尾症怎么治疗？" → "湿尾症病因包括..."
"它严重吗？"           → 检索 query = "仓鼠湿尾症怎么治疗？它严重吗？"
                                                        ↑ 噪声
```

拼接法有两个问题：① 历史越长，检索 query 越稀释，BM25 的 TF-IDF 对长 query 不友好；② 英文 embedding 模型面对中英混杂的拼接文本，语义表示质量下降。

当前的 Rewriter 用一次 DeepSeek 调用完成三件事：
- **指代消解**："它" → "湿尾症"
- **翻译 + 检索优化**：生成适合英文向量库的检索 query
- **多路召回**：primary query + 2-3 个 alternative queries + 关键词列表

HybridRetriever 拿到这些后，对每个 query 分别做向量 + BM25 检索，再 RRF 融合。这比"历史拼接"多了一次 LLM 调用（约 200ms），但检索质量提升是决定性的。

### 3.3 jieba 自定义词典：10 分钟的工作，BM25 召回的天花板

BM25 的效果直接取决于分词质量。默认 jieba 分词：

```python
list(jieba.cut("仓鼠湿尾症怎么治疗"))
# → ['仓鼠', '湿', '尾症', '怎么', '治疗']   ← "湿尾症"被切碎了
```

"湿尾症"的 BM25 索引项是 `["湿", "尾症"]`，用户搜"湿尾症"时的 query token 也是 `["湿", "尾症"]`——匹配上了，但"湿"这个 token 在很多无关文档中出现，导致评分被稀释。

加上自定义词典后：

```python
jieba.load_userdict("data/hamster_dict.txt")
list(jieba.cut("仓鼠湿尾症怎么治疗"))
# → ['仓鼠', '湿尾症', '怎么', '治疗']   ← 术语完整
```

`hamster_dict.txt` 包含 37 个领域术语：湿尾症、颊囊炎、增生性肠炎、合笼、伪冬眠、Lawsonia intracellularis、Clostridioides difficile 等。每个词频设为 5，确保分词器优先识别。

### 3.4 RRF 融合：为什么不用加权求和

向量检索和 BM25 的分数分布完全不同——向量相似度集中在 0.7-1.0，BM25 分数跨度可达 0-50。直接加权求和会让 BM25 主导排序。

RRF（Reciprocal Rank Fusion）无视绝对分数，只关心**排名**：

```
RRF_score(d) = Σ 1/(k + rank_i(d))
```

k=60 是一个平缓的参数：当 k 较大时，排名第 1 和第 5 的权重差距较小，避免单个检索器的一票否决。对于这个规模（每路 20 个候选，总共最多 40 个），RRF 比加权求和更稳定。

### 3.5 LLM Reranker：为什么不用 Cross-Encoder

常见的 Reranker 选型是 `bge-reranker-v2-m3` 这类 Cross-Encoder 模型，本地跑、延迟低。但本项目选择用 DeepSeek API 做精排，原因是：

- **没有 GPU**。Cross-Encoder 在 CPU 上跑 20 个候选对的速度远慢于一次 DeepSeek API 调用
- **领域适配**。仓鼠兽医学有大量拉丁文学名和专有术语，通用 Cross-Encoder 不一定比 LLM 更懂这些词的语义相关性
- **部署简单**。不引入新的模型依赖，DeepSeek API 已经在用

LLM Reranker 的 prompt 设计是：给 20 个候选 chunk，让 LLM 对每个 chunk 打出 1-5 分的相关性评分，取 Top-5。一次调用完成全部打分。

代价是每次查询多了约 0.3 秒延迟和 ~$0.0003 的 API 费用。

### 3.6 Facts 表：什么时候绕过语义检索

语义检索的本质是"找意思相近的文本"，但有些查询不应该走这条路：

```
"湿尾症用什么抗生素" → 这不是语义匹配问题，是事实查找问题
```

正确的路径是：
1. 用 `LIKE '%湿尾症%' AND drug IS NOT NULL` 查 SQLite
2. 直接返回"四环素 10mg/kg PO q12h 5-7天"或"恩诺沙星 10mg/kg PO"
3. 把命中的事实作为 prompt 前缀注入，LLM 在此基础上组织语言

Facts 表在 ingest 时由 `FactExtractor` 用 DeepSeek 一次性抽取——740 个 chunk 分 93 个 batch，每个 batch 调一次 LLM，共抽取了 187 条结构化事实。查询时零额外延迟。

### 3.7 PreferenceExtractor：为什么用 daemon thread 而不是 BackgroundTasks

FastAPI 有 `BackgroundTasks` 机制，但它要求依赖注入——需要在路由函数里声明 `background_tasks: BackgroundTasks`，然后 `background_tasks.add_task(...)`。对于深埋在 `QueryService` 内部的后处理逻辑，这意味着一路把 `BackgroundTasks` 对象传递下来，侵入性太大。

当前的方案：`threading.Thread(target=_extract, daemon=True).start()`。一个 fire-and-forget 的守护线程。QPS < 1 意味着不会出现线程堆积；如果未来 QPS 增长，可以改成单一 `ThreadPoolExecutor` 线程池。daemon=True 保证进程退出时这些线程被自动清理。

---

## 四、检索精度

在 17 题 golden set（覆盖 term_match / synonym / reasoning / coreference 四个难度层级）上的对比：

| 难度 | Vector Only | Full Pipeline |
|------|------------|---------------|
| term_match（术语匹配） | 71.43% | **100.00%** |
| synonym（同义表达） | 33.33% | **100.00%** |
| reasoning（推理型） | 50.00% | **100.00%** |
| coreference（指代消解） | 33.33% | **100.00%** |
| **Recall@10** | **52.94%** | **100.00%** |
| **MRR@10** | **0.35** | **0.97** |

提升主要来自三个环节的叠加效应：QueryRewriter 让指代消解和同义词不再是盲区；BM25 补上了向量对专有名词的覆盖缺口；RRF + Reranker 让多个召回源的信号有效融合而非互相淹没。

---

## 五、部署

```bash
# 一键启动
docker compose up -d

# 初次使用拉取 Ollama 模型
docker exec <ollama-container> ollama pull nomic-embed-text

# 入库（首次或数据更新后）
curl -X POST http://localhost:8000/api/rag/ingest \
  -H "Content-Type: application/json" \
  -d '{"reset_collection": true}'

# 验证全链路
curl http://localhost:8000/health
curl -X POST http://localhost:8000/api/rag/query \
  -H "Content-Type: application/json" \
  -d '{"question":"湿尾症怎么治疗"}'
```

本地开发：

```bash
# AI 服务
cd ai && poetry install && cd src && uvicorn main:app --port 8000

# 前端
cd frontend && npm install && npm run dev
# .env.local: NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

---

## 六、设计约束

这个系统有意不引入以下组件，每个都有明确理由：

| 不用的组件 | 替代方案 | 触发升级的条件 |
|-----------|---------|--------------|
| Elasticsearch | rank-bm25 内存检索 | 文档 > 500 / chunk > 5 万 |
| Neo4j 知识图谱 | SQLite 事实表 + LIKE 查询 | 事实 > 1000 行 / 跨实体复杂查询 |
| Milvus | Chroma HNSW | QPS > 50 / 延迟 > 200ms |
| Kafka / 消息队列 | 同步处理 | 需要批量 ingest / 定时 eval |
| LangChain Agent | 手写 AgentRouter ~100 行 | 需要 ReAct 多步推理 |
| Cross-Encoder Reranker | DeepSeek LLM Reranker | 需要 GPU / 对延迟要求 < 100ms |

**当前状态：一个条件都没触发。**

---

*2026-06-14 · 基于 infrastructure-optimization-plan.md v2.0 实施*
