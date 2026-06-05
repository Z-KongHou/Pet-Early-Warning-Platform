from fastapi import FastAPI

from api.middleware.size_limit import SizeLimitMiddleware
from api.routes import hamster, health, rag

app = FastAPI(
    title="宠物异常监测系统",
    description="基于萤石AI的宠物健康监测系统 - 统一分析接口",
    version="1.0",
    swagger_ui_parameters={
        "defaultModelsExpandDepth": -1,
        "displayOperationId": False,
        "showExtensions": False,
        "tryItOutEnabled": True,
    },
)

app.add_middleware(SizeLimitMiddleware)
app.include_router(health.router)
app.include_router(hamster.router)
app.include_router(rag.router)
