# Hybrid RAG 优化三日实录：从单向量到多路召回+精排的完整落地

> 基于 [`hybrid-rag-3day-plan.md`](./hybrid-rag-3day-plan.md) 的三天执行过程全记录。  
> 目标：在 **不换 Chroma / 不大改 API** 的前提下，用多路召回 + RRF 融合 + 精排提升检索质量。

---

## 起点：Day 0 的 RAG 长什么样

优化前的管线非常简单：

```
用户问题 → 拼上最近几轮 history → Ollama 译英 → Chroma 向量检索 Top-4 → DeepSeek 生成
```

问题清单：
- **单向量 Top-4**，召回覆盖不足
- **history 污染检索 query**，follow-up 信号被稀释
- **无关键词召回**，症状名/药名等术语匹配差
- **无精排**，噪声直接进 prompt
- **chunk 1200 太大**，细粒度匹配差
- **无指标**，不知道到底多差

---

## Day 1（6月11日）：地基评测 + Query 链路

### 上午：评测体系搭建

第一步不是写代码，是建指标。写了三个脚本：

**`eval_rag.py`** — 核心评测脚本  
对 golden set（17 条，含 term_match / synonym / reasoning / coreference 四类 difficulty）逐条检索，计算 Recall@10 和 MRR@10，按 difficulty 分组输出。

**`analyze_distances.py`** — 距离阈值数据化  
对 golden set 的检索结果采样 distance 分布，算 P50/P90/P95/P99，用 P95 来定 `RAG_MAX_DISTANCE`，避免拍脑袋。

**`eval_embedding.py`** — Embedding 天花板快检  
对比四种 query 变体（中文原文 / qwen 译 / DeepSeek 译 / 人工英译）的 Recall，判断 nomic-embed-text 是否够用。结论：人工英译 Recall@10=100%，embedding 本身没问题，瓶颈在检索侧。

### 下午：Query 层重写

核心改动是 **检索与生成分离**。原来 `build_retrieval_query` 会把 history 拼进检索 query，导致向量信号被稀释。改成：

```
检索只用改写后的 english_query（不含 history）
History 仅用于：
  - QueryRewriter 做指代消解
  - 生成 prompt 中提供上下文
```

**`QueryRewriter`** — DeepSeek 驱动的查询改写器：

- 输入：用户原始问题 + 最近对话轮次
- 输出：`primary_query`（消解了指代的主检索 query）+ `alternative_queries`（扩展向量检索）+ `keywords`（BM25 检索用，Day 2 启用）

**三层 fallback**：

```
1. DeepSeek Rewriter（指代消解 + 多 query + keywords）
   ↓ 失败
2. 轻量指代 fallback（检测"它/这个/刚才"等标记，拼上最近一轮 user）
   ↓ 仍不可用
3. 旧 Translator（Ollama qwen2.5:0.5b 翻译 → 英文检索）
```

### Day 1 产出

| 项目 | 文件 |
|------|------|
| QueryRewriter | `services/rag/retrieval/query_rewriter.py` |
| 三层 fallback | `query_service.py` 中的 `_prepare_query()` |
| 结构化日志 | `query_service.py` 中的 `_log_structured()` |
| Eval 脚本 ×3 | `scripts/eval_rag.py`, `analyze_distances.py`, `eval_embedding.py` |
| Chunk 调优 | 512/100（原 1200/200） |

基线：**Recall@10 = 52.94%，MRR@10 = 0.35**（向量-only）。

---

## Day 2（6月12日上午）：BM25 + RRF 混合检索

### 为什么需要 BM25

向量检索擅长语义匹配，但对**精确术语**（药名、症状名、英文专有名词）不敏感。比如"湿尾症"和"proliferative ileitis"在向量空间可能离得不近，但 BM25 通过分词能精确命中。

### 实现

**`Bm25IndexRepository`** — 镜像 `VectorStoreRepository` 的接口：

- 分词：jieba（中文/CJK） + 空格分词（纯英文）
- 索引：`rank_bm25.BM25Okapi`
- 持久化：pickle 到 `chroma_db/bm25_corpus.pkl`
- 操作：`add_documents` / `delete_by_source` / `search` / `count` / `reset`

