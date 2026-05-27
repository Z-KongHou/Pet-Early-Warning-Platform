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
import sqlite3
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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "upload")
DATABASE_PATH = "pet_analysis.db"
MAX_HISTORY_RECORDS = 3
MAX_BATCH_IMAGES = 20

DAY_START_HOUR = 8
DAY_END_HOUR = 22

DAY_STATIONARY_THRESHOLD = 3 * 60
NIGHT_STATIONARY_THRESHOLD = 3 * 60

DAY_EATING_THRESHOLD = 3 * 60
NIGHT_EATING_THRESHOLD = 3 * 60

MOVEMENT_THRESHOLD = 0.1

def init_database():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pet_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            camera_id TEXT NOT NULL,
            timestamp REAL NOT NULL,
            has_pet INTEGER NOT NULL,
            movement_state TEXT DEFAULT 'stationary',
            food_state TEXT DEFAULT 'unknown',
            position_x INTEGER,
            position_y INTEGER,
            position_width INTEGER,
            position_height INTEGER,
            confidence REAL,
            created_at REAL DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_camera_timestamp ON pet_analysis(camera_id, timestamp)
    ''')
    conn.commit()
    conn.close()

def get_db_connection():
    return sqlite3.connect(DATABASE_PATH)

def insert_analysis_record(camera_id, timestamp, analysis):
    conn = get_db_connection()
    cursor = conn.cursor()
    position = analysis.get("position") or {}
    
    movement_state = "moving" if analysis.get("is_moving", False) else "stationary"
    food_status = analysis.get("food_status", "unknown")
    if food_status == "食盆不空":
        food_state = "present"
    elif food_status == "食盆为空":
        food_state = "empty"
    else:
        food_state = "unknown"
    
    cursor.execute('''
        INSERT INTO pet_analysis (
            camera_id, timestamp, has_pet, movement_state, food_state,
            position_x, position_y, position_width, position_height, confidence
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        camera_id,
        timestamp,
        1 if analysis.get("has_pet", False) else 0,
        movement_state,
        food_state,
        position.get("x"),
        position.get("y"),
        position.get("width"),
        position.get("height"),
        analysis.get("confidence", 0)
    ))
    conn.commit()
    
    cursor.execute('''
        DELETE FROM pet_analysis 
        WHERE camera_id = ? 
        AND id NOT IN (
            SELECT id FROM pet_analysis WHERE camera_id = ? ORDER BY timestamp DESC LIMIT ?
        )
    ''', (camera_id, camera_id, MAX_HISTORY_RECORDS))
    conn.commit()
    conn.close()

