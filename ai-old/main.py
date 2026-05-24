from fastapi import FastAPI, File, UploadFile, HTTPException, Header, Depends, Form, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Union
import base64
import requests
import os
import uuid
import time
from datetime import datetime
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from io import BytesIO
from PIL import Image
import pytesseract

app = FastAPI(
    title="宠物异常监测系统",
    description="基于萤石AI的宠物健康监测系统 - 统一分析接口",
    version="1.0",
    swagger_ui_parameters={"defaultModelsExpandDepth": -1, "displayOperationId": False, "showExtensions": False, "tryItOutEnabled": True}
)

MAX_REQUEST_SIZE = 50 * 1024 * 1024

class SizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in ["POST", "PUT"]:
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > MAX_REQUEST_SIZE:
                return JSONResponse(
                    content={"code": 413, "message": "请求实体过大，请上传小于50MB的文件", "data": None},
                    status_code=413
                )
        response = await call_next(request)
        return response

app.add_middleware(SizeLimitMiddleware)

security = HTTPBearer()

def compress_image(image_bytes: bytes, max_size_kb: int = 500) -> bytes:
    try:
        img = Image.open(BytesIO(image_bytes))
        
        if img.mode in ('RGBA', 'LA'):
            img = img.convert('RGB')
        
        quality = 95
        while True:
            buffer = BytesIO()
            img.save(buffer, format='JPEG', quality=quality)
            buffer_size = buffer.tell() / 1024
            
            if buffer_size <= max_size_kb or quality <= 10:
                break
            
            quality -= 5
        
        return buffer.getvalue()
    except Exception as e:
        return image_bytes

EZVIZ_APP_KEY = os.getenv("EZVIZ_APP_KEY", "ef6f78de7878472d924ed3e2347c66ec")
EZVIZ_APP_SECRET = os.getenv("EZVIZ_APP_SECRET", "13e02bd12ac38cd466e2b51556700356")
EZVIZ_ACCESS_TOKEN = os.getenv("EZVIZ_ACCESS_TOKEN", "at.35ku3ja7892fcnou64hea23rddx74d21-39ltkr69q7-08ucyjk-qenqe7dbs")

PET_DETECTION_API = "https://open.ys7.com/api/service/intelligence/algo/analysis/pet_detection"

PET_STATE_CACHE = {}

DAY_START_HOUR = 8
DAY_END_HOUR = 22

DAY_STATIONARY_THRESHOLD = 5 * 60 * 60
NIGHT_STATIONARY_THRESHOLD = 3 * 60 * 60

DAY_EATING_THRESHOLD = 5 * 60 * 60
NIGHT_EATING_THRESHOLD = 3 * 60 * 60

MOVEMENT_THRESHOLD = 0.01
MAX_HISTORY = 180

def is_daytime(timestamp: float = None) -> bool:
    if timestamp is None:
        timestamp = time.time()
    hour = datetime.fromtimestamp(timestamp).hour
    return DAY_START_HOUR <= hour < DAY_END_HOUR

def get_stationary_threshold(timestamp: float = None) -> int:
    return DAY_STATIONARY_THRESHOLD if is_daytime(timestamp) else NIGHT_STATIONARY_THRESHOLD

def get_eating_threshold(timestamp: float = None) -> int:
    return DAY_EATING_THRESHOLD if is_daytime(timestamp) else NIGHT_EATING_THRESHOLD

def success_response(data: dict = None, message: str = "success") -> JSONResponse:
    return JSONResponse(content={
        "code": 200,
        "message": message,
        "data": data if data else {}
    })

def error_response(code: int, message: str, request_id: str = None) -> JSONResponse:
    status_code = 400 if code >= 40000 and code < 50000 else 500
    return JSONResponse(content={
        "code": code,
        "message": message,
        "data": None,
        "request_id": request_id
    }, status_code=status_code)

def get_access_token() -> str:
    return EZVIZ_ACCESS_TOKEN

