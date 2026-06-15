"""RAG 请求/响应 Schema。"""

from typing import Literal

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    data_dir: str | None = Field(
        default=None,
        description="待入库目录，默认使用配置 RAG_DATA_DIR",
    )
    reset_collection: bool = Field(
        default=False,
        description="为 true 时先清空整个 Chroma 集合再入库",
    )


class IngestResponse(BaseModel):
    data_dir: str
    files_loaded: int
    chunks_indexed: int
    vectors_removed: int
    sources: list[str]


class CollectionStatsResponse(BaseModel):
    collection: str
    document_count: int
    bm25_chunk_count: int = Field(default=0, description="BM25 索引中的片段数")
    facts_count: int = Field(default=0, description="结构化事实条目数")
    persist_dir: str


class ChatHistoryMessage(BaseModel):
    role: Literal["user", "assistant"] = Field(..., description="对话角色")
    content: str = Field(..., min_length=1, max_length=8000, description="消息正文")


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, description="用户问题")
    top_k: int | None = Field(default=None, ge=1, le=20, description="检索片段数量，默认 RAG_TOP_K")
    history: list[ChatHistoryMessage] = Field(
        default_factory=list,
        max_length=24,
        description="多轮对话历史（仅 user/assistant 正文，不含检索片段）；服务端按 RAG_CHAT_MAX_TURNS 截断",
    )


class SourceCitationSchema(BaseModel):
    source: str
    filename: str
    chunk_index: int | None
    excerpt: str
    score: float


class QueryResponse(BaseModel):
    question: str
    answer: str
    sources: list[SourceCitationSchema]
    llm_model: str
    detected_language: str = Field(default="en", description="检测到的用户提问语言（ISO 639-1）")
    english_question: str | None = Field(
        default=None,
        description="用于向量检索的英文问句；非英文提问时返回",
    )
