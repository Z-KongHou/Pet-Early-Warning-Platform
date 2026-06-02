import uuid

import requests
from fastapi import HTTPException

from shared.config import settings


class EzvizClient:
    def detect_pet_base64(self, image_base64: str, access_token: str | None = None) -> dict:
        token = access_token or settings.ezviz_access_token
        headers = {
            "accessToken": token,
            "Content-Type": "application/json",
        }
        payload = {
            "requestId": str(uuid.uuid4()),
            "taskType": "pet_detection",
            "stream": False,
            "dataInfo": [{"modal": "image", "type": "base64", "data": image_base64}],
            "dataParams": [{"modal": "image", "img_width": 960, "img_height": 540}],
        }

        try:
            response = requests.post(
                settings.pet_detection_api,
                headers=headers,
                json=payload,
                timeout=30,
            )

            if response.status_code != 200:
                error_detail = f"HTTP状态码: {response.status_code}, 响应内容: {response.text[:200]}"
                raise HTTPException(status_code=400, detail=f"调用宠物检测API失败: {error_detail}")

            try:
                result = response.json()
            except Exception as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"宠物检测API响应解析失败: {str(e)}, 响应内容: {response.text[:200]}",
                ) from e

            meta_code = result.get("meta", {}).get("code")
            meta_message = result.get("meta", {}).get("message", "未知错误")

            if meta_code != 200:
                error_detail = f"API错误码: {meta_code}, 错误信息: {meta_message}"
                if meta_code == 401 or "accessToken" in meta_message.lower():
                    error_detail += " (可能是AccessToken过期或无效)"
                raise HTTPException(status_code=400, detail=f"宠物检测API错误: {error_detail}")

            return result
        except requests.exceptions.RequestException as e:
            raise HTTPException(status_code=500, detail=f"调用宠物检测API网络异常: {str(e)}") from e
