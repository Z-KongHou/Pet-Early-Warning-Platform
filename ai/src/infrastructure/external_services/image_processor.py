from io import BytesIO

from PIL import Image


def compress_image(image_bytes: bytes, max_size_kb: int = 500) -> bytes:
    try:
        img = Image.open(BytesIO(image_bytes))

        if img.mode in ("RGBA", "LA"):
            img = img.convert("RGB")

        quality = 95
        while True:
            buffer = BytesIO()
            img.save(buffer, format="JPEG", quality=quality)
            buffer_size = buffer.tell() / 1024

            if buffer_size <= max_size_kb or quality <= 10:
                break

            quality -= 5

        return buffer.getvalue()
    except Exception:
        return image_bytes
