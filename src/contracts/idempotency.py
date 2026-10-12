"""
src/contracts/idempotency.py — Idempotency Key & Error Classification (AI16, US-26)
==================================================================================
Quản lý khóa chống trùng lặp SHA256 và phân loại lỗi chuẩn mực theo Domain Model v1.
"""

import hashlib
import time
from typing import Dict, Any, Optional


class IdempotencyManager:
    """
    Tạo và quản lý khóa chống trùng lặp:
    idempotency_key = SHA256(ProcessingBlockId + ModelVersionId + ManifestChecksum)
    """

    def __init__(self):
        # Bộ nhớ đệm in-memory (có thể mở rộng sang Redis sau này)
        self._cache: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def generate_key(processing_block_id: str, model_version_id: str, manifest_checksum: str) -> str:
        """Sinh mã băm SHA256 bất biến từ 3 thành phần định danh."""
        raw_key = f"{processing_block_id}_{model_version_id}_{manifest_checksum}".strip()
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def get_cached_result(self, idempotency_key: str) -> Optional[Dict[str, Any]]:
        """Lấy kết quả đã lưu trong bộ đệm nếu có."""
        return self._cache.get(idempotency_key)

    def save_result(self, idempotency_key: str, result_payload: Dict[str, Any]) -> None:
        """Lưu kết quả phân tích gắn với idempotency_key."""
        self._cache[idempotency_key] = {
            "result": result_payload,
            "cached_at": time.time()
        }


class ErrorClassifier:
    """
    Phân loại lỗi chuẩn mực giữa Backend ASP.NET Core và AI Service.
    - INFRASTRUCTURE_ERROR: Cho phép Backend retry có exponential backoff.
    - DATA_ERROR: Chặn retry vô vọng, chuyển Job sang FAILED, thông báo PM bay bổ sung (KS11).
    """

    INFRASTRUCTURE_ERROR = "INFRASTRUCTURE_ERROR"
    DATA_ERROR = "DATA_ERROR"

    # Danh mục mã lỗi chi tiết
    ERROR_CODES = {
        # Hạ tầng (Retryable)
        "GPU_OUT_OF_MEMORY": (INFRASTRUCTURE_ERROR, True, "GPU hết bộ nhớ VRAM khi xử lý đa tile"),
        "WORKER_TIMEOUT": (INFRASTRUCTURE_ERROR, True, "Quá thời gian xử lý cho phép trên hàng đợi"),
        "STORAGE_CONNECTION_FAILED": (INFRASTRUCTURE_ERROR, True, "Mất kết nối tải video từ Object Storage tạm thời"),

        # Dữ liệu khảo sát (Non-retryable)
        "CORRUPTED_VIDEO_FILE": (DATA_ERROR, False, "Tệp video MP4 bị hỏng hoặc không giải mã được codec"),
        "MISSING_SRT_FILE": (DATA_ERROR, False, "Không tìm thấy tệp phụ đề định vị GPS SRT tương ứng"),
        "SRT_SYNC_MISMATCH": (DATA_ERROR, False, "Thời lượng video và SRT bị lệch mốc thời gian quá lớn"),
        "LOW_QUALITY_BLUR": (DATA_ERROR, False, "Tỷ lệ khung hình nhòe mờ vượt quá ngưỡng an toàn (>30%)"),
        "HIGH_ALTITUDE_EXCEEDED": (DATA_ERROR, False, "Độ cao bay vượt quá giới hạn an toàn 20m, GSD không tin cậy"),
        "INVALID_MANIFEST_SCHEMA": (DATA_ERROR, False, "Payload ProcessingInputManifest không hợp lệ theo hợp đồng"),
    }

    @classmethod
    def format_error_response(
        cls,
        processing_job_id: str,
        error_code: str,
        custom_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """Tạo payload báo lỗi chuẩn hóa gửi về cho Backend."""
        err_info = cls.ERROR_CODES.get(error_code, (cls.INFRASTRUCTURE_ERROR, False, "Lỗi không xác định"))
        err_type, retryable, default_msg = err_info

        return {
            "processing_job_id": processing_job_id,
            "status": "FAILED",
            "error_type": err_type,
            "error_code": error_code,
            "error_message": custom_message or default_msg,
            "retryable": retryable,
            "timestamp": time.time()
        }
