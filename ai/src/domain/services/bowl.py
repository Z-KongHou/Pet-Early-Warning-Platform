from io import BytesIO

from PIL import Image

from shared.config import settings


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
    except Exception:
        return 1.0


def analyze_bowl(image_bytes: bytes, bowl_position: dict | None) -> dict:
    if not bowl_position:
        return {"blue_ratio": None, "food_status": "unknown"}

    blue_ratio = analyze_bowl_color(image_bytes, bowl_position)
    food_status = "食盆为空" if blue_ratio > settings.bowl_empty_blue_ratio else "食盆不空"
    return {"blue_ratio": round(blue_ratio, 4), "food_status": food_status}
