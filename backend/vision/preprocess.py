"""
Image preprocessing pipeline for BillSplit AI.
Runs BEFORE sending to Gemini to improve extraction accuracy on hard cases:
  - EXIF auto-orient
  - Deskew (OpenCV minAreaRect)
  - CLAHE adaptive contrast (faded thermal prints)
  - Downscale if > 4000px on long edge
"""
from __future__ import annotations

import io
import math
from typing import Any

import cv2
import numpy as np
from PIL import Image, ExifTags


def _auto_orient(img: Image.Image) -> Image.Image:
    """Rotate image according to EXIF orientation tag."""
    try:
        exif: Any = img._getexif()  # type: ignore[attr-defined]
        if exif is None:
            return img
        orient_key = next(k for k, v in ExifTags.TAGS.items() if v == "Orientation")
        orientation = exif.get(orient_key)
        rotation_map = {3: 180, 6: 270, 8: 90}
        if orientation in rotation_map:
            img = img.rotate(rotation_map[orientation], expand=True)
    except Exception:
        pass
    return img


def _pil_to_cv(img: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2BGR)


def _cv_to_pil(arr: np.ndarray) -> Image.Image:
    return Image.fromarray(cv2.cvtColor(arr, cv2.COLOR_BGR2RGB))


def _deskew(img: Image.Image) -> Image.Image:
    """
    Detect the dominant rotation angle using Hough lines on a Canny edge map,
    then rotate to correct steep-angle / tilted phone shots.
    Falls back gracefully if no strong lines are found.
    """
    arr = _pil_to_cv(img)
    gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)

    # Canny edges
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(edges, 1, math.pi / 180, threshold=100,
                             minLineLength=img.width // 4, maxLineGap=20)
    if lines is None:
        return img

    angles = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        if x2 != x1:
            angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
            # Only consider near-horizontal lines (text lines)
            if -45 < angle < 45:
                angles.append(angle)

    if not angles:
        return img

    median_angle = float(np.median(angles))
    if abs(median_angle) < 0.5:   # Already straight enough
        return img

    # Rotate to correct
    (h, w) = arr.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, median_angle, 1.0)
    rotated = cv2.warpAffine(arr, M, (w, h),
                              flags=cv2.INTER_CUBIC,
                              borderMode=cv2.BORDER_REPLICATE)
    return _cv_to_pil(rotated)


def _apply_clahe(img: Image.Image) -> Image.Image:
    """
    Apply CLAHE (Contrast Limited Adaptive Histogram Equalisation) to the
    luminance channel — boosts readability of faded thermal prints.
    """
    arr = _pil_to_cv(img)
    lab = cv2.cvtColor(arr, cv2.COLOR_BGR2LAB)
    l_ch, a_ch, b_ch = cv2.split(lab)

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l_ch = clahe.apply(l_ch)

    merged = cv2.merge([l_ch, a_ch, b_ch])
    result = cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)
    return _cv_to_pil(result)


def _downscale(img: Image.Image, max_long_edge: int = 4000) -> Image.Image:
    """Resize only if the long edge exceeds the limit."""
    w, h = img.size
    long_edge = max(w, h)
    if long_edge <= max_long_edge:
        return img
    scale = max_long_edge / long_edge
    new_w, new_h = int(w * scale), int(h * scale)
    return img.resize((new_w, new_h), Image.LANCZOS)


def preprocess_image(raw_bytes: bytes) -> bytes:
    """
    Full preprocessing pipeline. Returns JPEG bytes ready for Gemini.
    Pipeline: orient → downscale (2000px) → deskew → CLAHE → JPEG encode
    """
    img = Image.open(io.BytesIO(raw_bytes))
    img = _auto_orient(img)
    img = _downscale(img, max_long_edge=2000)
    img = _deskew(img)
    img = _apply_clahe(img)

    # Convert to RGB if needed (removes alpha channel, handles palette modes)
    if img.mode != "RGB":
        img = img.convert("RGB")

    output = io.BytesIO()
    img.save(output, format="JPEG", quality=88, optimize=True)
    return output.getvalue()
