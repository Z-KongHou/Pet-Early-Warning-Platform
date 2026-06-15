# Hybrid RAG 优化思路整理与 3 天落地计划

> 本文基于 [`hybrid-rag-optimization-review.md`](./hybrid-rag-optimization-review.md) 整理优化思路，并压缩为 **3 个工作日** 内可交付 Hybrid RAG MVP 的执行计划。  
> 完整分阶段方案见 [`hybrid-rag-implementation-plan.md`](./hybrid-rag-implementation-plan.md)。

---

## 一、优化思路总览

### 1.1 核心判断

当前 RAG 的主要问题不在生成模型（DeepSeek 已足够），而在 **检索侧**：单向量 Top-4、大块 embedding、query 被 history 污染、无关键词召回、无精排。  
Hybrid RAG 的目标是在 **不替换 Chroma / 不大改 API** 的前提下，用 **多路召回 + 融合 + 精排** 提升 Recall，再用 **结构化 prompt** 提升回答可信度。

### 1.2 评审文档对原方案的八大修正

| # | 问题 | 修正 |
|---|------|------|
| 1 | Embedding 未验证即当作前提 | 先跑 embedding / 翻译上限实验，再决定是否换模型 |
| 2 | LLM Rerank 作默认精排 | **Cross-encoder 优先**；LLM rerank 仅作降级 |
| 3 | 无成本模型 | 每条 query 估算 token 成本与 P50 延迟 |
| 4 | 无线上可观测性 | 阶段 1 起加结构化日志与 `/stats` 扩展 |
| 5 | 去掉 history 拼接后 follow-up 退化 | **阶段 1+2 合并上线**，加指代 fallback |
| 6 | BM25 中文分词未考虑 | 知识库含中文时用 jieba；纯英文用空格分词 |
| 7 | `RAG_MAX_DISTANCE` 无依据 | 用 golden set 跑 distance 分位数再定阈值 |
| 8 | Golden set 无分层 | 按 `term_match / synonym / reasoning / coreference` 标注 |

### 1.3 三个架构决策（优先级最高）

1. **Embedding 是地基**  
   若「人工英译 query + 当前 embedding」Recall@10 仍 < 60%，应先换模型（如 `bge-m3`）并重入库，再堆 Hybrid 架构。

2. **Cross-encoder > LLM Rerank**  
   精排是确定性打分任务：本地 cross-encoder（`bge-reranker-v2-m3`）成本 ≈ 0、延迟 ~100ms；LLM rerank 约 +1.5s、成本约 2.1×。

3. **没有指标就不谈优化**  
   离线 eval（Recall/MRR）+ 线上结构化日志（空召回率、各阶段耗时）必须同步建设。

---

## 二、优化思路按模块整理

### 2.1 检索层

| 思路 | 做法 | 预期收益 |
|------|------|----------|
| 多路召回 | 向量（多 query）+ BM25，RRF 融合 | 症状名/药名/英文术语 recall ↑ |
| 扩召回再精排 | 向量/BM25 各 Top-20 → RRF → rerank 至 Top-5 | 噪声↓，context 质量↑ |
| 小块分块 | chunk 512 / overlap 100（替代 1200/200） | 细粒度语义匹配↑ |
| 距离阈值数据化 | `analyze_distances.py` 取 P90~P95 定 `RAG_MAX_DISTANCE` | 减少误过滤 |
| Embedding 选型 | `eval_embedding.py` 对比中/译英/人工英译 | 避免在错误地基上建楼 |

### 2.2 Query 层

| 思路 | 做法 | 预期收益 |
|------|------|----------|
| 检索与生成分离 | 检索只用改写后的 query；history 仅进生成 prompt | 向量信号不被稀释 |
| DeepSeek 多 query 改写 | `primary_query` + `alternative_queries` + `keywords` | 跨语言 + 同义表达 |
| 指代消解 | Rewriter prompt 显式消解 it/它/刚才 | follow-up recall 不降级 |
| 三层 fallback | Rewriter 失败 → 指代词拼最近 1 轮 user → 旧 Translator 仅翻译 | 稳定性↑ |

**PreparedQuery 扩展字段**：

```python
english_query: str              # 主检索 query
alternative_queries: list[str]  # 扩展向量检索
keywords: list[str]             # BM25 检索
```

### 2.3 精排层

