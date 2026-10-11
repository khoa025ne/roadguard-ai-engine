"""
src/utils/io.py — Tiện ích xử lý I/O ảnh và tệp tin tương thích Windows UTF-8
=============================================================================
"""

from pathlib import Path
import cv2
import numpy as np


def safe_imwrite(path: Path | str, img: np.ndarray) -> bool:
    """Ghi ảnh tương thích đường dẫn chứa ký tự tiếng Việt (UTF-8) trên Windows."""
    try:
        ret, buf = cv2.imencode(".jpg", img)
        if ret:
            buf.tofile(str(path))
            return True
        return False
    except Exception:
        return False


def safe_imread(path: Path | str) -> np.ndarray | None:
    """Đọc ảnh tương thích đường dẫn chứa ký tự tiếng Việt (UTF-8) trên Windows."""
    try:
        return cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
    except Exception:
        return None