def get_all_history(camera_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM pet_analysis 
        WHERE camera_id = ? 
        ORDER BY timestamp ASC
    ''', (camera_id,))
    rows = cursor.fetchall()
    conn.close()
    
    history = []
    for row in rows:
        history.append({
            "id": row[0],
            "camera_id": row[1],
            "timestamp": row[2],
            "has_pet": bool(row[3]),
            "movement_state": row[4],
            "is_moving": row[4] == "moving",
            "food_state": row[5],
            "position": {
                "x": row[6],
                "y": row[7],
                "width": row[8],
                "height": row[9]
            } if row[6] is not None else None,
            "confidence": row[10]
        })
    return history

def get_camera_state(camera_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM pet_analysis 
        WHERE camera_id = ? AND has_pet = 1
        ORDER BY timestamp DESC LIMIT 1
    ''', (camera_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "last_position": {
                "x": row[6],
                "y": row[7],
                "width": row[8],
                "height": row[9]
            } if row[6] is not None else None,
            "last_movement_state": row[4],
            "last_food_state": row[5],
            "total_analyses": get_total_analyses(camera_id)
        }
    return {
        "last_position": None,
        "last_movement_state": "stationary",
        "last_food_state": "unknown",
        "total_analyses": 0
    }

def get_total_analyses(camera_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM pet_analysis WHERE camera_id = ?', (camera_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count



init_database()

def ensure_upload_dir():
    os.makedirs(UPLOAD_DIR, exist_ok=True)

def save_debug_upload(camera_id: str, index: int, filename: str, image_bytes: bytes) -> str:
    """保存前端上传的原始图片到 upload/，便于调试抓帧与分析链路。"""
    ensure_upload_dir()
    safe_name = os.path.basename(filename or "capture.jpg")
    for ch in '<>:"/\\|?*':
        safe_name = safe_name.replace(ch, "_")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    out_name = f"{camera_id}_{ts}_{index}_{safe_name}"
    out_path = os.path.join(UPLOAD_DIR, out_name)
    with open(out_path, "wb") as f:
        f.write(image_bytes)
    return os.path.relpath(out_path, BASE_DIR).replace("\\", "/")

ensure_upload_dir()

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
    if pet_detection_result is None:
        return {
            "has_pet": False,
            "pet_type": "仓鼠",
            "position": None,
            "is_moving": False,
            "food_status": "unknown",
            "anomaly": {"long_stationary": False, "no_eating": False},
            "confidence": 0.0
        }
    
    data = pet_detection_result.get("data") or {}
    images = data.get("images") or []
    
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
    
    image_result = images[0] or {}
    content_ann = image_result.get("contentAnn") or {}
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
    if analysis is None:
        analysis = {
            "has_pet": False,
            "pet_type": "仓鼠",
            "position": None,
            "is_moving": False,
            "food_status": "unknown",
            "anomaly": {"long_stationary": False, "no_eating": False},
            "confidence": 0.0
        }
    
    if "anomaly" not in analysis:
        analysis["anomaly"] = {"long_stationary": False, "no_eating": False}
    
    current_time = image_timestamp if image_timestamp else time.time()
    
    if "food_status" not in analysis:
        analysis["food_status"] = "unknown"
    
    current_movement_state = "moving" if analysis.get("is_moving", False) else "stationary"
    current_food_state = "empty" if analysis.get("food_status") == "食盆为空" else "present"
    
    insert_analysis_record(camera_id, current_time, analysis)
    
    history = get_all_history(camera_id)
    
    stationary_duration = 0
    if len(history) >= 1:
        start_time = history[-1]["timestamp"]
        for record in reversed(history[:-1]):
            if record["movement_state"] == current_movement_state:
                start_time = record["timestamp"]
            else:
                break
        stationary_duration = current_time - start_time if current_movement_state == "stationary" else 0
    
    empty_food_duration = 0
    if len(history) >= 1:
        start_time = history[-1]["timestamp"]
        for record in reversed(history[:-1]):
            if record["food_state"] == current_food_state:
                start_time = record["timestamp"]
            else:
                break
        empty_food_duration = current_time - start_time if current_food_state == "empty" else 0
    
    stationary_threshold = get_stationary_threshold(current_time)
    analysis["anomaly"]["long_stationary"] = stationary_duration > stationary_threshold
    
    eating_threshold = get_eating_threshold(current_time)
    analysis["anomaly"]["no_eating"] = empty_food_duration > eating_threshold
    
    analysis["stationary_duration"] = stationary_duration
    analysis["empty_food_duration"] = empty_food_duration
    
    return analysis

def calculate_activity_score(analysis: dict) -> int:
    if analysis is None:
        return 50
    
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
    if analysis is None:
        return "未检测到仓鼠"
    
    if not analysis.get("has_pet", False):
        return "未检测到仓鼠"
    
    result = "仓鼠"
    
    if analysis.get("is_moving", False):
        result += "正在活动中"
    else:
        result += "处于静止状态"
        stationary_duration = analysis.get("stationary_duration", 0)
        if stationary_duration > 0:
            minutes = int(stationary_duration // 60)
            seconds = int(stationary_duration % 60)
            if minutes > 0:
                result += f"（已持续{minutes}分{seconds}秒）"
    
    food_status = analysis.get("food_status", "unknown")
    if food_status == "食盆不空":
        result += "，食盆中有食物"
    elif food_status == "食盆为空":
        result += "，食盆为空"
        empty_duration = analysis.get("empty_food_duration", 0)
        if empty_duration > 0:
            minutes = int(empty_duration // 60)
            seconds = int(empty_duration % 60)
            if minutes > 0:
                result += f"（已持续{minutes}分{seconds}秒）"
    
    stationary_minutes = 3
    eating_minutes = 3
    
    if analysis.get("anomaly", {}).get("long_stationary", False):
        result += f"，预警：已超过{stationary_minutes}分钟持续静止"
    
    if analysis.get("anomaly", {}).get("no_eating", False):
        result += f"，预警：已超过{eating_minutes}分钟食盆为空"
    
    return result

def analyze_movement_trend(history: list) -> dict:
    if not history:
        return {
            "trend": "stable",
            "trend_description": "暂无数据",
            "suggestion": "暂无足够数据进行趋势分析"
        }
    
    total_records = len(history)
    valid_records = [r for r in history if r is not None]
    moving_count = sum(1 for record in valid_records if record.get("is_moving", False))
    pet_detected_count = sum(1 for record in valid_records if record.get("has_pet", False))
    
    movement_ratio = moving_count / total_records if total_records > 0 else 0.0
    avg_confidence = sum(record.get("confidence", 0) for record in valid_records) / total_records if total_records > 0 else 0.0
    
    recent_moving = sum(1 for record in valid_records[-3:] if record.get("is_moving", False)) if len(valid_records) >= 3 else moving_count
    earlier_moving = sum(1 for record in valid_records[:-3] if record.get("is_moving", False)) if len(valid_records) > 3 else 0
    
    if earlier_moving > 0:
        if recent_moving / min(3, len(valid_records)) > earlier_moving / (len(valid_records) - 3):
            trend = "increasing"
        elif recent_moving / min(3, len(valid_records)) < earlier_moving / (len(valid_records) - 3) * 0.7:
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
        "trend": trend,
        "trend_description": trend_descriptions.get(trend, "未知趋势"),
        "suggestion": "; ".join(suggestions) if suggestions else "仓鼠活动状态正常"
    }

@app.post("/api/hamster/analyze", summary="仓鼠健康分析", description="上传图片分析仓鼠健康状态，支持单张或批量上传（最多20张）")
async def analyze_hamster(
    files: List[UploadFile] = File(..., description="上传图片文件进行仓鼠健康分析，支持批量上传，最多20张"),
    camera_id: str = Form("default_camera", description="摄像头标识，用于关联历史图片"),
    bowl_x: Optional[int] = Form(180, description="食盆位置X坐标"),
    bowl_y: Optional[int] = Form(720, description="食盆位置Y坐标"),
    bowl_width: Optional[int] = Form(180, description="食盆宽度"),
    bowl_height: Optional[int] = Form(180, description="食盆高度"),
    x_request_id: Optional[str] = Header(None, alias="X-Request-Id")
):
    request_id = x_request_id if x_request_id else str(uuid.uuid4())
    
    total_uploaded = len(files)
    if total_uploaded > MAX_BATCH_IMAGES:
        files = files[:MAX_BATCH_IMAGES]
        warning_message = f"上传了 {total_uploaded} 张图片，超过最大限制 {MAX_BATCH_IMAGES} 张，已截断处理前 {MAX_BATCH_IMAGES} 张"
    else:
        warning_message = None
    
    bowl_position = {"x": bowl_x, "y": bowl_y, "width": bowl_width, "height": bowl_height} if all([bowl_x, bowl_y, bowl_width, bowl_height]) else None
    
    results = []
    total_success = 0
    total_has_pet = 0
    anomaly_counts = {"long_stationary": 0, "no_eating": 0}
    
    for index, file in enumerate(files):
        try:
            if not file.content_type.startswith("image/"):
                results.append({
                    "index": index,
                    "filename": file.filename,
                    "success": False,
                    "error": "文件必须是图片"
                })
                continue
            
            original_image_bytes = await file.read()
            saved_path = save_debug_upload(camera_id, index, file.filename or "capture.jpg", original_image_bytes)
            
            image_for_api = original_image_bytes
            if len(image_for_api) > 500 * 1024:
                image_for_api = compress_image(image_for_api, max_size_kb=500)
            
            image_base64 = base64.b64encode(image_for_api).decode("utf-8")
            
            image_timestamp = extract_time_from_image(original_image_bytes)
            current_time = image_timestamp if image_timestamp else time.time()
            
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
            
            if bowl_position and analysis.get("position"):
                analysis["is_in_food_bowl"] = is_in_food_bowl(analysis["position"], bowl_position)
            else:
                analysis["is_in_food_bowl"] = False
            
            history = get_all_history(camera_id)
            
            analysis["is_moving"] = False
            
            if history and len(history) >= 1 and analysis.get("has_pet", False) and analysis.get("position"):
                latest_record = history[-1]
                if latest_record is not None and latest_record.get("has_pet", False) and latest_record.get("position"):
                    curr_pos = analysis["position"]
                    curr_center = (curr_pos["x"] + curr_pos["width"]/2, curr_pos["y"] + curr_pos["height"]/2)
                    
                    prev_pos = latest_record["position"]
                    prev_center = (prev_pos["x"] + prev_pos["width"]/2, prev_pos["y"] + prev_pos["height"]/2)
                    
                    distance = ((prev_center[0] - curr_center[0])**2 + (prev_center[1] - curr_center[1])**2)**0.5
                    avg_size = ((prev_pos["width"] + prev_pos["height"]) + (curr_pos["width"] + curr_pos["height"])) / 4
                    
                    if avg_size > 0:
                        movement_rate = distance / avg_size
                        is_moving = movement_rate > MOVEMENT_THRESHOLD
                        analysis["is_moving"] = is_moving
            
            analysis = update_pet_state(camera_id, analysis, image_timestamp)
            
            activity_score = calculate_activity_score(analysis)
            activity_status = get_activity_status(activity_score)
            analysis_result_text = get_analysis_result(analysis, image_timestamp)
            
            result = {
                "index": index,
                "filename": file.filename,
                "saved_path": saved_path,
                "success": True,
                "has_pet": analysis["has_pet"],
                "is_moving": analysis["is_moving"],
                "is_in_food_bowl": analysis.get("is_in_food_bowl", False),
                "food_status": analysis["food_status"],
                "anomaly": analysis["anomaly"],
                "confidence": round(analysis["confidence"], 4),
                "activity_score": activity_score,
                "activity_status": activity_status,
                "analysis_result": analysis_result_text,
                "image_timestamp": image_timestamp,
                "current_time": current_time
            }
            
            results.append(result)
            total_success += 1
            
            if analysis.get("has_pet", False):
                total_has_pet += 1
            
            if analysis.get("anomaly", {}).get("long_stationary", False):
                anomaly_counts["long_stationary"] += 1
            if analysis.get("anomaly", {}).get("no_eating", False):
                anomaly_counts["no_eating"] += 1
                
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            results.append({
                "index": index,
                "filename": file.filename,
                "success": False,
                "error": f"分析失败: {str(e)}"
            })
    
    summary = {
        "total_uploaded": total_uploaded,
        "processed_count": len(files),
        "success_count": total_success,
        "failed_count": len(files) - total_success,
        "has_pet_count": total_has_pet,
        "no_pet_count": total_success - total_has_pet,
        "anomaly_counts": anomaly_counts,
        "warning": warning_message
    }
    
    return success_response({
        "results": results,
        "summary": summary
    })



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)