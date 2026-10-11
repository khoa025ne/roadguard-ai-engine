"""
src/api/ui_server.py — FastAPI Web Server cho Giao diện Kiểm thử Video RoadGuard AI
===================================================================================
Phục vụ giao diện web trực quan để người dùng đẩy video lên, chọn mô hình,
chạy phân tích và xem kết quả Bounding Box, ảnh Crop, và báo cáo ngay trên trình duyệt.
"""

import os
import sys
import time
import json
import uuid
import shutil
import asyncio
import math
from pathlib import Path
from typing import Dict, Any, List, Optional
import cv2
import numpy as np
from pydantic import BaseModel, Field
from fastapi import FastAPI, BackgroundTasks, UploadFile, File, HTTPException, status
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from src.inference.predictor import RoadDefectPredictor
from src.curation import AIAutoTagger, DatasetExporter
from src.ingestion.dataset_scanner import DatasetScanner
from src.pipeline.pipeline import run_video_analysis_task

# Thiết lập đường dẫn thư mục gốc
WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = WORKSPACE_ROOT / "src/api/web"
RESULTS_DIR = WORKSPACE_ROOT / "results/web_runs"
UPLOADS_DIR = WORKSPACE_ROOT / "results/web_uploads"
WEIGHTS_DIR = WORKSPACE_ROOT / "weights"
PRESET_VIDEO = WORKSPACE_ROOT / "data/raw_videos/DJI_0057.MP4"
if not PRESET_VIDEO.exists():
    PRESET_VIDEO = Path("F:/Fake_admin/Downloads/đồ án test vid/DJI_0057.MP4")
SYNTHETIC_VIDEO = WORKSPACE_ROOT / "results/test_videos/dataset_road_survey_test.mp4"

RESULTS_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
CURATED_EXPORT_DIR = WORKSPACE_ROOT / "data/curated_export"
CURATED_EXPORT_DIR.mkdir(parents=True, exist_ok=True)


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

