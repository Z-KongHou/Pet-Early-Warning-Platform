import re
from datetime import datetime
from io import BytesIO

from PIL import Image

try:
    import pytesseract
except Exception:  # pragma: no cover - optional dependency in local env
    pytesseract = None


class TimestampExtractor:
    def extract(self, image_bytes: bytes) -> float | None:
        if pytesseract is None:
            return None

        try:
            image = Image.open(BytesIO(image_bytes))
            width, height = image.size
            bottom_region = image.crop((width * 0.7, height * 0.9, width, height))
            text = pytesseract.image_to_string(bottom_region, config="--psm 6")
            matched = re.search(r"\d{4}[-/]\d{2}[-/]\d{2}\s+\d{2}:\d{2}(:\d{2})?", text)
            date_str = matched.group(0) if matched else text.strip()

            for date_format in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M"):
                try:
                    return datetime.strptime(date_str, date_format).timestamp()
                except ValueError:
                    continue
        except Exception:
            return None

        return None