def extract_time_from_image(image_bytes: bytes) -> Optional[float]:
    try:
        img = Image.open(BytesIO(image_bytes))
        width, height = img.size
        
        bottom_region = img.crop((width * 0.7, height * 0.9, width, height))
        
        text = pytesseract.image_to_string(bottom_region, config='--psm 6')
        
        date_formats = [
            '%Y-%m-%d %H:%M:%S',
            '%Y/%m/%d %H:%M:%S',
            '%Y-%m-%d %H:%M',
            '%Y/%m/%d %H:%M'
        ]
        
        for date_format in date_formats:
            try:
                match = None
                import re
                date_pattern = r'\d{4}[-/]\d{2}[-/]\d{2}\s+\d{2}:\d{2}(:\d{2})?'
                matches = re.findall(date_pattern, text)
                if matches:
                    date_str = matches[0]
                else:
                    date_str = text.strip()
                
                dt = datetime.strptime(date_str, date_format)
                return dt.timestamp()
            except ValueError:
                continue
        
        return None
    except Exception as e:
        return None

def detect_pet(access_token: str, image_data: str, data_type: str = "url") -> dict:
    headers = {
        "accessToken": access_token,
        "Content-Type": "application/json"
    }
    
    if data_type == "url":
        data_info = [{"modal": "image", "type": "url", "data": image_data}]
    else:
        data_info = [{"modal": "image", "type": "base64", "data": image_data}]
    
    payload = {
        "requestId": str(uuid.uuid4()),
        "taskType": "pet_detection",
        "stream": False,
        "dataInfo": data_info,
        "dataParams": [{"modal": "image", "img_width": 960, "img_height": 540}]
    }
    
    try:
        response = requests.post(PET_DETECTION_API, headers=headers, json=payload, timeout=30)
        
        if response.status_code != 200:
            error_detail = f"HTTP状态码: {response.status_code}, 响应内容: {response.text[:200]}"
            raise HTTPException(status_code=400, detail=f"调用宠物检测API失败: {error_detail}")
        
        try:
            result = response.json()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"宠物检测API响应解析失败: {str(e)}, 响应内容: {response.text[:200]}")
        
        meta_code = result.get("meta", {}).get("code")
        meta_message = result.get("meta", {}).get("message", "未知错误")
        
        if meta_code != 200:
            error_detail = f"API错误码: {meta_code}, 错误信息: {meta_message}"
            if meta_code == 401 or "accessToken" in meta_message.lower():
                error_detail += " (可能是AccessToken过期或无效)"
            raise HTTPException(status_code=400, detail=f"宠物检测API错误: {error_detail}")
        
        return result
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"调用宠物检测API网络异常: {str(e)}")

def analyze_pet_behavior(pet_detection_result: dict) -> dict:
    data = pet_detection_result.get("data", {})
    images = data.get("images", [])
    
    analysis = {
        "has_pet": False,
        "pet_type": "仓鼠",
        "position": None,
        "is_moving": False,
        "food_status": "unknown",
        "anomaly": {"long_stationary": False, "no_eating": False},
        "confidence": 0.0
    }
    
    if not images:
        return analysis
    
    image_result = images[0]
    content_ann = image_result.get("contentAnn", {})
    bboxes = content_ann.get("bboxes", [])
    
    if bboxes:
        analysis["has_pet"] = True
        bbox = bboxes[0]
        analysis["confidence"] = bbox.get("weight", 0.0)
        
        points = bbox.get("points", [])
        if points and len(points) >= 2:
            x1, y1 = points[0].get("x"), points[0].get("y")
            x2, y2 = points[1].get("x"), points[1].get("y")
            analysis["position"] = {"x": x1, "y": y1, "width": x2 - x1, "height": y2 - y1}
    
    return analysis

