# Hybrid RAG 优化方案：架构评审与修订

> 原方案 `hybrid-rag-implementation-plan.md` 在工程 discipline（增量/回滚/feature flag/eval 驱动）上已经在水准之上。
> 本文档从**成本、延迟、可观测性、模型选型**四个架构维度补充优化，同时修正原方案中几处技术路径选择。
> **阅读本文前建议先通读原方案**，本文是对它的修订层，不重复原方案已覆盖的内容。

---

## 一、原方案核心问题与修正总览

| # | 问题 | 严重度 | 修正方向 |
|---|------|--------|----------|
| 1 | Embedding 模型选型未经验证就被当作既定前提 | **高** | 阶段 0 前增加 embedding 对比实验 |
| 2 | LLM Rerank 作为默认精排路径——成本高、延迟大、一致性差 | **高** | 改为 cross-encoder 优先，LLM rerank 降级为实验性备选 |
| 3 | 架构决策无成本模型 | **中** | 每个阶段附带成本/延迟预估 |
| 4 | 无生产可观测性设计 | **中** | 阶段 1 同步埋点 |
| 5 | 阶段 1 去掉 history 拼接后 follow-up 立即退化 | **中** | 阶段 1+2 合并上线，中间加最简 fallback |
| 6 | BM25 中文 tokenization 未被讨论 | **中** | 阶段 3 增加 jieba 分词条件判断 |
| 7 | RAG_MAX_DISTANCE 阈值无数据支撑 | **低** | 阶段 1 前先跑 distance distribution |
| 8 | Golden set 无难度分层 | **低** | 阶段 0 补充分层标注 |

---

## 二、新增前置工作（架构师必做）

### 2.1 Embedding 模型质量评估（P0，0.5 天）

**为什么必须做**：如果 `nomic-embed-text` 对 veterinary 英文 + 中文跨语言映射本身就不行，阶段 2~4 的架构改动可能只带来边际收益。换一个 embedding 模型的 ROI 可能超过阶段 3+4 的总投入。

**具体做法**：

```bash
# 在 ai/ 目录下新建评估脚本
ai/scripts/eval_embedding.py
```

脚本逻辑：

```python
# 1. 挑选 10 条中文 golden question，人工翻译为高质量英文
HUMAN_TRANSLATIONS = {
    "仓鼠拉肚子怎么办": "hamster diarrhea treatment and causes",
    "仓鼠不吃不喝没精神": "hamster not eating drinking lethargic causes",
    # ... 10 条
}

# 2. 对每条中文 question，分别用以下方式生成 embedding query：
#    (a) 原始中文 → embed 检索    （当前行为，baseline）
#    (b) qwen2.5:0.5b 翻译 → embed 检索  （当前 translator）
#    (c) DeepSeek 翻译 → embed 检索        （阶段 2 预期）
#    (d) 人工英文翻译 → embed 检索          （理论上限）
#
# 3. 对比 4 种方式 Recall@10 / MRR

# 4. 如果 (d) 的 Recall 也低（< 60%），说明问题不在翻译，在 embedding 模型本身
#    → 此时应该优先评估替代模型：
#    - bge-m3 (Ollama, 1024d, 多语言 MTEB top)
#    - multilingual-e5-large (Ollama)
#    - bge-large-en-v1.5 (Ollama, 仅英文但 veterinary 可能够用)
```

**验收输出**：

| 查询方式 | Recall@10 | MRR | 结论 |
|----------|-----------|-----|------|
| 中文原文 | 基线 | 基线 | — |
| qwen2.5:0.5b 翻译 | ? | ? | 当前 translator 是否有效 |
| DeepSeek 翻译 | ? | ? | 阶段 2 预期收益 |
| 人工英文翻译 | ? | ? | **embedding 模型理论上限** |

**决策矩阵**：

```
人工翻译 Recall@10 ≥ 70% → embedding 模型 OK，按原计划推进
人工翻译 Recall@10 < 60% → 先换 embedding 模型，再推进阶段 2+
人工翻译 60~70%       → 边推进边评估替代 embedding
```

**代码变更**（如换模型）：

```python
# config.py 增加
ollama_embed_model: str = os.getenv("OLLAMA_EMBED_MODEL", "bge-m3")  # 从 nomic-embed-text 切换

# 注意：换 embedding 模型后必须 re-ingest
```

---