| 路径 | 适用 | 成本/query | 延迟 |
|------|------|------------|------|
| **Cross-encoder（默认）** | 机器可跑 bge-reranker | ~¥0 | ~0.1s |
| LLM Rerank（降级） | 低配机 / cross-encoder 不可用 | ~¥0.004 | ~1.5s |
| 无 rerank（Day 2 过渡） | RRF Top-5 直接生成 | ¥0 | 0 |

### 2.4 生成层

| 思路 | 做法 |
|------|------|
| 结构化回答 | 结论 / 原因 / 建议 / 何时就医 |
| 强制引用 | 事实后标注 `[1][2]` |
| 引用校验 | `answer_validator.py` 检测非法引用编号，写 warn 日志 |
| 不足即明说 | context 不够时禁止 extrapolate |

### 2.5 工程与运维

| 思路 | 做法 |
|------|------|
| Feature flag | `rag_hybrid_enabled`、`rag_query_rewrite_enabled`、`rag_rerank_enabled` 可独立关闭 |
| 结构化日志 | 各阶段 `duration_*_ms`、召回数、空召回标记 |
| Stats 双索引 | `/api/rag/stats` 展示 Chroma 与 BM25 条数，差异 >5% 告警 |
| Golden set 分层 eval | 按 difficulty 输出 Recall，定位退化类型 |
| 成本文档 | `ai/docs/cost-model.md` 记录实测 token 与延迟 |

### 2.6 目标架构（3 天结束时）

```
用户问题 + history
    ↓
QueryRewriter（DeepSeek：指代消解 + 多 query + keywords）
    ↓  （失败 → 指代 fallback → Translator fallback）
┌──────────────────────┬──────────────────────┐
│ 向量检索 × N queries │  BM25（keywords+query）│
│ 各 Top-20            │  Top-20              │
└──────────┬───────────┴──────────┬───────────┘
           ↓      RRF (k=60)       ↓
                    ↓
         CrossEncoderReranker → Top-5
                    ↓
         DeepSeek 生成（结构化 + [n] 引用）
                    ↓
         结构化日志 + 引用校验
```

### 2.7 3 天内明确不做

| 事项 | 原因 |
|------|------|
| Parent-Child 分块 | 需改 ingest + 重入库，留 P4 |
| LLM Rerank 作默认 | 成本高、慢；仅保留降级代码路径 |
| 换向量数据库 | 数据量小，Chroma 够用 |
| 完整 `/metrics` 大盘 | 3 天内只做日志 + stats 扩展 |

---

## 三、3 天落地计划

### 3.1 时间线与交付物

| 天 | 主题 | 结束时应达到的状态 |
|----|------|-------------------|
| **Day 1** | 地基 + Query 链路 | 有 baseline；chunk/阈值调优；DeepSeek Rewriter 上线；可观测日志 |
| **Day 2** | Hybrid 检索 | BM25 + RRF 上线；ingest 双索引同步；stats 双计数 |
| **Day 3** | 精排 + 收尾 | Cross-encoder rerank；prompt 引用；eval 报告与回滚验证 |

**MVP 定义（Day 3 EOD）**：`POST /api/rag/query/stream` 走完整 Hybrid 链路，feature flag 可回退单向量，baseline 报告可量化对比。

---

### Day 1：地基评测 + Query 改写（合并原阶段 0 精简版 + 阶段 1+2）

#### 上午（3~4h）：评测与 embedding 快检

| 序号 | 任务 | 产出 |
|------|------|------|
| 1.1 | 编写 `ai/data/eval/questions.jsonl`（≥15 条，含 4 类 difficulty + 2 条 coreference） | golden set |
| 1.2 | 实现 `ai/scripts/eval_rag.py`（Recall@10、MRR、按 difficulty 分组） | 可重复评测 |
| 1.3 | 实现 `ai/scripts/analyze_distances.py`，对 golden set 输出 distance P50/P90/P95 | 阈值依据 |
| 1.4 | **快检** `ai/scripts/eval_embedding.py`（5~10 条：中文 / qwen 译 / DeepSeek 译 / 人工英译） | 是否需换 embedding |

**决策点（Day 1 中午）**：

```
人工英译 Recall@10 ≥ 70%  → 继续 nomic-embed-text
人工英译 Recall@10 < 60%  → 下午优先换 bge-m3 + re-ingest，再推进 Rewriter
60~70%                    → 并行推进，Day 2 前再评估
```

**配置初调**（re-ingest 前写入 `.env`）：

```env
RAG_CHUNK_SIZE=512
RAG_CHUNK_OVERLAP=100
RAG_TOP_K=12
RAG_MAX_DISTANCE=<P95 from analyze_distances，典型 1.3~1.5>
```

