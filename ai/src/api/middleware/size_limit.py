from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from config import settings


class SizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in ("POST", "PUT"):
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > settings.max_request_size:
                return JSONResponse(
                    content={"code": 413, "message": "请求实体过大，请上传小于50MB的文件", "data": None},
                    status_code=413,
                )
        return await call_next(request)