### 2.2 成本模型（P0，0.5 天）

**每个架构决策必须附带成本估算。** 以下是基于 deepseek-v4-flash 定价的模型：

| 调用 | 输入 tokens | 输出 tokens | 单次成本(¥) | 千次/天成本(¥) | 万次/天成本(¥) |
|------|------------|-------------|-------------|----------------|----------------|
| Query Rewrite (DS flash) | ~300 | ~100 | ~0.0005 | 0.50 | 5.00 |
| LLM Rerank (DS flash) | ~3000 | ~200 | ~0.004 | 4.00 | 40.00 |
| Generation (DS flash) | ~2000 | ~500 | ~0.003 | 3.00 | 30.00 |
| **总计（LLM Rerank 路径）** | | | **~0.0075** | **7.50** | **75.00** |
| | | | | | |
| Cross-encoder Rerank (本地) | 0 | 0 | 0 | 0 | 0 |
| **总计（Cross-encoder 路径）** | | | **~0.0035** | **3.50** | **35.00** |

**延迟模型**（串行链路，P50 估算）：

```
LLM Rerank 路径：
  Rewrite (DS) → 1.0s → Vector + BM25 → 0.3s → Rerank (DS) → 1.5s → Generate (DS) → 2.0s = ~4.8s

Cross-encoder 路径：
  Rewrite (DS) → 1.0s → Vector + BM25 → 0.3s → Rerank (local) → 0.1s → Generate (DS) → 2.0s = ~3.4s
```

**关键发现**：LLM Rerank 路径每条 query 成本是 cross-encoder 路径的 **2.1 倍**，首 token 延迟多 **~1.4s**。按日活 1000 用户每人 5 问计算，月成本差异约 ¥5,250 vs ¥11,250。

> 如使用 deepseek-v4-pro 做 rerank，成本再 ×10，LLM Rerank 路径单条 query 成本 ~¥0.04。

**建议**：在 `ai/docs/` 下维护一个 `cost-model.md`，每个阶段上线后更新实际成本数据。

---

### 2.3 生产可观测性（P0，阶段 1 同步落地）

原方案只有离线 eval，缺少线上监控。以下为最小可观测性设计：

#### 2.3.1 结构化日志（阶段 1 即加）

在 `query_service.py` 中增强日志：

```python
# 当前日志（仅一行）
logger.info(
    "RAG query: chunks=%d lang=%s history=%d english_query=%r llm=%s",
    len(chunks), prepared.language, len(chat_history),
    prepared.english_query, llm.model,
)

# 优化为结构化 JSON 日志（方便接入 ELK / Grafana Loki）
logger.info(
    "RAG query completed",
    extra={
        "event": "rag_query",
        "chunks_retrieved": len(chunks),
        "chunks_after_rerank": len(reranked_chunks),
        "empty_retrieval": len(chunks) == 0,
        "language": prepared.language,
        "history_turns": len(chat_history),
        "rewrite_enabled": settings.rag_query_rewrite_enabled,
        "hybrid_enabled": settings.rag_hybrid_enabled,
        "rerank_enabled": settings.rag_rerank_enabled,
        "duration_rewrite_ms": rewrite_duration_ms,
        "duration_retrieval_ms": retrieval_duration_ms,
        "duration_rerank_ms": rerank_duration_ms,
        "duration_generation_ms": generation_duration_ms,
        "llm_model": llm.model,
    },
)
```

#### 2.3.2 指标暴露（阶段 2+）

在 `ai/src/api/routes/rag.py` 中增加一个内部 metrics endpoint：

```python
@router.get("/metrics", summary="RAG 运行指标")
async def rag_metrics(service: IngestService = Depends(get_ingest_service)):
    """非公开 endpoint，供监控系统拉取"""
    stats = service.collection_stats()
    return {
        **stats,
        "retrieval_empty_rate_1h": ...,    # 滑动窗口空召回率
        "p50_latency_ms": ...,
        "p99_latency_ms": ...,
    }
```

#### 2.3.3 关键告警阈值

| 指标 | 告警阈值 | 动作 |
|------|----------|------|
| 空召回率（5min 窗口） | > 10% | 检查 ingest 是否过期、collection 是否被清空 |
| P99 延迟 | > 8s | 检查 DeepSeek API 状态、Ollama 是否 OOM |
| BM25 与 Chroma 条数差 | > 5% | 重建 BM25 索引 |
| 连续 5 条回答含"资料不足" | — | 可能知识库覆盖不足 |

