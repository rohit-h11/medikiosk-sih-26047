"""
In-memory WebP image optimization and thumbnail utilities for MediKiosk.
"""

import io
from typing import Tuple
from PIL import Image


def generate_thumbnail_webp(image_bytes: bytes, max_dim: int = 300, quality: int = 75) -> bytes:
    """
    Generates an ultra-fast in-memory WebP thumbnail (~30 KB) from raw image bytes.
    Used for instant doctor timeline rendering with zero storage download penalty.
    """
    with Image.open(io.BytesIO(image_bytes)) as img:
        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")
        thumb_img = img.copy()
        thumb_img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        thumb_img.save(buffer, format="WEBP", quality=quality, method=3)
        return buffer.getvalue()


def create_optimized_image_variants(raw_bytes: bytes) -> Tuple[bytes, bytes]:
    """
    Transforms raw image bytes into two optimized WebP variants:
    1. Processed Master Image (max 2048px on longest edge, Q=88)
    2. UI Thumbnail (max 300px on longest edge, Q=75)
    """
    with Image.open(io.BytesIO(raw_bytes)) as img:
        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")

        # 1. Processed Master Image
        proc_img = img.copy()
        proc_img.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
        proc_buf = io.BytesIO()
        proc_img.save(proc_buf, format="WEBP", quality=88, method=4)
        processed_bytes = proc_buf.getvalue()

        # 2. UI Preview Thumbnail
        thumb_img = img.copy()
        thumb_img.thumbnail((300, 300), Image.Resampling.LANCZOS)
        thumb_buf = io.BytesIO()
        thumb_img.save(thumb_buf, format="WEBP", quality=75, method=3)
        thumbnail_bytes = thumb_buf.getvalue()

    return processed_bytes, thumbnail_bytes