**`HybridRetriever`** — 多路召回 + RRF 融合：

```
PreparedQuery (english_query + alternative_queries + keywords)
    │
    ├── 向量检索 × N queries ──→ 各 Top-20
    │   （用 VectorStoreRepository.similarity_search_with_score 拿原始分数）
    │
    ├── BM25 检索 ──→ Top-20
    │   （keywords + english_query 拼成 BM25 查询串）
    │
    └── RRF 融合 (k=60) ──→ Top-K
         RRF_score(d) = Σ 1/(60 + rank_i(d))
         按 (source, chunk_index) 去重
```

### Ingest 双索引同步

`IngestService` 在写入 Chroma 后同步写入 BM25，replace 和 reset 操作也同步：

```python
# Replace sources in vector store
removed = self._replace_sources(chunks)
indexed = self._vector_store.add_documents(chunks)

# Sync BM25
bm25_removed = self._replace_bm25_sources(chunks)
bm25_indexed = self._bm25.add_documents(chunks)
```

验证结果：**Chroma 739 = BM25 739**，0% 差异。

### Stats 增强

`GET /api/rag/stats` 现在返回两个计数：

```json
{
  "collection": "yingshi_rag",
  "document_count": 739,
  "bm25_chunk_count": 739,
  "persist_dir": "E:\\yingshi\\ai\\chroma_db"
}
```

### Feature Flag

`RAG_HYBRID_ENABLED` — 设为 `false` 即回退到向量-only 路径。

### Day 2 产出

| 项目 | 文件 |
|------|------|
| BM25 索引 | `repositories/bm25_index.py` |
| 混合检索器 | `services/rag/retrieval/hybrid_retriever.py` |
| 双索引同步 | `services/rag/orchestration/ingest_service.py` |
| Stats 双计数 | `api/schemas/rag.py`, `api/routes/rag.py` |
| 依赖 | `rank-bm25` + `jieba` |

---

## Day 3（6月12日下午）：精排 + 生成增强

### 精排决策

3 天计划中 Cross-encoder 是首选（零成本、低延迟），但当前环境无 GPU、无 torch。按计划降级到 **LLM Rerank**。

**`LlmReranker`** — DeepSeek 点式相关性打分：

```
输入：原始用户问题 + 20 个候选 chunk
LLM 对每个 chunk 打 1-5 分（5=直接回答，1=不相关）
输出：Top-5，分数归一化到 [0, 1]
```

解析逻辑做了三层容错：直接 JSON 解析 → 正则提取 `[...]` → 正则提取单个数字。

### Prompt 增强

在原有"仅基于 context 回答"的基础上，增加了：

- **强制 `[N]` 引用**：每条事实必须标注来源编号
- **结构化输出**：结论 → 支持细节 → 实用建议 → 何时就医

### AnswerValidator

轻量后处理：扫描生成答案中的 `[N]` 引用，检测是否存在非法编号（如只有 5 个 source 却引用了 `[7]`），发现即写 warn 日志。

### 成本模型

| Phase | Token (in) | Token (out) | Cost | Latency |
|-------|-----------|-------------|------|---------|
| Rewrite | ~300 | ~80 | ~$0.0001 | ~1.2s |
| Vector | — | — | ¥0 | ~0.15s |
| BM25 | — | — | ¥0 | ~0.01s |
| Rerank | ~2000 | ~20 | ~$0.0005 | ~1.5s |
| Generate | ~2500 | ~300 | ~$0.0015 | ~2.5s |
| **Total** | **~4800** | **~400** | **~$0.0021** | **~5.4s** |

每 query 约 1.5 分人民币，3000 query/月 ≈ $6.30。

### Day 3 产出

| 项目 | 文件 |
|------|------|
| LLM Reranker | `services/rag/reranker.py` |
| 引用校验 | `services/rag/answer_validator.py` |
| Prompt 增强 | `services/rag/prompts/prompt_builder.py` |
| 成本模型 | `ai/docs/cost-model.md` |
| Baseline v1.0 | `docs/hybrid-rag-baseline.md` |

---

## 最终架构