---

## 三、各阶段具体优化

### 阶段 0 优化：Golden Set 分层标注

原方案的 questions.jsonl 格式过于扁平。建议加分层标签：

```jsonl
{"question": "仓鼠湿尾症怎么治疗", "difficulty": "term_match", "lang": "zh", "expected_sources": ["wet_tail.md"], "expected_keywords": ["wet tail", "proliferative ileitis", "Lawsonia"], "is_multiturn": false}
{"question": "仓鼠拉肚子", "difficulty": "synonym", "lang": "zh", "expected_sources": ["diarrhea.md", "digestive.md"], "expected_keywords": ["diarrhea", "enteritis", "loose stool"], "is_multiturn": false}
{"question": "仓鼠突然不吃东西也不爱动可能是什么病", "difficulty": "reasoning", "lang": "zh", "expected_sources": ["lethargy.md", "appetite_loss.md", "common_diseases.md"], "expected_keywords": ["lethargy", "anorexia", "differential diagnosis"], "is_multiturn": false}
{"question": "它严重吗", "difficulty": "coreference", "lang": "zh", "expected_sources": ["wet_tail.md"], "expected_keywords": ["prognosis", "mortality", "severe"], "is_multiturn": true, "previous_turns": [{"role": "user", "content": "仓鼠湿尾症怎么治疗"}]}
```

`difficulty` 维度让 eval 脚本可以按类别输出 Recall，发现哪类问题在退化：

```python
# eval_rag.py 增强
def eval_by_category(questions, retriever):
    results = {"term_match": [], "synonym": [], "reasoning": [], "coreference": []}
    for q in questions:
        recall = compute_recall(retriever.retrieve(q))
        results[q["difficulty"]].append(recall)
    for cat, scores in results.items():
        print(f"{cat}: Recall@10 = {np.mean(scores):.2%} (n={len(scores)})")
```

---

### 阶段 1+2 合并优化：Query 分离 + DeepSeek Rewrite 同步上线

**核心问题**：阶段 1 去掉 history 拼接后，follow-up 类问题的检索会立即退化（"它怎么了" 没法检索）。阶段 2 的 QueryRewriter 用 DeepSeek 做指代消解能修复这个问题——但如果阶段 2 推迟或失败，中间窗口用户体验下降。

**优化方案：合并上线 + 最简 fallback**

```python
# services/rag/query_service.py 中的 _prepare_query 优化

def _prepare_query(self, question: str, history: list[ChatTurn]) -> PreparedQuery:
    text = question.strip()
    if not text:
        raise ValueError("Question must not be empty")

    # === 优化点 1：检索侧只用当前 question（不拼 history） ===
    retrieval_source = text

    # === 优化点 2：阶段 2 QueryRewriter 做指代消解 ===
    if settings.rag_query_rewrite_enabled and self._rewriter is not None:
        try:
            rewritten = self._rewriter.rewrite(text, history)
            return PreparedQuery(
                original=text,
                language=detect_language_code(text),
                english_query=rewritten.primary_query,  # 已消解指代的英文 query
                alternative_queries=rewritten.alternative_queries,  # 扩展 query
                keywords=rewritten.keywords,
            )
        except Exception as exc:
            logger.warning("Query rewrite failed, falling back: %s", exc)
            # fall through to fallback

    # === 优化点 3：rewrite 失败或未开启时的 fallback ===
    # 对于有明显指代词的短问题，拼入最近 1 轮 user message
    if _has_coreference(text) and history:
        last_user = _last_user_message(history)
        if last_user:
            retrieval_source = f"{last_user} {text}"

    # 保留原 Translator 作为最廉价 fallback（仅翻译，不做改写）
    if settings.rag_query_translation_enabled and self._translator is not None:
        prepared = self._translator.prepare(retrieval_source)
        return PreparedQuery(
            original=text,
            language=detect_language_code(text),
            english_query=prepared.english_query,
            alternative_queries=[],
            keywords=[],
        )

    return PreparedQuery(
        original=text,
        language=detect_language_code(text),
        english_query=retrieval_source,
        alternative_queries=[],
        keywords=[],
    )


# 简单的指代词检测（不依赖 LLM）
_COREFERENCE_PATTERNS = re.compile(
    r"\b(it|its|they|them|their|this|that|these|those|he|she|him|her)\b|"
    r"这[个些种]|那[个些种]|它|他|她|它们|他们|她们|刚才|前面|上面",
    re.IGNORECASE,
)

def _has_coreference(text: str) -> bool:
    """检测 question 是否包含指代词（不依赖 LLM 的快速判断）"""
    return bool(_COREFERENCE_PATTERNS.search(text))


def _last_user_message(history: list[ChatTurn]) -> str | None:
    """获取最近一条 user 消息"""
    for turn in reversed(history):
        if turn.role == "user":
            return turn.content.strip()
    return None
```

