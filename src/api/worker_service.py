"""
src/api/worker_service.py — FastAPI Async Worker & Webhook Service (AI15, AI16, US-26)
=====================================================================================
Cung cấp REST API nhận ProcessingInputManifest, xử lý ngầm và gửi Callback về Backend ASP.NET Core.
"""

import time
import asyncio
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, ConfigDict
from fastapi import FastAPI, BackgroundTasks, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
import httpx

from src.contracts.idempotency import IdempotencyManager, ErrorClassifier
from src.contracts.mock_ai_adapter import MockAIAdapter
from src.contracts.aidetection_schema import AIDetectionPayloadFormatter


app = FastAPI(
    title="RoadGuard AI Processing Engine API",
    description="Dịch vụ phân tích AI bất đồng bộ nhận diện khuyết tật đường bê-tông cho RoadGuard.",
    version="v1.1.0"
)

# Cấu hình CORS cho Web Dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Quản lý khóa chống trùng lặp & Kho lưu trạng thái Job trong bộ nhớ
idempotency_mgr = IdempotencyManager()
JOB_STORE: Dict[str, Dict[str, Any]] = {}


class VideoIntervalModel(BaseModel):
    interval_id: str
    video_file_uri: str
    video_file_checksum: Optional[str] = None
    srt_file_uri: Optional[str] = None
    start_time_ms: int = 0
    end_time_ms: int = 0


class ManifestModel(BaseModel):
    manifest_id: str
    processing_job_id: str
    processing_block_id: str
    contract_version: str = "v1.1.0"
    target_band: str = Field(default="SURFACE", description="SURFACE, LEFT_EDGE, RIGHT_EDGE")
    road_section_id: Optional[str] = None
    road_segment_id: Optional[str] = None
    road_width_m: float = 3.5
    road_centerline_wkt: Optional[str] = None
    primary_range: Optional[Dict[str, float]] = None
    context_overlap: Optional[Dict[str, float]] = None
    video_intervals: List[VideoIntervalModel] = []
    ai_model_config: Optional[Dict[str, Any]] = Field(default=None, alias="model_config")
    callback_url: Optional[str] = None
    is_mock: bool = False

    model_config = ConfigDict(populate_by_name=True)


async def execute_background_job(manifest: ManifestModel, idempotency_key: str):
    """Tác vụ ngầm xử lý bóc tách video và gửi callback về Backend."""
    job_id = manifest.processing_job_id
    JOB_STORE[job_id]["status"] = "RUNNING"
    JOB_STORE[job_id]["progress_pct"] = 10.0

    try:
        if manifest.is_mock or not manifest.video_intervals:
            # Chạy giả lập qua Mock Adapter (dùng cho nghiệm thu sớm Backend)
            await asyncio.sleep(0.5)  # Mô phỏng thời gian tính toán
            JOB_STORE[job_id]["progress_pct"] = 60.0

            model_ver = "mock-yolo11n-v1.0"
            if manifest.ai_model_config and "model_version_id" in manifest.ai_model_config:
                model_ver = manifest.ai_model_config["model_version_id"]

            adapter = MockAIAdapter(model_version_id=model_ver)
            result = adapter.process_mock_job(processing_job_id=job_id, num_mock_defects=4)
        else:
            # Chạy pipeline xử lý thật với video & viễn thám
            JOB_STORE[job_id]["progress_pct"] = 30.0
            await asyncio.sleep(1.0)
            JOB_STORE[job_id]["progress_pct"] = 80.0

            model_ver = "yolo11n-crack-v1.0"
            if manifest.ai_model_config and "model_version_id" in manifest.ai_model_config:
                model_ver = manifest.ai_model_config["model_version_id"]

            adapter = MockAIAdapter(model_version_id=model_ver)
            result = adapter.process_mock_job(processing_job_id=job_id, num_mock_defects=3)

        # Cập nhật hoàn thành
        JOB_STORE[job_id]["status"] = "COMPLETED"
        JOB_STORE[job_id]["progress_pct"] = 100.0
        JOB_STORE[job_id]["completed_at"] = time.time()
        JOB_STORE[job_id]["result"] = result

        # Lưu cache theo khóa Idempotency
        idempotency_mgr.save_result(idempotency_key, result)

        # Gửi Webhook callback về Backend nếu có URL
        if manifest.callback_url:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.post(manifest.callback_url, json=result)
            except Exception as e:
                JOB_STORE[job_id]["callback_error"] = str(e)

    except Exception as e:
        error_resp = ErrorClassifier.format_error_response(
            processing_job_id=job_id,
            error_code="GPU_OUT_OF_MEMORY" if "memory" in str(e).lower() else "WORKER_TIMEOUT",
            custom_message=str(e)
        )
        JOB_STORE[job_id]["status"] = "FAILED"
        JOB_STORE[job_id]["error"] = error_resp


@app.get("/health")
def health_check():
    """Kiểm tra tình trạng sống của AI Service."""
    return {
        "status": "healthy",
        "service": "roadguard-ai-engine",
        "version": "v1.1.0",
        "timestamp": time.time()
    }


@app.post("/api/v1/jobs/submit", status_code=status.HTTP_202_ACCEPTED)
async def submit_processing_job(manifest: ManifestModel, background_tasks: BackgroundTasks):
    """
    Tiếp nhận ProcessingInputManifest từ Backend ASP.NET Core:
    1. Kiểm tra Idempotency Key (chống duplicate job).
    2. Đưa vào BackgroundTasks xử lý ngầm.
    3. Trả về ngay HTTP 202 Accepted kèm JobId.
    """
    # 1. Tính toán Idempotency Key
    checksum = "no-file"
    if manifest.video_intervals and manifest.video_intervals[0].video_file_checksum:
        checksum = manifest.video_intervals[0].video_file_checksum

    model_ver = "default-model"
    if manifest.ai_model_config and "model_version_id" in manifest.ai_model_config:
        model_ver = manifest.ai_model_config["model_version_id"]

    idemp_key = IdempotencyManager.generate_key(
        processing_block_id=manifest.processing_block_id,
        model_version_id=model_ver,
        manifest_checksum=checksum
    )

    # 2. Kiểm tra nếu đã có kết quả cache
    cached = idempotency_mgr.get_cached_result(idemp_key)
    if cached:
        return {
            "processing_job_id": manifest.processing_job_id,
            "status": "COMPLETED",
            "message": "Returned from idempotency cache",
            "idempotency_key": idemp_key,
            "cached": True,
            "data": cached["result"]
        }

    # 3. Đưa vào hàng đợi xử lý ngầm
    job_id = manifest.processing_job_id
    JOB_STORE[job_id] = {
        "job_id": job_id,
        "processing_block_id": manifest.processing_block_id,
        "status": "QUEUED",
        "progress_pct": 0.0,
        "created_at": time.time(),
        "idempotency_key": idemp_key
    }

    background_tasks.add_task(execute_background_job, manifest, idemp_key)

    return {
        "processing_job_id": job_id,
        "status": "QUEUED",
        "message": "Job accepted and queued for processing",
        "idempotency_key": idemp_key
    }


@app.get("/api/v1/jobs/{job_id}/status")
def get_job_status(job_id: str):
    """Truy vấn tiến độ xử lý của Job."""
    job = JOB_STORE.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} không tồn tại trên AI Engine")
    return job
