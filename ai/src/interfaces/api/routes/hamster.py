import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile

from application.analyze_hamster import AnalyzeHamsterUseCase
from interfaces.api.dependencies.hamster import get_analyze_hamster_use_case_dep
from interfaces.api.schemas.common import error_response, success_response

router = APIRouter(prefix="/api/hamster", tags=["hamster"])


@router.post(
    "/analyze",
    summary="仓鼠健康分析",
    description="上传多张图片，在3分钟时间窗口内对比帧间位移，超过20张时随机抽样，返回统一分析结果",
)
async def analyze_hamster(
    files: list[UploadFile] = File(..., description="上传图片文件，支持批量"),
    camera_id: str = Form("default_camera", description="摄像头标识，用于关联历史图片"),
    bowl_x: Optional[int] = Form(180, description="食盆位置X坐标"),
    bowl_y: Optional[int] = Form(720, description="食盆位置Y坐标"),
    bowl_width: Optional[int] = Form(180, description="食盆宽度"),
    bowl_height: Optional[int] = Form(180, description="食盆高度"),
    x_request_id: Optional[str] = Header(None, alias="X-Request-Id"),
    use_case: AnalyzeHamsterUseCase = Depends(get_analyze_hamster_use_case_dep),
):
    request_id = x_request_id or str(uuid.uuid4())
    try:
        result = await use_case.execute(
            files=files,
            camera_id=camera_id,
            bowl_x=bowl_x,
            bowl_y=bowl_y,
            bowl_width=bowl_width,
            bowl_height=bowl_height,
            request_id=request_id,
        )
        return success_response(result)
    except ValueError as e:
        return error_response(40001, str(e), request_id)
    except HTTPException as e:
        return error_response(40001, str(e.detail), request_id)
    except Exception as e:
        return error_response(50001, f"AI分析服务异常: {str(e)}", request_id)