**PreparedQuery 扩展**：

```python
@dataclass(frozen=True)
class PreparedQuery:
    original: str
    language: str
    english_query: str                      # 主检索 query（已消解指代）
    alternative_queries: list[str] = field(default_factory=list)  # 扩展 query（阶段 2 产出）
    keywords: list[str] = field(default_factory=list)             # BM25 关键词（阶段 2 产出）
```

**QueryRewriter 的 prompt 优化**（相比原方案的翻译 prompt，增加指代消解能力）：

```python
REWRITE_SYSTEM = """You are a search query rewriter for a hamster veterinary knowledge base.

Given a user question AND prior conversation history, produce JSON with:
- "primary_query": a standalone English search query that resolves all pronouns and references.
  Example: if history says "my hamster has diarrhea" and current question is "how to treat it",
  primary_query should be "how to treat hamster diarrhea".
- "alternative_queries": 1-3 alternative English phrasings (synonyms, related angles).
  Example: ["hamster diarrhea treatment medication", "wet tail hamster treatment"].
- "keywords": 3-8 key medical/symptom terms in English.
  Example: ["hamster", "diarrhea", "wet tail", "treatment", "antibiotics"].

Rules:
- Resolve ALL pronouns (it/they/this/that) using conversation history.
- Use veterinary terminology where appropriate.
- Output ONLY valid JSON, no markdown, no explanation."""

REWRITE_USER_TEMPLATE = """Conversation history:
{history}

Current question: {question}

JSON:"""
```

#### 阶段 1+2 验收标准补充

- follow-up 类问题的 Recall@10 不低于单轮问题（原方案没这个对比）
- `_has_coreference` fallback 覆盖 ≥90% 的退化 case（人工抽 20 条 follow-up）
- Rewrite 延迟 P50 < 1.5s（日志记录）

---

### 阶段 1 补充：RAG_MAX_DISTANCE 数据驱动校准

在改 `RAG_MAX_DISTANCE` 前，先跑 distance distribution：

```python
# scripts/analyze_distances.py（一次性分析脚本）
import numpy as np
from repositories.vector_store import VectorStoreRepository
from clients.embedding_client import get_embeddings

store = VectorStoreRepository(embeddings=get_embeddings())

# 对 golden set 中每条 question 取 top-20 的 distance
questions = load_golden_questions()
all_distances = []
for q in questions:
    results = store.similarity_search_with_score(q["question"], k=20)
    distances = [score for _, score in results]
    all_distances.extend(distances)

# 输出分位数
for p in [50, 75, 90, 95, 99]:
    print(f"P{p}: {np.percentile(all_distances, p):.4f}")

# 建议：MAX_DISTANCE 设在 P90~P95 之间，既过滤噪声又不过度截断
# 对 nomic-embed-text + cosine distance，典型 P95 约 1.3~1.5
```

把这个分析脚本的输出贴在 `docs/hybrid-rag-baseline.md` 中，让阈值选择有据可查。

---

### 阶段 3 优化：BM25 中文 Tokenization

**关键判断**：你的知识库到底有没有中文内容？

```python
# services/rag/hybrid_retriever.py 中的 BM25 tokenizer

import re

# 检测文本是否含中文
_CJK_RE = re.compile(r"[一-鿿㐀-䶿]")

def _has_cjk(text: str) -> bool:
    return bool(_CJK_RE.search(text))

# 分词策略
def _tokenize(text: str) -> list[str]:
    """Tokenize for BM25 indexing/search, handling mixed CJK/Latin text."""
    if not _has_cjk(text):
        # 纯英文：rank-bm25 默认的空格分词就够用
        return text.lower().split()
    
    # 含中文：用 jieba 分词
    try:
        import jieba
        tokens = list(jieba.cut(text))
        return [t.strip().lower() for t in tokens if t.strip()]
    except ImportError:
        # jieba 未安装时的降级：按字符级 + 英文按空格
        logger.warning("jieba not installed, BM25 CJK tokenization degraded")
        tokens = []
        for part in re.split(r"(\s+)", text):
            if _has_cjk(part):
                tokens.extend(list(part))
            else:
                tokens.extend(part.lower().split())
        return [t for t in tokens if t.strip()]
```

