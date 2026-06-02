from fastapi.responses import JSONResponse


def success_response(data: dict | None = None, message: str = "success") -> JSONResponse:
    return JSONResponse(
        content={
            "code": 200,
            "message": message,
            "data": data if data else {},
        }
    )


def error_response(code: int, message: str, request_id: str | None = None) -> JSONResponse:
    status_code = 400 if 40000 <= code < 50000 else 500
    return JSONResponse(
        content={
            "code": code,
            "message": message,
            "data": None,
            "request_id": request_id,
        },
        status_code=status_code,
    )