app = FastAPI(
    title="RoadGuard AI Web Test Bench",
    description="Giao diện kiểm thử hiệu năng mô hình AI và trực quan hóa khuyết tật mặt đường.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount thư mục lưu kết quả ảnh để trình duyệt tải được
app.mount("/static_results", StaticFiles(directory=str(RESULTS_DIR)), name="static_results")

# Bộ nhớ lưu trạng thái tác vụ
TASKS_STORE: Dict[str, Dict[str, Any]] = {}


class AnalysisRequest(BaseModel):
    video_path: str
    model_path: str
    conf_threshold: float = 0.25
    max_duration_seconds: int = 30
    sampling_rate_fps: int = 2
    use_tiling: bool = True


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = WEB_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Không tìm thấy file giao diện index.html")
    with open(index_file, "r", encoding="utf-8") as f:
        return f.read()


@app.get("/api/init-info")
async def get_init_info():
    """Lấy danh sách mô hình có sẵn và video mẫu."""
    models = []
    # Tìm kiếm các file .pt trong thư mục weights
    for pt_file in WEIGHTS_DIR.glob("**/*.pt"):
        if pt_file.stat().st_size == 0:
            continue
        size_mb = round(pt_file.stat().st_size / (1024 * 1024), 2)
        models.append({
            "name": pt_file.name,
            "path": str(pt_file).replace("\\", "/"),
            "size_mb": size_mb,
            "mtime": pt_file.stat().st_mtime,
        })
    # Sắp xếp mô hình mới nhất (file sửa đổi/tạo gần đây nhất) lên trên cùng
    models.sort(key=lambda x: x["mtime"], reverse=True)

    preset_videos = []
    if SYNTHETIC_VIDEO.exists():
        preset_videos.append({
            "name": f"[Video Ghép] {SYNTHETIC_VIDEO.name} (60 ảnh Dataset)",
            "path": str(SYNTHETIC_VIDEO).replace("\\", "/"),
            "size_mb": round(SYNTHETIC_VIDEO.stat().st_size / (1024 * 1024), 2),
        })
    if PRESET_VIDEO.exists():
        preset_videos.append({
            "name": f"[Video Thực Địa] {PRESET_VIDEO.name} (Flycam gốc)",
            "path": str(PRESET_VIDEO).replace("\\", "/"),
            "size_mb": round(PRESET_VIDEO.stat().st_size / (1024 * 1024), 1),
        })

    preset_datasets = []
    sample_zip = WORKSPACE_ROOT / "data/sample_dataset_test.zip"
    if sample_zip.exists():
        preset_datasets.append({
            "name": f"[ZIP Mẫu] {sample_zip.name} (5 ảnh Pothole Test)",
            "path": str(sample_zip).replace("\\", "/"),
            "size_mb": round(sample_zip.stat().st_size / (1024 * 1024), 2)
        })
    pothole_5k_zip = WORKSPACE_ROOT / "data/pothole_dataset_5k.zip"
    if pothole_5k_zip.exists():
        preset_datasets.append({
            "name": "[ZIP 5K] pothole_dataset_5k.zip (5,000 ảnh Ổ gà)",
            "path": str(pothole_5k_zip).replace("\\", "/"),
            "size_mb": round(pothole_5k_zip.stat().st_size / (1024 * 1024), 1)
        })

    pothole_dir = WORKSPACE_ROOT / "data/pothole/test/images"
    if pothole_dir.exists():
        preset_datasets.append({
            "name": "[Folder Test] data/pothole/test/images (198 ảnh Test Pothole)",
            "path": str(pothole_dir).replace("\\", "/"),
            "size_mb": 0.0
        })

    dataset_15k_test = WORKSPACE_ROOT / "data/unified_road_dataset_15k/test/images"
    if dataset_15k_test.exists():
        preset_datasets.append({
            "name": "[Folder 15K] data/unified_road_dataset_15k/test/images (751 ảnh Test 15K: Pothole & Crack)",
            "path": str(dataset_15k_test).replace("\\", "/"),
            "size_mb": 0.0
        })

    dataset_15k_valid = WORKSPACE_ROOT / "data/unified_road_dataset_15k/valid/images"
    if dataset_15k_valid.exists():
        preset_datasets.append({
            "name": "[Folder Val] data/unified_road_dataset_15k/valid/images (2,056 ảnh Val 15K)",
            "path": str(dataset_15k_valid).replace("\\", "/"),
            "size_mb": 0.0
        })

    latest_task_id = None
    if RESULTS_DIR.exists():
        task_candidates = [
            d for d in RESULTS_DIR.iterdir()
            if d.is_dir() and (d / "inspection_report.json").exists()
        ]
        if task_candidates:
            task_candidates.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            latest_task_id = task_candidates[0].name

    return {
        "models": models,
        "preset_videos": preset_videos,
        "preset_video": preset_videos[0] if preset_videos else None,
        "preset_datasets": preset_datasets,
        "preset_dataset": preset_datasets[0] if preset_datasets else None,
        "latest_task_id": latest_task_id
    }


@app.post("/api/upload-video")
async def upload_video(file: UploadFile = File(...)):
    """Tiếp nhận video tải lên từ máy tính."""
    ext = Path(file.filename).suffix.lower()
    if ext not in [".mp4", ".mov", ".avi", ".mkv"]:
        raise HTTPException(status_code=400, detail="Chỉ hỗ trợ file video (.mp4, .mov, .avi, .mkv)")

    safe_name = f"upload_{int(time.time())}_{file.filename}"
    saved_path = UPLOADS_DIR / safe_name
    with open(saved_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {
        "message": "Tải video lên thành công",
        "filename": file.filename,
        "saved_path": str(saved_path).replace("\\", "/")
    }


@app.post("/api/upload-dataset")
async def upload_dataset(file: UploadFile = File(...)):
    """Tiếp nhận file nén dataset (.zip) tải lên từ máy tính."""
    ext = Path(file.filename).suffix.lower()
    if ext != ".zip":
        raise HTTPException(status_code=400, detail="Chỉ hỗ trợ file nén dataset (.zip)")

    safe_name = f"dataset_{int(time.time())}_{file.filename}"
    saved_path = UPLOADS_DIR / safe_name
    with open(saved_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {
        "message": "Tải dataset ZIP lên thành công",
        "filename": file.filename,
        "saved_path": str(saved_path).replace("\\", "/")
    }


@app.post("/api/upload-folder")
async def upload_folder(files: List[UploadFile] = File(...)):
    """Tiếp nhận tải lên nguyên thư mục ảnh từ trình duyệt."""
    if not files:
        raise HTTPException(status_code=400, detail="Chưa chọn file ảnh nào")

    folder_id = f"folder_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    target_folder = UPLOADS_DIR / folder_id
    target_folder.mkdir(parents=True, exist_ok=True)

    saved_count = 0
    for f in files:
        fname = Path(f.filename).name
        ext = Path(fname).suffix.lower()
        if ext in [".jpg", ".jpeg", ".png", ".bmp", ".webp"]:
            dest = target_folder / fname
            with open(dest, "wb") as buffer:
                shutil.copyfileobj(f.file, buffer)
            saved_count += 1

    if saved_count == 0:
        raise HTTPException(status_code=400, detail="Thư mục tải lên không chứa file ảnh hợp lệ (.jpg, .png, .jpeg)")

    return {
        "message": f"Tải lên thành công {saved_count} file ảnh",
        "saved_path": str(target_folder).replace("\\", "/"),
        "count": saved_count
    }


@app.get("/api/frames/{task_id}/{filename}")
async def serve_frame_file(task_id: str, filename: str):
    fpath = RESULTS_DIR / task_id / "frames" / filename
    if not fpath.exists():
        fpath = RESULTS_DIR / task_id / "visualizations" / filename
    if not fpath.exists():
        raise HTTPException(status_code=404, detail="Ảnh không tồn tại")
    return FileResponse(str(fpath))


@app.get("/api/crops/{task_id}/{filename}")
async def serve_crop_file(task_id: str, filename: str):
    fpath = RESULTS_DIR / task_id / "crops" / filename
    if not fpath.exists():
        raise HTTPException(status_code=404, detail="Ảnh crop không tồn tại")
    return FileResponse(str(fpath))


def execute_analysis_sync(task_id: str, req: AnalysisRequest):
    """Hàm chạy ngầm phân tích video qua Pipeline Tuyến Tính Kiến Trúc A (7 stages)."""
    task = TASKS_STORE[task_id]
    task_dir = RESULTS_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    video_path = Path(req.video_path)
    if not video_path.exists():
        task["status"] = "FAILED"
        task["error"] = f"Không tìm thấy file video: {req.video_path}"
        return

    task["message"] = "Đang khởi chạy Pipeline Tuyến Tính (Kiến Trúc A: 7 Stages)..."
    task["progress_pct"] = 15.0

    try:
        report_data = run_video_analysis_task(
            video_path=video_path,
            model_path=req.model_path,
            task_id=task_id,
            output_dir=task_dir,
            conf_threshold=req.conf_threshold,
            max_duration_seconds=req.max_duration_seconds,
            sampling_rate_fps=req.sampling_rate_fps,
            use_tiling=req.use_tiling
        )

        task["status"] = "COMPLETED"
        task["progress_pct"] = 100.0
        task["message"] = "Hoàn tất phân tích qua Pipeline Tuyến Tính!"
        task["results"] = report_data
    except Exception as e:
        task["status"] = "FAILED"
        task["error"] = f"Lỗi trong quá trình phân tích Pipeline: {str(e)}"


@app.post("/api/start-analysis")
async def start_analysis(req: AnalysisRequest, bg: BackgroundTasks):
    task_id = f"task_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    TASKS_STORE[task_id] = {
        "status": "RUNNING",
        "progress_pct": 0.0,
        "processed_frames": 0,
        "total_frames": 0,
        "defects_found": 0,
        "message": "Đang chuẩn bị tiến trình...",
        "error": None,
        "results": None
    }
    bg.add_task(execute_analysis_sync, task_id, req)
    return {"task_id": task_id, "status": "STARTED"}


class DatasetAnalysisRequest(BaseModel):
    zip_path: Optional[str] = None
    folder_path: Optional[str] = None
    model_path: str = "weights/trained/roadguard_best_15k.pt"
    conf_threshold: float = 0.25
    max_images: Optional[int] = 50


def execute_dataset_analysis_sync(task_id: str, req: DatasetAnalysisRequest):
    """Hàm chạy ngầm giải nén zip, quét ảnh dataset và trích xuất khuyết tật."""
    task = TASKS_STORE[task_id]
    task_dir = RESULTS_DIR / task_id
    frames_dir = task_dir / "frames"
    crops_dir = task_dir / "crops"
    unzipped_dir = task_dir / "unzipped"
    frames_dir.mkdir(parents=True, exist_ok=True)
    crops_dir.mkdir(parents=True, exist_ok=True)

    task["message"] = "Đang nạp mô hình AI..."
    try:
        predictor = RoadDefectPredictor(req.model_path, conf_threshold=req.conf_threshold)
    except Exception as e:
        task["status"] = "FAILED"
        task["error"] = f"Lỗi nạp mô hình: {str(e)}"
        return

    scanner = DatasetScanner(predictor=predictor)

    task["message"] = "Đang chuẩn bị danh sách ảnh dataset..."
    image_paths = []
    if req.zip_path:
        z_path = Path(req.zip_path)
        if not z_path.exists():
            task["status"] = "FAILED"
            task["error"] = f"Không tìm thấy file ZIP: {req.zip_path}"
            return
        try:
            image_paths = scanner.extract_zip(z_path, unzipped_dir)
        except Exception as e:
            task["status"] = "FAILED"
            task["error"] = f"Lỗi giải nén ZIP: {str(e)}"
            return
    elif req.folder_path:
        f_path = Path(req.folder_path)
        if not f_path.exists():
            task["status"] = "FAILED"
            task["error"] = f"Không tìm thấy thư mục: {req.folder_path}"
            return
        image_paths = scanner.find_images_in_folder(f_path)
    else:
        task["status"] = "FAILED"
        task["error"] = "Vui lòng cung cấp zip_path hoặc folder_path"
        return

    if not image_paths:
        task["status"] = "FAILED"
        task["error"] = "Không tìm thấy file ảnh hợp lệ nào trong dataset"
        return

    if req.max_images and len(image_paths) > req.max_images:
        image_paths = image_paths[:req.max_images]

    task["total_frames"] = len(image_paths)

    def on_progress(current, total, filename):
        task["processed_frames"] = current
        task["progress_pct"] = round((current / total) * 100, 1)
        task["message"] = f"Đang quét ảnh {current}/{total}: {filename[:25]}"

    try:
        report = scanner.scan_images(
            image_paths=image_paths,
            output_dir=task_dir,
            predictor=predictor,
            progress_callback=on_progress
        )
    except Exception as e:
        task["status"] = "FAILED"
        task["error"] = f"Lỗi khi quét dataset: {str(e)}"
        return

    # Chuẩn hóa dữ liệu trả về cho Web UI
    web_frames = []
    for img_info in report.get("images", []):
        vpath = Path(img_info["vis_path"])
        f_name = f"frame_{img_info['image_index']:04d}_vis.jpg"
        target_fpath = frames_dir / f_name
        if vpath.exists():
            shutil.copy2(vpath, target_fpath)

        frame_url = f"/static_results/{task_id}/frames/{f_name}"
        web_frames.append({
            "frame_id": f"img_{img_info['image_index']}",
            "frame_index": img_info["image_index"],
            "timestamp_s": round(img_info["image_index"] * 0.5, 2),
            "filename": f_name,
            "annotated_url": frame_url,
            "image_url": frame_url,
            "original_name": img_info["filename"],
            "defects_count": img_info["defect_count"],
            "pothole_count": sum(1 for d in img_info["detections"] if "pothole" in d.get("class_name", "").lower() or d.get("class_id") == 0),
            "crack_count": sum(1 for d in img_info["detections"] if "crack" in d.get("class_name", "").lower() or d.get("class_id") != 0),
            "defects": img_info["detections"],
            "has_defect": img_info["has_defect"]
        })

    web_crops = []
    all_defects = []
    for c in report.get("all_crops", []):
        crop_file = Path(c["crop_path"]).name
        # Đảm bảo ảnh crop nằm sẵn trong crops_dir
        dest_crop = crops_dir / crop_file
        if Path(c["crop_path"]).resolve() != dest_crop.resolve() and Path(c["crop_path"]).exists():
            shutil.copy2(c["crop_path"], dest_crop)

        crop_url = f"/static_results/{task_id}/crops/{crop_file}"
        crop_entry = {
            "crop_id": c["crop_id"],
            "crop_file": crop_file,
            "url": crop_url,
            "crop_url": crop_url,
            "crop_path": str(dest_crop),
            "frame_index": c["image_index"],
            "timestamp_s": c["timestamp_s"],
            "class_name": c["class_name"],
            "class_vn": "Ổ gà" if c["class_name"] == "pothole" else "Vết nứt",
            "confidence": c["confidence"],
            "box": c["box"]
        }
        web_crops.append(crop_entry)

        all_defects.append({
            "frame_index": c["image_index"],
            "timestamp_s": c["timestamp_s"],
            "class_name": c["class_name"],
            "class_vn": crop_entry["class_vn"],
            "confidence": c["confidence"],
            "box": c["box"],
            "crop_url": crop_url
        })

    summary = report.get("summary", {})
    results = {
        "task_id": task_id,
        "dataset_mode": True,
        "summary": {
            "total_frames": summary.get("total_images", 0),
            "defect_frames": summary.get("defect_images", 0),
            "clean_frames": summary.get("clean_images", 0),
            "hit_rate_pct": summary.get("hit_rate_pct", 0.0),
            "total_defects": summary.get("total_defects_found", 0),
            "crack_count": summary.get("crack_count", 0),
            "pothole_count": summary.get("pothole_count", 0),
            "cracks_count": summary.get("crack_count", 0),
            "potholes_count": summary.get("pothole_count", 0),
            "avg_latency_ms": summary.get("avg_latency_ms", 0.0),
            "fps": summary.get("fps", 0.0),
            "total_crops": len(web_crops)
        },
        "frames": web_frames,
        "crops": web_crops,
        "all_defects": all_defects
    }

    task["status"] = "COMPLETED"
    task["progress_pct"] = 100.0
    task["defects_found"] = summary.get("total_defects_found", 0)
    task["message"] = f"Hoàn tất quét {summary.get('total_images', 0)} ảnh dataset! (Tìm thấy {summary.get('total_defects_found', 0)} khuyết tật)"
    task["results"] = results


@app.post("/api/start-dataset-analysis")
async def start_dataset_analysis(req: DatasetAnalysisRequest, bg: BackgroundTasks):
    task_id = f"task_ds_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    TASKS_STORE[task_id] = {
        "status": "RUNNING",
        "progress_pct": 0.0,
        "processed_frames": 0,
        "total_frames": 0,
        "defects_found": 0,
        "message": "Đang khởi tạo tác vụ quét dataset...",
        "error": None,
        "results": None
    }
    bg.add_task(execute_dataset_analysis_sync, task_id, req)
    return {"task_id": task_id, "status": "STARTED"}


@app.get("/api/task-status/{task_id}")
async def get_task_status(task_id: str):
    if task_id not in TASKS_STORE:
        raise HTTPException(status_code=404, detail="Không tìm thấy task_id")
    task = TASKS_STORE[task_id]
    return {
        "task_id": task_id,
        "status": task["status"],
        "progress_pct": task["progress_pct"],
        "processed_frames": task["processed_frames"],
        "total_frames": task["total_frames"],
        "defects_found": task["defects_found"],
        "message": task["message"],
        "error": task["error"]
    }


@app.get("/api/task-results/{task_id}")
async def get_task_results(task_id: str):
    task_dir = RESULTS_DIR / task_id
    if task_id not in TASKS_STORE:
        # Tự động phục hồi tác vụ từ ổ đĩa nếu máy chủ vừa khởi động lại
        rep_file = task_dir / "inspection_report.json"
        if rep_file.exists():
            try:
                with open(rep_file, "r", encoding="utf-8") as f:
                    rep_data = json.load(f)
                    all_defects = rep_data.get("all_defects", [])
                    TASKS_STORE[task_id] = {
                        "status": "COMPLETED",
                        "progress_pct": 100.0,
                        "processed_frames": rep_data.get("summary", {}).get("processed_frames", len(rep_data.get("frames", []))),
                        "total_frames": rep_data.get("summary", {}).get("total_frames", len(rep_data.get("frames", []))),
                        "defects_found": len(all_defects),
                        "message": "Đã nạp kết quả phân tích từ bộ nhớ lưu trữ",
                        "error": None,
                        "results": rep_data
                    }
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Lỗi đọc dữ liệu: {str(e)}")
        else:
            raise HTTPException(status_code=404, detail="Không tìm thấy task_id")

    task = TASKS_STORE[task_id]
    if task["status"] != "COMPLETED" or not task.get("results"):
        raise HTTPException(status_code=400, detail="Tác vụ chưa hoàn thành hoặc đã lỗi")

    results = dict(task["results"])
    # Tự động nạp curated_results.json nếu đã có kết quả thẩm định của KTV
    cur_file = task_dir / "curated_results.json"
    if cur_file.exists():
        try:
            with open(cur_file, "r", encoding="utf-8") as f:
                results["curated_items"] = json.load(f)
        except Exception:
            results["curated_items"] = []
    else:
        results["curated_items"] = []

    return results


@app.get("/api/download/{task_id}/{filename}")
async def download_file(task_id: str, filename: str):
    task_dir = RESULTS_DIR / task_id
    if filename == "report.json":
        fpath = task_dir / "inspection_report.json"
    elif filename == "layer.geojson":
        fpath = task_dir / "inspection_layer.geojson"
    else:
        raise HTTPException(status_code=404, detail="File không tồn tại")

    if not fpath.exists():
        raise HTTPException(status_code=404, detail="File chưa sẵn sàng")
    return FileResponse(str(fpath), filename=filename)


class CurationFilterRequest(BaseModel):
    task_id: str
    items: List[Dict[str, Any]]
    batch_size: Optional[int] = 100
    apply_dedup: Optional[bool] = True


class OverviewInspectionRequest(BaseModel):
    task_id: str
    frame_index: Optional[int] = None
    items: Optional[List[Dict[str, Any]]] = None
    road_metadata: Optional[Dict[str, Any]] = None
    batch_size: Optional[int] = 6


class CrackAssessRequest(BaseModel):
    task_id: str
    items: Optional[List[Dict[str, Any]]] = None


class ItemUpdateRequest(BaseModel):
    task_id: str
    item_index: int
    updated_item: Dict[str, Any]


class SaveCuratedItemsRequest(BaseModel):
    task_id: str
    curated_items: List[Dict[str, Any]]


class DatasetExportRequest(BaseModel):
    task_id: str
    curated_items: List[Dict[str, Any]]
    export_name: Optional[str] = None
    export_unique_only: Optional[bool] = True


@app.post("/api/curation/filter-and-tag")
async def filter_and_tag(req: CurationFilterRequest):
    """Sàng lọc và gắn tag chi tiết cho các khuyết tật được chọn (Gom 100 ảnh / 1 request KTV, khử trùng lặp)."""
    tagger = AIAutoTagger()
    task_dir = RESULTS_DIR / req.task_id

    enriched_items = []
    for item in req.items:
        it = dict(item)
        if "crop_path" not in it or not Path(it["crop_path"]).exists():
            url = it.get("url") or it.get("crop_url", "")
            if url:
                cname = Path(url).name
                local_crop = task_dir / "crops" / cname
                if local_crop.exists():
                    it["crop_path"] = str(local_crop)
        enriched_items.append(it)

    batch_sz = req.batch_size or 100
    curated = tagger.curate_batch(enriched_items, batch_size=batch_sz, apply_dedup=False)

    # Khử trùng lặp đối tượng
    dedup_res = tagger.deduplicate_items(curated)
    deduped_items = dedup_res["deduplicated_items"]
    unique_items = dedup_res["unique_items"]

    # Lưu lại kết quả xuống task_dir để phục hồi trạng thái khi người dùng chỉnh sửa
    try:
        cur_file = task_dir / "curated_results.json"
        with open(cur_file, "w", encoding="utf-8") as f:
            json.dump(deduped_items, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    requests_used = math.ceil(len(enriched_items) / batch_sz) if enriched_items else 0
    return {
        "status": "SUCCESS",
        "curated_items": deduped_items,
        "unique_items": unique_items,
        "total_items": len(enriched_items),
        "unique_count": dedup_res["unique_count"],
        "duplicate_count": dedup_res["duplicate_count"],
        "requests_used": requests_used
    }


@app.post("/api/curation/inspect-overview-context")
async def inspect_overview_context_endpoint(req: OverviewInspectionRequest):
    """
    Thẩm định KTV AI GPT-5.4 Vision chế độ DUAL-VIEW CONTEXT:
    Đọc trực tiếp ảnh Khung hình Tổng thể chưa cắt (Overview Frame) bao quát tuyến đường
    kết hợp ảnh cắt cận cảnh phóng to (Zoom-in patches) để phân tích bối cảnh công trình,
    khe co giãn, bóng dây điện, tạp vật ven đường và đánh giá định lượng độ mở vết nứt/hố.
    """
    tagger = AIAutoTagger()
    task_dir = RESULTS_DIR / req.task_id
    frames_dir = task_dir / "frames"
    crops_dir = task_dir / "crops"

    # Lấy thông tin task và kết quả đã lưu
    cur_file = task_dir / "curated_results.json"
    existing_curated = []
    if cur_file.exists():
        try:
            with open(cur_file, "r", encoding="utf-8") as f:
                existing_curated = json.load(f)
        except Exception:
            existing_curated = []

    # Nạp danh sách items cần thẩm định
    items_to_process = req.items or []
    if not items_to_process and existing_curated:
        items_to_process = existing_curated
    elif not items_to_process:
        # Lấy từ task results report.json
        res_file = task_dir / "report.json"
        if res_file.exists():
            try:
                with open(res_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    items_to_process = data.get("all_crops") or data.get("crops") or []
            except Exception:
                items_to_process = []

    if not items_to_process:
        raise HTTPException(status_code=400, detail="Không tìm thấy danh sách khuyết tật để thẩm định bối cảnh")

    # Gom nhóm theo từng khung hình tổng thể (frame_index)
    grouped_by_frame = {}
    for item in items_to_process:
        it = dict(item)
        if "crop_path" not in it or not Path(it["crop_path"]).exists():
            url = it.get("url") or it.get("crop_url", "")
            if url:
                cname = Path(url).name
                local_crop = crops_dir / cname
                if local_crop.exists():
                    it["crop_path"] = str(local_crop)

        f_idx = it.get("frame_index", 1)
        if req.frame_index is not None and int(f_idx) != int(req.frame_index):
            continue

        if f_idx not in grouped_by_frame:
            grouped_by_frame[f_idx] = []
        grouped_by_frame[f_idx].append(it)

    if not grouped_by_frame:
        raise HTTPException(status_code=400, detail="Không tìm thấy khung hình phù hợp với yêu cầu")

    road_meta = req.road_metadata or {
        "road_name": "Tuyến đường bê tông xi măng nông thôn",
        "road_width_m": 5.0,
        "pavement_type": "Mặt đường bê tông có khe co giãn nhiệt định kỳ 4m-5m"
    }

    all_curated_results = []
    # Tiến hành xử lý theo từng Khung hình Tổng thể
    for f_idx, f_items in grouped_by_frame.items():
        # Tìm file ảnh khung hình tổng thể (Overview Frame)
        overview_path = None
        for candidate_name in [f"frame_{f_idx:04d}_vis.jpg", f"frame_{f_idx:04d}.jpg", f"frame_{f_idx}.jpg"]:
            cand = frames_dir / candidate_name
            if cand.exists():
                overview_path = cand
                break
            cand_vis = task_dir / "visualizations" / candidate_name
            if cand_vis.exists():
                overview_path = cand_vis
                break

        if not overview_path and frames_dir.exists():
            frame_files = list(frames_dir.glob(f"*{f_idx}*.jpg"))
            if frame_files:
                overview_path = frame_files[0]

        batch_sz = req.batch_size or 6
        curated_frame_items = tagger.curate_with_overview_context(
            overview_image=overview_path or "",
            items=f_items,
            road_metadata=road_meta,
            batch_size=batch_sz
        )

        overview_url = f"/static_results/{req.task_id}/frames/{overview_path.name}" if overview_path else ""
        for c_item in curated_frame_items:
            c_item["overview_frame_url"] = overview_url
            c_item["overview_frame_index"] = f_idx

        all_curated_results.extend(curated_frame_items)

    # Khử trùng lặp đối tượng và gán Defect_ID định danh bất biến
    dedup_res = tagger.deduplicate_items(all_curated_results)
    deduped_items = dedup_res["deduplicated_items"]
    unique_items = dedup_res["unique_items"]

    # Lưu lại kết quả tổng hợp vào curated_results.json
    try:
        cur_file = task_dir / "curated_results.json"
        with open(cur_file, "w", encoding="utf-8") as f:
            json.dump(deduped_items, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    return {
        "status": "SUCCESS",
        "message": f"Đã thẩm định xong bối cảnh toàn cảnh cho {len(grouped_by_frame)} khung hình tổng thể với GPT-5.4 Vision",
        "curated_items": deduped_items,
        "unique_items": unique_items,
        "total_items": len(all_curated_results),
        "unique_count": dedup_res["unique_count"],
        "duplicate_count": dedup_res["duplicate_count"],
        "frames_processed": len(grouped_by_frame)
    }


@app.post("/api/curation/assess-cracks")

async def assess_cracks_endpoint(req: CrackAssessRequest):
    """Chức năng đánh giá và phân loại vết nứt chuyên sâu."""
    tagger = AIAutoTagger()
    task_dir = RESULTS_DIR / req.task_id

    items = req.items
    if not items:
        cur_file = task_dir / "curated_results.json"
        if cur_file.exists():
            try:
                with open(cur_file, "r", encoding="utf-8") as f:
                    items = json.load(f)
            except Exception:
                items = []

    if not items:
        # Lấy từ task results
        res_file = task_dir / "report.json"
        if res_file.exists():
            try:
                with open(res_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    items = data.get("all_crops") or data.get("crops") or []
            except Exception:
                items = []

    if not items:
        return {"status": "ERROR", "message": "Không tìm thấy danh sách ảnh vết nứt để phân tích"}

    crack_results = []
    for item in items:
        it = dict(item)
        c_path = it.get("crop_path")
        if not c_path or not Path(c_path).exists():
            url = it.get("url") or it.get("crop_url", "")
            if url:
                cname = Path(url).name
                local_crop = task_dir / "crops" / cname
                if local_crop.exists():
                    c_path = str(local_crop)
                    it["crop_path"] = c_path

        conf = float(it.get("confidence", 0.5))
        c_analysis = tagger.assess_crack(c_path or "", confidence=conf)
        merged = {**it, **c_analysis}
        crack_results.append(merged)

    # Khử trùng lặp
    dedup_res = tagger.deduplicate_items(crack_results)

    # Lưu lại kết quả
    try:
        cur_file = task_dir / "curated_results.json"
        with open(cur_file, "w", encoding="utf-8") as f:
            json.dump(dedup_res["deduplicated_items"], f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    return {
        "status": "SUCCESS",
        "curated_items": dedup_res["deduplicated_items"],
        "unique_items": dedup_res["unique_items"],
        "total_items": len(crack_results),
        "unique_count": dedup_res["unique_count"],
        "duplicate_count": dedup_res["duplicate_count"]
    }


@app.post("/api/curation/update-item")
async def update_curation_item(req: ItemUpdateRequest):
    """Cập nhật và lưu lại nội dung đánh giá của KTV sau khi người dùng chỉnh sửa."""
    task_dir = RESULTS_DIR / req.task_id
    cur_file = task_dir / "curated_results.json"

    items = []
    if cur_file.exists():
        try:
            with open(cur_file, "r", encoding="utf-8") as f:
                items = json.load(f)
        except Exception:
            items = []

    if 0 <= req.item_index < len(items):
        items[req.item_index] = req.updated_item
        items[req.item_index]["user_edited"] = True
        items[req.item_index]["edited_at"] = time.time()
        try:
            with open(cur_file, "w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False, indent=2)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Lỗi lưu file: {str(e)}")
        return {"status": "SUCCESS", "message": "Đã lưu chỉnh sửa thành công", "item": items[req.item_index]}

    return {"status": "SUCCESS", "message": "Đã ghi nhận chỉnh sửa trên client"}


@app.post("/api/curation/save-all")
async def save_all_curated(req: SaveCuratedItemsRequest):
    """Lưu toàn bộ danh sách đánh giá đã qua chỉnh sửa của người dùng."""
    task_dir = RESULTS_DIR / req.task_id
    cur_file = task_dir / "curated_results.json"
    try:
        with open(cur_file, "w", encoding="utf-8") as f:
            json.dump(req.curated_items, f, ensure_ascii=False, indent=2)
        return {"status": "SUCCESS", "message": "Đã lưu toàn bộ nhận định"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi lưu kết quả: {str(e)}")


@app.get("/api/curation/results/{task_id}")
async def get_curation_results(task_id: str):
    """Lấy lại kết quả thẩm định đã lưu (bao gồm cả các nhận định người dùng đã chỉnh sửa)."""
    task_dir = RESULTS_DIR / task_id
    cur_file = task_dir / "curated_results.json"
    if cur_file.exists():
        try:
            with open(cur_file, "r", encoding="utf-8") as f:
                items = json.load(f)
            return {"status": "SUCCESS", "curated_items": items}
        except Exception:
            pass
    return {"status": "NOT_FOUND", "curated_items": []}


@app.post("/api/curation/export-dataset")
async def export_curated_dataset(req: DatasetExportRequest):
    """Đóng gói danh sách khuyết tật đã thẩm định thành dataset YOLO."""
    task_dir = RESULTS_DIR / req.task_id
    frames_dir = task_dir / "frames"

    frames_lookup = {}
    if frames_dir.exists():
        for fp in frames_dir.glob("*.jpg"):
            parts = fp.stem.split("_")
            if len(parts) >= 2 and parts[1].isdigit():
                f_idx = str(int(parts[1]))
                frames_lookup[f_idx] = str(fp)

    items_to_export = req.curated_items
    if req.export_unique_only:
        # Chỉ xuất các khuyết tật độc nhất (bỏ qua các góc chụp trùng lặp)
        items_to_export = [it for it in req.curated_items if not it.get("is_duplicate", False)]

    for it in items_to_export:
        f_idx = str(it.get("frame_index", ""))
        if f_idx in frames_lookup and not it.get("frame_path"):
            it["frame_path"] = frames_lookup[f_idx]
        if not it.get("crop_path"):
            url = it.get("url") or it.get("crop_url", "")
            if url:
                cname = Path(url).name
                local_crop = task_dir / "crops" / cname
                if local_crop.exists():
                    it["crop_path"] = str(local_crop)

    exporter = DatasetExporter(base_export_dir=CURATED_EXPORT_DIR)
    res = exporter.export_yolo_dataset(
        curated_items=items_to_export,
        frames_lookup=frames_lookup,
        export_name=req.export_name
    )
    res["download_url"] = f"/api/curation/download/{res['zip_filename']}"
    return res


@app.get("/api/curation/download/{filename}")
async def download_curated_zip(filename: str):
    zip_path = CURATED_EXPORT_DIR / filename
    if not zip_path.exists():
        raise HTTPException(status_code=404, detail="File zip không tồn tại")
    return FileResponse(str(zip_path), filename=filename, media_type="application/zip")