**依赖管理**：

```toml
# pyproject.toml
[tool.poetry.dependencies]
rank-bm25 = "^0.2.2"
jieba = { version = "^0.42.1", optional = true }  # 仅知识库含中文时需要

[tool.poetry.extras]
cjk = ["jieba"]
```

**BM25 索引同步策略优化**（原方案的"同事务"不可行）：

```python
# repositories/bm25_index.py

class Bm25IndexRepository:
    """BM25 index with source-level consistency guarantees."""
    
    def __init__(self, index_dir: Path) -> None:
        self._index_dir = index_dir
        self._index_dir.mkdir(parents=True, exist_ok=True)
        self._index: BM25Okapi | None = None
        self._chunks: list[dict] = []  # [{chunk_id, text, metadata}]
    
    def replace_by_source(self, source: str, chunks: list[dict]) -> int:
        """Replace all chunks for a source. Best-effort consistent with Chroma."""
        # 1. 先从内存索引中移除旧条目
        removed = sum(1 for c in self._chunks if c["metadata"].get("source") == source)
        self._chunks = [c for c in self._chunks if c["metadata"].get("source") != source]
        
        # 2. 添加新条目
        self._chunks.extend(chunks)
        
        # 3. 重建索引
        self._rebuild_index()
        
        # 4. 持久化
        self._save()
        
        return removed
    
    def stats(self) -> dict:
        """返回 BM25 侧统计，供 /api/rag/stats 对比"""
        return {
            "bm25_chunk_count": len(self._chunks),
            "bm25_index_dir": str(self._index_dir),
        }
```

在 `/api/rag/stats` 中同时展示 Chroma 和 BM25 的条数：

```python
# api/routes/rag.py
@router.get("/stats")
async def collection_stats(
    ingest_service: IngestService = Depends(get_ingest_service),
):
    stats = ingest_service.collection_stats()
    # 阶段 3 后加入
    # bm25_stats = get_bm25_index().stats()
    # stats.update(bm25_stats)
    return success_response(CollectionStatsResponse(**stats).model_dump())
```

---

### 阶段 4 重大修正：Cross-encoder 优先，LLM Rerank 降级

**这是整个优化方案中最重要的修正。**

#### 推荐默认方案：Ollama Cross-encoder