#### 下午（4h）：Query 分离 + DeepSeek Rewriter + 日志

| 序号 | 任务 | 文件 |
|------|------|------|
| 1.5 | 新建 `QueryRewriter`（指代消解 + multi-query + keywords） | `services/rag/query_rewriter.py` |
| 1.6 | 扩展 `PreparedQuery`；重写 `_prepare_query`（三层 fallback） | `query_service.py`、`query_translator.py` |
| 1.7 | 检索侧停用 `build_retrieval_query` 拼 history | `query_service.py` |
| 1.8 | 结构化日志：rewrite/retrieve/generate 耗时 | `query_service.py` |
| 1.9 | 新增 env + `.env.example` | `config.py` |
| 1.10 | **re-ingest** + 跑 eval，写入 `docs/hybrid-rag-baseline.md` v0.1 | baseline 报告 |

```env
RAG_QUERY_REWRITE_ENABLED=true
RAG_QUERY_REWRITE_MAX_QUERIES=3
```

#### Day 1 验收

- [ ] eval 脚本一键可跑
- [ ] Rewriter 开启后，coreference 类 Recall 不低于 term_match 均值
- [ ] Rewriter 失败不 500，fallback 可用
- [ ] baseline 文档含：配置快照、distance 分位数、分 difficulty Recall

---

### Day 2：BM25 + RRF 混合检索（原阶段 3）

#### 全天（6~7h）

| 序号 | 任务 | 文件 |
|------|------|------|
| 2.1 | `poetry add rank-bm25`；纯英文库不加 jieba，含中文则 `poetry install -E cjk` | `pyproject.toml` |
| 2.2 | 实现 `Bm25IndexRepository`（replace_by_source、持久化、stats） | `repositories/bm25_index.py` |
| 2.3 | 实现 `HybridRetriever`（多 query 向量 + BM25 + RRF） | `services/rag/hybrid_retriever.py` |
| 2.4 | ingest 同步更新 BM25 | `ingest_service.py` |
| 2.5 | deps 注入；`rag_hybrid_enabled` feature flag | `api/deps.py`、`config.py` |
| 2.6 | `/api/rag/stats` 增加 `bm25_chunk_count` | `api/routes/rag.py`、`ingest_service.py` |
| 2.7 | 全量 re-ingest + eval 对比 Day 1 | baseline v0.2 |

```env
RAG_HYBRID_ENABLED=true
RAG_VECTOR_TOP_N=20
RAG_BM25_TOP_N=20
RAG_RRF_K=60
```

**Day 2 过渡策略**：rerank 尚未就绪时，`HybridRetriever` 直接返回 RRF Top-5~6 供生成，Day 3 再插入 rerank 层。

#### Day 2 验收

- [ ] BM25 与 Chroma chunk 数一致（或差异 < 5%）
- [ ] 总体 Recall@10 相对 Day 1 提升（目标 +10pp，视 baseline 而定）
- [ ] 至少 2 条 case 仅 BM25 命中（记录在 baseline）
- [ ] `RAG_HYBRID_ENABLED=false` 可回退单向量

---

### Day 3：Cross-encoder Rerank + 生成增强 + 收尾

#### 上午（3~4h）：精排

| 序号 | 任务 | 文件 |
|------|------|------|
| 3.1 | 拉取 Ollama 模型：`ollama pull bge-reranker-v2-m3`（或 base 降级） | 本地环境 |
| 3.2 | 实现 `CrossEncoderReranker` + `LlmReranker` 降级 | `services/rag/reranker.py` |
| 3.3 | `query_service`：retrieve → rerank → prompt | `query_service.py` |
| 3.4 | 日志增加 `chunks_after_rerank`、`duration_rerank_ms` | `query_service.py` |

```env
RAG_RERANK_ENABLED=true
RAG_RERANK_BACKEND=cross_encoder
RAG_RERANK_CROSS_ENCODER_MODEL=bge-reranker-v2-m3
RAG_RERANK_TOP_N=5
RAG_RERANK_CANDIDATE_N=20
```

**降级决策树（Day 3 上午）**：

```
cross-encoder 本地可跑？
  Yes → RAG_RERANK_BACKEND=cross_encoder
  No  → RAG_RERANK_BACKEND=llm（临时）或 RAG_RERANK_ENABLED=false（RRF Top-5）
```

#### 下午（3~4h）：生成 + 文档 + 全链路验证