def is_in_food_bowl(pet_position: dict, bowl_position: dict) -> bool:
    if not pet_position or not bowl_position:
        return False
    
    pet_center_x = pet_position["x"] + pet_position["width"] / 2
    pet_center_y = pet_position["y"] + pet_position["height"] / 2
    
    bowl_left = bowl_position.get("x", 0)
    bowl_top = bowl_position.get("y", 0)
    bowl_right = bowl_left + bowl_position.get("width", 0)
    bowl_bottom = bowl_top + bowl_position.get("height", 0)
    
    return bowl_left <= pet_center_x <= bowl_right and bowl_top <= pet_center_y <= bowl_bottom

def analyze_bowl_color(image_bytes: bytes, bowl_position: dict) -> float:
    try:
        img = Image.open(BytesIO(image_bytes))
        img = img.convert("RGB")
        width, height = img.size
        
        bowl_x = int(bowl_position.get("x", 0))
        bowl_y = int(bowl_position.get("y", 0))
        bowl_w = int(bowl_position.get("width", 0))
        bowl_h = int(bowl_position.get("height", 0))
        
        bowl_x = max(0, bowl_x)
        bowl_y = max(0, bowl_y)
        bowl_w = min(bowl_w, width - bowl_x)
        bowl_h = min(bowl_h, height - bowl_y)
        
        if bowl_w <= 0 or bowl_h <= 0:
            return 1.0
        
        pixels = img.load()
        blue_pixel_count = 0
        total_pixel_count = 0
        
        step = max(1, bowl_w // 50, bowl_h // 50)
        
        for y in range(bowl_y, bowl_y + bowl_h, step):
            for x in range(bowl_x, bowl_x + bowl_w, step):
                r, g, b = pixels[x, y]
                
                if b > r + 30 and b > g + 30 and b > 80:
                    blue_pixel_count += 1
                total_pixel_count += 1
        
        if total_pixel_count == 0:
            return 1.0
        
        return blue_pixel_count / total_pixel_count
    except Exception as e:
        return 1.0

def update_pet_state(camera_id: str, analysis: dict, image_timestamp: Optional[float] = None) -> dict:
    current_time = image_timestamp if image_timestamp else time.time()
    
    if camera_id not in PET_STATE_CACHE:
        PET_STATE_CACHE[camera_id] = {
            "last_position": None,
            "last_movement_time": current_time,
            "last_eating_time": current_time,
            "stationary_start_time": current_time,
            "no_eating_start_time": current_time,
            "food_bowl_position": None,
            "history": [],
            "total_analyses": 0,
            "consecutive_non_eating_frames": 0
        }
    
    state = PET_STATE_CACHE[camera_id]
    
    if analysis["has_pet"] and analysis["position"]:
        if state["last_position"]:
            prev_pos = state["last_position"]
            curr_pos = analysis["position"]
            
            prev_center = (prev_pos["x"] + prev_pos["width"]/2, prev_pos["y"] + prev_pos["height"]/2)
            curr_center = (curr_pos["x"] + curr_pos["width"]/2, curr_pos["y"] + curr_pos["height"]/2)
            
            distance = ((prev_center[0] - curr_center[0])**2 + (prev_center[1] - curr_center[1])**2)**0.5
            avg_size = ((prev_pos["width"] + prev_pos["height"]) + (curr_pos["width"] + curr_pos["height"])) / 4
            
            if avg_size > 0:
                movement_rate = distance / avg_size
                analysis["is_moving"] = movement_rate > MOVEMENT_THRESHOLD
                
                if analysis["is_moving"]:
                    state["last_movement_time"] = current_time
                    state["stationary_start_time"] = current_time
        
        state["last_position"] = analysis["position"]
        
        if state["food_bowl_position"]:
            if is_in_food_bowl(analysis["position"], state["food_bowl_position"]):
                state["last_eating_time"] = current_time
                state["no_eating_start_time"] = current_time
                state["consecutive_non_eating_frames"] = 0
                analysis["is_eating"] = True
            else:
                state["consecutive_non_eating_frames"] += 1
                analysis["is_eating"] = False
        else:
            analysis["is_eating"] = False
    
    stationary_threshold = get_stationary_threshold(current_time)
    stationary_duration = current_time - state["stationary_start_time"]
    analysis["anomaly"]["long_stationary"] = stationary_duration > stationary_threshold
    
    eating_threshold = get_eating_threshold(current_time)
    no_eating_duration = current_time - state["last_eating_time"]
    analysis["anomaly"]["no_eating"] = no_eating_duration > eating_threshold
    
    if "food_status" not in analysis:
        analysis["food_status"] = "unknown"
    
    analysis_record = {
        "timestamp": current_time,
        "has_pet": analysis["has_pet"],
        "position": analysis["position"],
        "is_moving": analysis.get("is_moving", False),
        "is_eating": analysis.get("is_eating", False),
        "food_status": analysis["food_status"],
        "confidence": analysis["confidence"]
    }
    
    state["history"].append(analysis_record)
    if len(state["history"]) > MAX_HISTORY:
        state["history"] = state["history"][-MAX_HISTORY:]
    
    state["total_analyses"] += 1
    state["last_activity_time"] = current_time
    
    return analysis

def calculate_activity_score(analysis: dict) -> int:
    score = 50
    
    if analysis.get("has_pet", False):
        score += 20
    
    if analysis.get("is_moving", False):
        score += 25
    else:
        score -= 15
    
    if analysis.get("food_status") == "present":
        score += 10
    
    if analysis.get("anomaly", {}).get("long_stationary", False):
        score -= 20
    
    return max(0, min(100, score))

def get_activity_status(score: int) -> str:
    if score >= 70:
        return "normal"
    elif score >= 40:
        return "low"
    else:
        return "critical"

def get_activity_description(score: int) -> str:
    if score >= 80:
        return "仓鼠活动频繁，较为活跃"
    elif score >= 60:
        return "仓鼠活动正常"
    elif score >= 40:
        return "仓鼠活动较少，建议关注"
    else:
        return "仓鼠活动异常，需要检查"

def get_analysis_result(analysis: dict, timestamp: float = None) -> str:
    if not analysis.get("has_pet", False):
        return "未检测到仓鼠"
    
    result = "仓鼠"
    
    if analysis.get("is_moving", False):
        result += "正在活动中"
    else:
        result += "处于静止状态"
    
    food_status = analysis.get("food_status", "unknown")
    if food_status == "食盆不空":
        result += "，食盆中有食物"
    elif food_status == "食盆为空":
        result += "，食盆为空"
    
    stationary_hours = 5 if is_daytime(timestamp) else 3
    eating_hours = 5 if is_daytime(timestamp) else 3
    
    if analysis.get("anomaly", {}).get("long_stationary", False):
        result += f"，已超过{stationary_hours}小时未移动"
    
    if analysis.get("anomaly", {}).get("no_eating", False):
        result += f"，已超过{eating_hours}小时未到食盆区域进食"
    
    return result

def analyze_movement_trend(history: list) -> dict:
    if not history:
        return {
            "total_records": 0,
            "movement_ratio": 0.0,
            "average_confidence": 0.0,
            "active_periods": 0,
            "stationary_periods": 0,
            "trend": "stable",
            "suggestion": "暂无足够数据进行趋势分析"
        }
    
    total_records = len(history)
    moving_count = sum(1 for record in history if record.get("is_moving", False))
    pet_detected_count = sum(1 for record in history if record.get("has_pet", False))
    
    movement_ratio = moving_count / total_records if total_records > 0 else 0.0
    avg_confidence = sum(record.get("confidence", 0) for record in history) / total_records if total_records > 0 else 0.0
    
    recent_moving = sum(1 for record in history[-3:] if record.get("is_moving", False)) if len(history) >= 3 else moving_count
    earlier_moving = sum(1 for record in history[:-3] if record.get("is_moving", False)) if len(history) > 3 else 0
    
    if earlier_moving > 0:
        if recent_moving / min(3, len(history)) > earlier_moving / (len(history) - 3):
            trend = "increasing"
        elif recent_moving / min(3, len(history)) < earlier_moving / (len(history) - 3) * 0.7:
            trend = "decreasing"
        else:
            trend = "stable"
    else:
        trend = "stable"
    
    trend_descriptions = {
        "increasing": "活动量呈上升趋势",
        "decreasing": "活动量呈下降趋势",
        "stable": "活动量保持稳定"
    }
    
    suggestions = []
    if movement_ratio > 0.7:
        suggestions.append("仓鼠活动频繁，状态良好")
    elif movement_ratio < 0.3:
        suggestions.append("仓鼠活动较少，建议关注健康状况")
    
    if avg_confidence < 0.5:
        suggestions.append("检测置信度较低，建议调整摄像头角度或光线")
    
    return {
        "total_records": total_records,
        "pet_detected_count": pet_detected_count,
        "movement_ratio": round(movement_ratio, 4),
        "average_confidence": round(avg_confidence, 4),
        "active_periods": moving_count,
        "stationary_periods": total_records - moving_count,
        "trend": trend,
        "trend_description": trend_descriptions.get(trend, "未知趋势"),
        "suggestion": "; ".join(suggestions) if suggestions else "仓鼠活动状态正常"
    }

@app.post("/api/hamster/analyze", summary="仓鼠健康分析", description="上传单张图片分析仓鼠健康状态，支持与历史图片对比分析活动情况")
async def analyze_hamster(
    file: UploadFile = File(..., description="上传单张图片文件进行仓鼠健康分析"),
    camera_id: str = Form("default_camera", description="摄像头标识，用于关联历史图片"),
    bowl_x: Optional[int] = Form(10, description="食盆位置X坐标"),
    bowl_y: Optional[int] = Form(320, description="食盆位置Y坐标"),
    bowl_width: Optional[int] = Form(150, description="食盆宽度"),
    bowl_height: Optional[int] = Form(150, description="食盆高度"),
    x_request_id: Optional[str] = Header(None, alias="X-Request-Id")
):
    request_id = x_request_id if x_request_id else str(uuid.uuid4())
    
    if not file.content_type.startswith("image/"):
        return error_response(40001, "文件必须是图片", request_id)

    try:
        original_image_bytes = await file.read()
        
        image_for_api = original_image_bytes
        if len(image_for_api) > 500 * 1024:
            image_for_api = compress_image(image_for_api, max_size_kb=500)
        
        image_base64 = base64.b64encode(image_for_api).decode("utf-8")
        
        image_timestamp = extract_time_from_image(original_image_bytes)
        
        if camera_id not in PET_STATE_CACHE:
            PET_STATE_CACHE[camera_id] = {
                "last_position": None,
                "last_movement_time": time.time(),
                "last_eating_time": time.time(),
                "stationary_start_time": time.time(),
                "no_eating_start_time": time.time(),
                "food_bowl_position": None,
                "history": [],
                "total_analyses": 0,
                "consecutive_non_eating_frames": 0
            }
        
        if all([bowl_x, bowl_y, bowl_width, bowl_height]):
            PET_STATE_CACHE[camera_id]["food_bowl_position"] = {
                "x": bowl_x,
                "y": bowl_y,
                "width": bowl_width,
                "height": bowl_height
            }
        
        state = PET_STATE_CACHE.get(camera_id)
        bowl_position = state.get("food_bowl_position")
        
        bowl_analysis = {
            "blue_ratio": None,
            "food_status": "unknown"
        }
        
        if bowl_position:
            blue_ratio = analyze_bowl_color(original_image_bytes, bowl_position)
            bowl_analysis["blue_ratio"] = round(blue_ratio, 4)
            
            if blue_ratio > 0.85:
                bowl_analysis["food_status"] = "食盆为空"
            else:
                bowl_analysis["food_status"] = "食盆不空"
        
        access_token = get_access_token()
        pet_result = detect_pet(access_token, image_base64, data_type="base64")
        analysis = analyze_pet_behavior(pet_result)
        
        analysis["blue_ratio"] = bowl_analysis["blue_ratio"]
        analysis["food_status"] = bowl_analysis["food_status"]
        
        history = state.get("history", []) if state else []
        
        movements = []
        if history and analysis["has_pet"] and analysis["position"]:
            curr_pos = analysis["position"]
            curr_center = (curr_pos["x"] + curr_pos["width"]/2, curr_pos["y"] + curr_pos["height"]/2)
            
            for i, record in enumerate(reversed(history)):
                if record["has_pet"] and record["position"]:
                    prev_pos = record["position"]
                    prev_center = (prev_pos["x"] + prev_pos["width"]/2, prev_pos["y"] + prev_pos["height"]/2)
                    
                    distance = ((prev_center[0] - curr_center[0])**2 + (prev_center[1] - curr_center[1])**2)**0.5
                    avg_size = ((prev_pos["width"] + prev_pos["height"]) + (curr_pos["width"] + curr_pos["height"])) / 4
                    
                    if avg_size > 0:
                        movement_rate = distance / avg_size
                        is_moving = movement_rate > MOVEMENT_THRESHOLD
                        
                        movements.append({
                            "from_image": f"history_{len(history)-i}",
                            "to_image": "current",
                            "movement_rate": round(movement_rate, 4),
                            "is_moving": is_moving,
                            "time_diff": time.time() - record["timestamp"]
                        })
            
            if movements:
                analysis["is_moving"] = any(m["is_moving"] for m in movements)
        
        analysis = update_pet_state(camera_id, analysis, image_timestamp)
        
        activity_score = calculate_activity_score(analysis)
        activity_status = get_activity_status(activity_score)
        description = get_activity_description(activity_score)
        analysis_result_text = get_analysis_result(analysis, image_timestamp)
        
        movement_trend = analyze_movement_trend(history)
        
        historical_summary = {
            "total_analyses": PET_STATE_CACHE.get(camera_id, {}).get("total_analyses", 1),
            "history_count": len(history),
            "first_analysis_time": history[0]["timestamp"] if history else time.time(),
            "last_activity_time": PET_STATE_CACHE.get(camera_id, {}).get("last_activity_time", time.time()),
            "movement_detection_enabled": len(history) > 0,
            "food_bowl_set": state.get("food_bowl_position") is not None,
            "movement_trend": movement_trend
        }
        
        movement_summary = None
        if movements:
            movement_summary = {
                "total_comparisons": len(movements),
                "moving_frames": sum(1 for m in movements if m["is_moving"]),
                "avg_movement_rate": sum(m["movement_rate"] for m in movements) / len(movements),
                "max_movement_rate": max(m["movement_rate"] for m in movements),
                "min_movement_rate": min(m["movement_rate"] for m in movements)
            }
        
        result = {
            "has_pet": analysis["has_pet"],
            "pet_type": analysis["pet_type"],
            "position": analysis["position"],
            "is_moving": analysis["is_moving"],
            "is_eating": analysis.get("is_eating", False),
            "food_status": analysis["food_status"],
            "blue_ratio": analysis.get("blue_ratio"),
            "anomaly": analysis["anomaly"],
            "confidence": round(analysis["confidence"], 4),
            "image_time": datetime.fromtimestamp(image_timestamp).isoformat() if image_timestamp else None,
            "movements": movements,
            "movement_summary": movement_summary,
            "activity_score": activity_score,
            "activity_status": activity_status,
            "description": description,
            "analysis_result": analysis_result_text,
            "camera_id": camera_id,
            "food_bowl_position": state.get("food_bowl_position"),
            "history": historical_summary,
            "summary": {
                "any_moving": any(m["is_moving"] for m in movements) if movements else False,
                "all_have_pet": analysis["has_pet"],
                "total_images": 1 + len(history),
                "successful_analyses": 1 + sum(1 for r in history if r["has_pet"])
            }
        }
        
        return success_response(result)
    except HTTPException as e:
        return error_response(40001, str(e.detail), request_id)
    except Exception as e:
        return error_response(50001, f"AI分析服务异常: {str(e)}", request_id)



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)