```python
# services/rag/reranker.py

from __future__ import annotations

import logging
from dataclasses import dataclass

from config import settings
from services.rag.retriever import RetrievedChunk

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RankedChunk:
    chunk: RetrievedChunk
    relevance_score: float  # 0~1


class CrossEncoderReranker:
    """本地 cross-encoder 精排 —— 默认 rerank 路径。
    
    模型：bge-reranker-v2-m3（Ollama 或 sentence-transformers）
    延迟：~50-100ms / 20 个候选（本地推理）
    成本：0
    """

    def __init__(self, model_name: str | None = None) -> None:
        self._model = model_name or settings.rag_rerank_cross_encoder_model
        # 方案 A：Ollama（与现有栈一致，无新依赖）
        # 方案 B：sentence-transformers（更快的本地推理）
        self._backend = settings.rag_rerank_backend  # "ollama" | "sentence_transformers"
        self._client = None  # lazy init

    def rerank(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        top_n: int | None = None,
    ) -> list[RankedChunk]:
        if not chunks:
            return []

        top_n = top_n or settings.rag_rerank_top_n

        # 截断候选：全量输入（不做 200 字截断）
        pairs = [(query, chunk.content) for chunk in chunks]

        if self._backend == "ollama":
            scores = self._rerank_ollama(pairs)
        else:
            scores = self._rerank_sentence_transformers(pairs)

        # 排序
        ranked = sorted(
            zip(chunks, scores),
            key=lambda x: x[1],
            reverse=True,
        )
        return [
            RankedChunk(chunk=c, relevance_score=s)
            for c, s in ranked[:top_n]
        ]

    def _rerank_ollama(self, pairs: list[tuple[str, str]]) -> list[float]:
        """通过 Ollama API 调用 cross-encoder 模型"""
        import json
        import requests
        
        # bge-reranker-v2-m3 在 Ollama 中的调用方式
        # 注意：Ollama 对 reranker 的支持取决于具体模型格式
        # 如果 Ollama 不支持，fallback 到 sentence-transformers
        scores = []
        for query, doc in pairs:
            resp = requests.post(
                f"{settings.ollama_base_url}/api/embeddings",
                json={"model": self._model, "prompt": f"{query} [SEP] {doc}"},
                timeout=10,
            )
            # cross-encoder 通常返回 relevance score
            # 具体实现依赖 Ollama 模型格式
            scores.append(float(resp.json().get("similarity", 0.5)))
        return scores

    def _rerank_sentence_transformers(self, pairs: list[tuple[str, str]]) -> list[float]:
        """通过 sentence-transformers 本地推理"""
        from sentence_transformers import CrossEncoder
        if self._client is None:
            self._client = CrossEncoder(self._model)
        return self._client.predict(pairs).tolist()


class LlmReranker:
    """DeepSeek LLM Rerank —— 实验性备选路径。
    
    仅在以下场景使用：
    - cross-encoder 模型不可用（如低配机器无法加载）
    - 需要极细粒度的语义理解（cross-encoder 也无法处理的 case）
    
    成本：~0.004/query（deepseek-v4-flash）
    延迟：~1.5s
    """

    def __init__(self) -> None:
        from clients.llm import get_chat_llm
        self._llm = get_chat_llm()

    def rerank(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        top_n: int | None = None,
    ) -> list[RankedChunk]:
        if not chunks:
            return []

        top_n = top_n or settings.rag_rerank_top_n
        max_candidates = min(len(chunks), settings.rag_rerank_candidate_n)

        # 构建候选列表（全量文本，不做截断——LLM context 够用时）
        candidates_text = []
        for i, chunk in enumerate(chunks[:max_candidates]):
            candidates_text.append(f"[{i}] {chunk.content[:400]}")  # 最多 400 字/条目

        system = (
            "You are a relevance judge for a hamster veterinary knowledge base. "
            "Rank the following text chunks by their relevance to the user's question. "
            "Output ONLY valid JSON with key 'ranked_ids' containing chunk indices in "
            "descending order of relevance."
        )
        user = (
            f"Question: {query}\n\n"
            + "\n\n---\n\n".join(candidates_text)
            + f"\n\nOutput the top {top_n} most relevant chunk indices as JSON."
        )

        try:
            raw = self._llm.chat(system, user)
            parsed = _parse_json_object(raw)
            ranked_ids = parsed.get("ranked_ids", [])
            ranked = [chunks[i] for i in ranked_ids if 0 <= i < len(chunks)]
            # fallback：LLM 返回为空时用原顺序
            if not ranked:
                ranked = chunks[:top_n]
            return [RankedChunk(chunk=c, relevance_score=1.0 - i * 0.01) for i, c in enumerate(ranked[:top_n])]
        except Exception as exc:
            logger.warning("LLM rerank failed, falling back to RRF order: %s", exc)
            return [RankedChunk(chunk=c, relevance_score=1.0) for c in chunks[:top_n]]
```

**配置项**：

```env
# .env.example 增加
# --- Rerank 配置 ---
RAG_RERANK_ENABLED=true
RAG_RERANK_BACKEND=cross_encoder          # cross_encoder | llm
RAG_RERANK_CROSS_ENCODER_MODEL=bge-reranker-v2-m3
RAG_RERANK_TOP_N=5
RAG_RERANK_CANDIDATE_N=20
```

**决策树**：

```
机器能跑 bge-reranker-v2-m3？
  ├── Yes → RAG_RERANK_BACKEND=cross_encoder （推荐）
  └── No  → RAG_RERANK_BACKEND=llm （贵且慢，但是可用的）
```

> bge-reranker-v2-m3 模型大小约 1.1GB，与 nomic-embed-text（~274MB）不同量级，
> 但任何能跑 Ollama 的 GPU 机器（4GB+ VRAM）都能跑。
> 如果机器实在带不动，考虑 bge-reranker-base（~560MB）。

---

### 阶段 5 补充：LLM 引用校验

原方案只说"强制引用"，但 LLM 的 `[3]` 引用常常与实际 source 对不上。加一个后端校验：