```
用户问题 + history
    ↓
QueryRewriter（DeepSeek：指代消解 + 多 query + keywords）
    ↓  失败 → 指代 fallback → Translator fallback
┌──────────────────────┬──────────────────────┐
│ 向量检索 × N queries │  BM25（keywords+query）│
│ 各 Top-20            │  Top-20              │
└──────────┬───────────┴──────────┬───────────┘
           ↓      RRF (k=60)       ↓
                    ↓
         LlmReranker → Top-5
                    ↓
         DeepSeek 生成（结构化 + [N] 引用）
                    ↓
         AnswerValidator（引用校验 + warn 日志）
```

## 端到端验证

| 测试用例 | 类型 | 召回文档 | 跨文档 |
|---------|------|---------|--------|
| 仓鼠拉肚子怎么办 | term_match | main, MSD, Merck | ✓ |
| 仓鼠湿尾症怎么治疗 | term_match | main, Merck, LafeberVet | ✓ |
| 仓鼠不吃东西没精神 | synonym | main, LafeberVet, SickHamster | ✓ |
| 它严重吗（follow-up） | coreference | main, Merck, Pathology | ✓ |
| hamster hair loss causes | English | SickHamster, main | ✓ |

## 回滚能力

三个 feature flag 独立可控，任一组合均可安全降级：

| Flag | 关闭后行为 |
|------|-----------|
| `RAG_QUERY_REWRITE_ENABLED=false` | Rewriter 停用，fallback 到指代拼接或 Translator |
| `RAG_HYBRID_ENABLED=false` | 混合检索停用，回退向量-only `RagRetriever` |
| `RAG_RERANK_ENABLED=false` | 精排停用，RRF Top-5 直接进生成 |
| 全关 | Day 0 单向量基线 |

## 关键文件清单

```
ai/src/
├── config.py                          # 所有 feature flag 和超参
├── api/
│   ├── deps.py                        # 依赖注入（条件注入各组件）
│   ├── routes/rag.py                  # /ingest /query /query/stream /stats
│   └── schemas/rag.py                 # CollectionStatsResponse 含 bm25_chunk_count
├── repositories/
│   ├── vector_store.py                # Chroma 向量库
│   └── bm25_index.py                  # BM25 关键词索引（NEW）
├── services/rag/
│   ├── retrieval/
│   │   ├── retriever.py               # 向量检索器
│   │   ├── query_rewriter.py          # DeepSeek 查询改写（Day 1）
│   │   ├── query_translator.py        # Ollama 翻译器
│   │   └── hybrid_retriever.py        # 混合检索 + RRF（Day 2 NEW）
│   ├── reranker.py                    # LLM 精排（Day 3 NEW）
│   ├── answer_validator.py            # 引用校验（Day 3 NEW）
│   ├── prompts/prompt_builder.py      # Prompt 组装（结构化引用）
│   └── orchestration/
│       ├── ingest_service.py          # 入库编排（双索引同步）
│       └── query_service.py           # 查询编排（全管线）
├── scripts/
│   ├── eval_rag.py                    # 检索质量评测
│   ├── analyze_distances.py           # 距离分位数分析
│   └── eval_embedding.py              # Embedding 天花板快检
└── docs/
    └── cost-model.md                  # 成本/延迟模型（NEW）

docs/
├── hybrid-rag-3day-plan.md            # 原始 3 天计划
├── hybrid-rag-baseline.md             # 评测基线（v1.0）
└── hybrid-rag-3day-implementation-blog.md  # 本文
```

---

## 已知限制与后续 backlog

| 优先级 | 事项 | 说明 |
|--------|------|------|
| P4 | Cross-encoder 精排 | 需要 GPU 或 torch；当前 LLM rerank 可用但慢 |
| P4 | Parent-Child 分块 | 需改 ingest + 重入库 |
| P4 | `/api/rag/metrics` 滑动窗口 | 目前只有结构化日志 |
| P4 | 前端 `[N]` 点击跳转 source | 目前只是文本引用 |
| P5 | Golden set 扩至 30+ 条 | 当前 17 条 |
| P5 | 缓存同 question 的 rewrite 结果 | 减少重复 API 调用 |

---

*实现日期：2026-06-11 ~ 2026-06-12 | 基于 [hybrid-rag-3day-plan.md](./hybrid-rag-3day-plan.md)*
