def parse_pet_detection(pet_detection_result: dict) -> dict:
    data = pet_detection_result.get("data", {})
    images = data.get("images", [])

    analysis = {
        "has_pet": False,
        "pet_type": "仓鼠",
        "position": None,
        "is_moving": False,
        "food_status": "unknown",
        "anomaly": {"long_stationary": False, "no_eating": False},
        "confidence": 0.0,
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