```python
# services/rag/answer_validator.py（阶段 5 新建）

import re

_REFERENCE_RE = re.compile(r"\[(\d+)\]")

def validate_citations(answer: str, max_sources: int) -> dict:
    """校验回答中的引用编号是否在合法范围内。
    
    Returns:
        {"valid": [1, 2], "invalid": [7], "total_references": 3}
    """
    refs = [int(m) for m in _REFERENCE_RE.findall(answer)]
    valid = [r for r in refs if 1 <= r <= max_sources]
    invalid = [r for r in refs if r < 1 or r > max_sources]
    return {
        "valid": list(set(valid)),
        "invalid": list(set(invalid)),
        "total_references": len(refs),
    }
```

如果 `invalid` 非空，在日志中 warn。如果比例高（>20% 的回答有非法引用），说明 prompt 需要调整。

---

## 四、修订后的目录结构

```
ai/
  data/
    eval/
      questions.jsonl              # 增加 difficulty/lang/is_multiturn 字段
  scripts/
    eval_rag.py                    # 增加按 difficulty 分组输出
    eval_embedding.py              # 新增：embedding 模型对比脚本
    analyze_distances.py           # 新增：distance distribution 分析
  src/
    repositories/
      vector_store.py
      bm25_index.py                # 阶段 3
    services/rag/
      document_loader.py
      text_processor.py
      chunking.py
      ingest_service.py
      query_rewriter.py            # 阶段 2：含指代消解
      hybrid_retriever.py          # 阶段 3：BM25 含 jieba 分词
      reranker.py                  # 阶段 4：cross-encoder 默认 + LLM 备选
      answer_validator.py          # 阶段 5：引用校验
      retriever.py
      query_service.py
      prompt_builder.py
      ...
  docs/
    cost-model.md                  # 新增：成本模型（上线后持续更新）
docs/
  hybrid-rag-implementation-plan.md
  hybrid-rag-optimization-review.md  # 本文档
  hybrid-rag-baseline.md
```

---

## 五、修订后的排期与优先级

| 优先级 | 事项 | 工期 | 前置条件 |
|--------|------|------|----------|
| **P0** | Embedding 模型质量评估 | 0.5 天 | 无 |
| **P0** | 成本模型文档 | 0.5 天 | 无 |
| **P0** | 阶段 0（增强版：分层 golden set + distance 分析） | 1 天 | 无 |
| **P1** | 阶段 1+2 合并（调参 + query 分离 + DeepSeek rewrite + 可观测性埋点） | 2~3 天 | P0 完成 |
| **P2** | 阶段 3（BM25 + RRF + jieba 条件分词） | 2~3 天 | 阶段 1+2 稳定 |
| **P2** | 阶段 5（生成增强 + 引用校验） | 1 天 | 可与阶段 3 并行 |
| **P3** | 阶段 4（cross-encoder rerank） | 1~2 天 | 阶段 3 稳定 |
| **P3** | LLM rerank（仅作为实验性备选） | 0.5 天 | cross-encoder 稳定后 |
| **P4** | 阶段 6（Parent-Child chunking） | 2~3 天 | 前序全部稳定 |

**总工期**：约 **2 周**（P0~P3），与原始方案相当，但优先级的调整确保：
1. 地基（embedding 选型）先验证
2. 最高 ROI 的改动（DeepSeek rewrite）和最低成本的改动（调参）先做
3. 高成本的改动（LLM rerank）降到 P3 仅作为备选
4. 生产可观测性从第一天就到位

---

## 六、最重要的三个决策

从 200w 架构师的视角，这份优化方案的核心价值不在细节，而在三个决策：

1. **Embedding 模型选型是地基**——花半天做对比实验，可能省掉后面两周的架构改动。不要假设 `nomic-embed-text` 就是对的。

2. **Cross-encoder > LLM Rerank**——成本减半、延迟降 1.5s、一致性更好。LLM 不是万能的，在 scoring/ranking 这种确定性任务上，专用模型几乎总是更好的选择。

3. **没有线上指标，就不要谈优化**——离线 eval 测的是上限，线上指标看的是真实用户收益。每个阶段上线后，应该能在 dashboard 上看到曲线的变化。

---

*文档版本：v1.0 | 创建日期：2026-06-11 | 配套文档：`hybrid-rag-implementation-plan.md`*
