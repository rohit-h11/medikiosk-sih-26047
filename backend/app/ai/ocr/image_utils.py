"""
In-memory WebP image optimization and thumbnail utilities for MediKiosk.
"""

import io
from typing import Tuple, Union
from PIL import Image
import numpy as np


def ndarray_to_webp(img_rgb: np.ndarray, quality: int = 88) -> bytes:
    """
    Converts an RGB numpy array (cropped/rectified document) to high-res master WebP bytes.
    """
    pil_img = Image.fromarray(img_rgb)
    buffer = io.BytesIO()
    pil_img.save(buffer, format="WEBP", quality=quality, method=4)
    return buffer.getvalue()


def generate_thumbnail_webp(image_input: Union[bytes, np.ndarray], max_dim: int = 300, quality: int = 75) -> bytes:
    """
    Generates an ultra-fast in-memory WebP thumbnail (~30 KB) from raw image bytes or numpy array.
    Used for instant doctor timeline rendering with zero storage download penalty.
    """
    if isinstance(image_input, np.ndarray):
        img = Image.fromarray(image_input)
    else:
        img = Image.open(io.BytesIO(image_input))

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
