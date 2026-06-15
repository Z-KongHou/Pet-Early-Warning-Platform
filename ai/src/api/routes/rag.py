"""RAG 路由：知识库入库与集合状态。"""

import uuid

from fastapi import APIRouter, Depends, Header
from fastapi.responses import StreamingResponse

from api.deps import get_ingest_service, get_query_service
from api.schemas.rag import (
    CollectionStatsResponse,
    IngestRequest,
    IngestResponse,
    QueryRequest,
    QueryResponse,
    SourceCitationSchema,
)
from services.rag.utils.history import ChatTurn
from services.rag.orchestration.ingest import IngestService
from services.rag.orchestration.query import QueryService
from utils.response import error_response, success_response
from utils.sse import format_sse

router = APIRouter(prefix="/api/rag", tags=["rag"])


def _to_chat_turns(body: QueryRequest) -> list[ChatTurn]:
    return [ChatTurn(role=msg.role, content=msg.content) for msg in body.history]


@router.post(
    "/ingest",
    summary="文档向量化入库",
    description="加载 data 目录文档，清洗、分块后经 Ollama embedding 写入 Chroma",
)
async def ingest_documents(
    body: IngestRequest | None = None,
    x_request_id: str | None = Header(None, alias="X-Request-Id"),
    service: IngestService = Depends(get_ingest_service),
):
    request_id = x_request_id or str(uuid.uuid4())
    payload = body or IngestRequest()
    try:
        result = service.ingest_directory(
            payload.data_dir,
            reset_collection=payload.reset_collection,
        )
        return success_response(
            IngestResponse(
                data_dir=result.data_dir,
                files_loaded=result.files_loaded,
                chunks_indexed=result.chunks_indexed,
                vectors_removed=result.vectors_removed,
                sources=result.sources,
            ).model_dump()
        )
    except NotADirectoryError as exc:
        return error_response(40001, str(exc), request_id)
    except Exception as exc:
        return error_response(50001, f"知识库入库失败: {exc}", request_id)


@router.post(
    "/query",
    summary="RAG 知识问答",
    description="支持多轮 history（最近 6 轮 / 2000 tokens）；非英文译英检索，每轮重检索，回答按提问语言生成",
)
async def rag_query(
    body: QueryRequest,
    x_request_id: str | None = Header(None, alias="X-Request-Id"),
    service: QueryService = Depends(get_query_service),
):
    request_id = x_request_id or str(uuid.uuid4())
    try:
        result = service.ask(body.question, top_k=body.top_k, history=_to_chat_turns(body))
        return success_response(
            QueryResponse(
                question=result.question,
                answer=result.answer,
                llm_model=result.llm_model,
                detected_language=result.detected_language,
                english_question=result.english_question,
                sources=[
                    SourceCitationSchema(
                        source=s.source,
                        filename=s.filename,
                        chunk_index=s.chunk_index,
                        excerpt=s.excerpt,
                        score=s.score,
                    )
                    for s in result.sources
                ],
            ).model_dump()
        )
    except ValueError as exc:
        return error_response(40001, str(exc), request_id)
    except Exception as exc:
        return error_response(50001, f"知识问答失败: {exc}", request_id)


@router.post(
    "/query/stream",
    summary="RAG 知识问答（SSE 流式）",
    description="多轮 history 同 /query；先推送 meta，再按提问语言流式 delta",
    response_class=StreamingResponse,
)
async def rag_query_stream(
    body: QueryRequest,
    service: QueryService = Depends(get_query_service),
):
    def event_stream():
        try:
            for event, data in service.ask_stream(
                body.question, top_k=body.top_k, history=_to_chat_turns(body)
            ):
                yield format_sse(event, data)
        except ValueError as exc:
            yield format_sse("error", {"message": str(exc), "code": 40001})
        except Exception as exc:
            yield format_sse("error", {"message": f"知识问答失败: {exc}", "code": 50001})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/stats",
    summary="向量库统计",
    description="返回 Chroma 集合名称与当前向量条数",
)
async def collection_stats(
    service: IngestService = Depends(get_ingest_service),
):
    stats = service.collection_stats()
    return success_response(CollectionStatsResponse(**stats).model_dump())
