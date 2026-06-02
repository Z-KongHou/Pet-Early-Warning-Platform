from fastapi import APIRouter

from interfaces.api.schemas.common import success_response

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    return success_response({"status": "ok"})