| 序号 | 任务 | 文件 |
|------|------|------|
| 3.5 | prompt 结构化 + 强制 `[n]` 引用 | `prompt_builder.py` |
| 3.6 | 引用校验（日志 warn） | `services/rag/answer_validator.py` |
| 3.7 | 前端 chat 页 smoke test（流式 + sources） | 手工 |
| 3.8 | 全量 eval + 更新 `docs/hybrid-rag-baseline.md` v1.0 | baseline 终版 |
| 3.9 | 编写 `ai/docs/cost-model.md`（实测延迟填表） | 成本文档 |
| 3.10 | 回滚演练：依次关闭 hybrid / rerank / rewrite | 运维备忘 |

#### Day 3 验收

- [ ] 端到端 P50 延迟 < 6s（cross-encoder 路径目标 ~3.5~4.5s）
- [ ] Recall@10 ≥ 70% 或相对 Day 0 提升 ≥ 15pp
- [ ] MRR@10 明显提升
- [ ] 空召回率 < 10%
- [ ] 10 条人工抽检可用性 ≥ 3.5/5
- [ ] 所有 feature flag 回滚验证通过

---

## 四、3 天任务 Checklist（可打印）

### Day 1

- [ ] `questions.jsonl`（15+ 条，含 difficulty）
- [ ] `eval_rag.py` / `analyze_distances.py` / `eval_embedding.py`（快检）
- [ ] embedding 决策（换或不换）
- [ ] chunk + distance 配置 + re-ingest
- [ ] `query_rewriter.py` + `_prepare_query` fallback
- [ ] 结构化日志
- [ ] `hybrid-rag-baseline.md` v0.1

### Day 2

- [ ] `rank-bm25` + `bm25_index.py`
- [ ] `hybrid_retriever.py` + RRF
- [ ] ingest 双索引 + stats 双计数
- [ ] `RAG_HYBRID_ENABLED` flag
- [ ] eval + baseline v0.2

### Day 3

- [ ] cross-encoder rerank（或降级方案）
- [ ] prompt 引用 + `answer_validator.py`
- [ ] 全链路 smoke + 回滚演练
- [ ] baseline v1.0 + `cost-model.md`

---

## 五、风险与缓冲

| 风险 | 缓冲策略 | 消耗时间 |
|------|----------|----------|
| embedding 需更换 | Day 1 下午改拉模型 + re-ingest | 2~3h |
| Ollama reranker 不可用 | Day 3 用 RRF Top-5 或 LLM rerank 降级 | 1~2h |
| 知识库 `data/` 为空 | 先用现有文档样本入库再 eval | 1h |
| DeepSeek API 不稳定 | Rewriter 超时 fallback 到 Translator | 已设计 |
| 3 天不够 Parent-Child | 明确延期到第 2 周 P4 | — |

---

## 六、成功标准（3 天 MVP）

| 维度 | 标准 |
|------|------|
| 架构 | 向量 + BM25 + RRF + rerank 四段式可查、可 flag 关闭 |
| 指标 | baseline 报告含 Day0→Day3 Recall/MRR/空召回对比 |
| 体验 | 中文术语类、follow-up 类问题明显改善（人工 ≥5 条） |
| 工程 | ingest 后双索引一致；日志可定位各阶段耗时 |
| 成本 | 默认不走 LLM rerank；单 query DeepSeek 调用 ≤2 次（rewrite + generate） |

---

## 七、3 天后的迭代 backlog（第 2 周）

| 优先级 | 事项 | 工期 |
|--------|------|------|
| P4 | Parent-Child 分块 | 2~3 天 |
| P4 | `/api/rag/metrics` 滑动窗口指标 | 1 天 |
| P4 | 前端 `[n]` 点击跳转 source | 0.5 天 |
| P5 | Golden set 扩至 30+ 条 | 0.5 天 |
| P5 | 缓存同 question 的 rewrite 结果 | 0.5 天 |

---

## 八、相关文档

| 文档 | 用途 |
|------|------|
| [`hybrid-rag-optimization-review.md`](./hybrid-rag-optimization-review.md) | 架构评审与修订细节（本文思路来源） |
| [`hybrid-rag-implementation-plan.md`](./hybrid-rag-implementation-plan.md) | 完整 2 周分阶段方案 |
| [`hybrid-rag-baseline.md`](./hybrid-rag-baseline.md) | 评测基线与对比数据（实施过程中创建） |
| [`ai/README.md`](../ai/README.md) | AI 服务运行与 ingest 说明 |

---

*文档版本：v1.0 | 创建日期：2026-06-11 | 配套：optimization-review + implementation-plan*
