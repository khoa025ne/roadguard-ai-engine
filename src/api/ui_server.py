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

# Thiết lập đường dẫn thư mục gốc
WORKSPACE_ROOT = Path("F:/train AI đồ án")
WEB_DIR = WORKSPACE_ROOT / "src/api/web"
RESULTS_DIR = WORKSPACE_ROOT / "results/web_runs"
UPLOADS_DIR = WORKSPACE_ROOT / "results/web_uploads"
WEIGHTS_DIR = WORKSPACE_ROOT / "weights"
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
        size_mb = round(pt_file.stat().st_size / (1024 * 1024), 2)
        models.append({
            "name": pt_file.name,
            "path": str(pt_file).replace("\\", "/"),
            "size_mb": size_mb,
        })
    # Sắp xếp ưu tiên các model mới nhất
    models.sort(key=lambda x: ("15k" in x["name"], "best" in x["name"]), reverse=True)

    preset_videos = []
    if SYNTHETIC_VIDEO.exists():
        preset_videos.append({
            "name": f"🎬 {SYNTHETIC_VIDEO.name} (Video ghép từ 60 ảnh Dataset)",
            "path": str(SYNTHETIC_VIDEO).replace("\\", "/"),
            "size_mb": round(SYNTHETIC_VIDEO.stat().st_size / (1024 * 1024), 2),
        })
    if PRESET_VIDEO.exists():
        preset_videos.append({
            "name": f"📹 {PRESET_VIDEO.name} (Video thực địa Flycam gốc)",
            "path": str(PRESET_VIDEO).replace("\\", "/"),
            "size_mb": round(PRESET_VIDEO.stat().st_size / (1024 * 1024), 1),
        })

    return {
        "models": models,
        "preset_videos": preset_videos,
        "preset_video": preset_videos[0] if preset_videos else None
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


def execute_analysis_sync(task_id: str, req: AnalysisRequest):
    """Hàm chạy ngầm phân tích video và xuất kết quả trực quan."""
    task = TASKS_STORE[task_id]
    task_dir = RESULTS_DIR / task_id
    frames_dir = task_dir / "frames"
    crops_dir = task_dir / "crops"
    frames_dir.mkdir(parents=True, exist_ok=True)
    crops_dir.mkdir(parents=True, exist_ok=True)

    video_path = Path(req.video_path)
    if not video_path.exists():
        task["status"] = "FAILED"
        task["error"] = f"Không tìm thấy file video: {req.video_path}"
        return

    # Khởi tạo mô hình
    task["message"] = "Đang nạp mô hình AI..."
    try:
        predictor = RoadDefectPredictor(req.model_path, conf_threshold=req.conf_threshold)
    except Exception as e:
        task["status"] = "FAILED"
        task["error"] = f"Lỗi nạp mô hình: {str(e)}"
        return

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        task["status"] = "FAILED"
        task["error"] = "Không thể mở file video với OpenCV"
        return

    orig_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_vid_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    video_dur_sec = total_vid_frames / orig_fps

    # Tính toán khoảng bước frame cần đọc
    target_fps = max(1, req.sampling_rate_fps)
    frame_step = max(1, int(round(orig_fps / target_fps)))

    if req.max_duration_seconds > 0:
        max_frames_to_read = min(total_vid_frames, int(req.max_duration_seconds * orig_fps))
    else:
        max_frames_to_read = total_vid_frames

    total_samples = max(1, len(range(0, max_frames_to_read, frame_step)))
    task["total_frames"] = total_samples
    task["message"] = f"Đang trích xuất và phân tích {total_samples} khung hình..."

    detected_frames = []
    crops_list = []
    all_defects = []
    pothole_count = 0
    crack_count = 0
    processed_count = 0

    t_start = time.perf_counter()

    for frame_idx in range(0, max_frames_to_read, frame_step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret or frame is None:
            break

        processed_count += 1
        timestamp_s = round(frame_idx / orig_fps, 2)

        # Chạy inference (Tiling hoặc trực tiếp)
        detections = predictor.predict_full_frame(frame, use_tiling=req.use_tiling)

        frame_potholes = 0
        frame_cracks = 0

        if len(detections) > 0:
            # Vẽ Bounding Box lên ảnh
            annotated_frame = predictor.visualize(frame, detections)
            frame_filename = f"frame_{processed_count:04d}_{timestamp_s}s.jpg"
            frame_save_path = frames_dir / frame_filename
            safe_imwrite(frame_save_path, annotated_frame)

            h, w = frame.shape[:2]

            # Cắt ảnh cận cảnh (Crops) từng khuyết tật
            for d_idx, d in enumerate(detections):
                x1, y1, x2, y2 = d["box"]
                cls_name = d["class_name"]
                conf = d["confidence"]

                if cls_name == "pothole":
                    pothole_count += 1
                    frame_potholes += 1
                    cls_vn = "Ổ gà"
                else:
                    crack_count += 1
                    frame_cracks += 1
                    cls_vn = "Vết nứt"

                # Padding 15px cho ảnh crop
                pad = 15
                cx1 = max(0, x1 - pad)
                cy1 = max(0, y1 - pad)
                cx2 = min(w, x2 + pad)
                cy2 = min(h, y2 + pad)

                crop_img = frame[cy1:cy2, cx1:cx2]
                crop_filename = f"crop_{processed_count:04d}_{d_idx+1}_{cls_name}.jpg"
                crop_save_path = crops_dir / crop_filename
                if crop_img.size > 0:
                    safe_imwrite(crop_save_path, crop_img)

                crop_info = {
                    "url": f"/static_results/{task_id}/crops/{crop_filename}",
                    "class_name": cls_name,
                    "class_vn": cls_vn,
                    "confidence": conf,
                    "timestamp_s": timestamp_s,
                    "box": d["box"]
                }
                crops_list.append(crop_info)

                defect_record = {
                    "frame_index": processed_count,
                    "timestamp_s": timestamp_s,
                    "class_name": cls_name,
                    "class_vn": cls_vn,
                    "confidence": conf,
                    "box": d["box"],
                    "crop_url": crop_info["url"]
                }
                all_defects.append(defect_record)

            detected_frames.append({
                "frame_index": processed_count,
                "timestamp_s": timestamp_s,
                "annotated_url": f"/static_results/{task_id}/frames/{frame_filename}",
                "defects_count": len(detections),
                "pothole_count": frame_potholes,
                "crack_count": frame_cracks,
            })

        # Cập nhật tiến độ
        pct = (processed_count / total_samples) * 100.0
        task["progress_pct"] = round(pct, 1)
        task["processed_frames"] = processed_count
        task["defects_found"] = len(all_defects)
        task["message"] = f"Đang phân tích khung hình {processed_count}/{total_samples} (Tìm thấy {len(all_defects)} khuyết tật)..."

    cap.release()
    total_time = time.perf_counter() - t_start
    fps_calc = round(processed_count / max(0.01, total_time), 2)

    # Xuất file báo cáo JSON
    report_data = {
        "task_id": task_id,
        "video_path": str(video_path),
        "model_path": req.model_path,
        "summary": {
            "processed_frames": processed_count,
            "total_defects": len(all_defects),
            "pothole_count": pothole_count,
            "crack_count": crack_count,
            "fps": fps_calc,
            "total_time_seconds": round(total_time, 2)
        },
        "frames": detected_frames,
        "crops": crops_list,
        "all_defects": all_defects
    }

    report_path = task_dir / "inspection_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)

    # Xuất file GeoJSON (tọa độ pixel chuẩn hóa nếu không có SRT)
    features = []
    for d in all_defects:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [d["box"][0], d["box"][1]]
            },
            "properties": {
                "class_name": d["class_name"],
                "class_vn": d["class_vn"],
                "confidence": d["confidence"],
                "timestamp_s": d["timestamp_s"]
            }
        })
    geojson_data = {
        "type": "FeatureCollection",
        "features": features
    }
    geojson_path = task_dir / "inspection_layer.geojson"
    with open(geojson_path, "w", encoding="utf-8") as f:
        json.dump(geojson_data, f, ensure_ascii=False, indent=2)

    task["status"] = "COMPLETED"
    task["progress_pct"] = 100.0
    task["message"] = "Hoàn tất phân tích toàn bộ khung hình!"
    task["results"] = report_data


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
    if task_id not in TASKS_STORE:
        raise HTTPException(status_code=404, detail="Không tìm thấy task_id")
    task = TASKS_STORE[task_id]
    if task["status"] != "COMPLETED" or not task.get("results"):
        raise HTTPException(status_code=400, detail="Tác vụ chưa hoàn thành hoặc đã lỗi")
    return task["results"]


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


class DatasetExportRequest(BaseModel):
    task_id: str
    curated_items: List[Dict[str, Any]]
    export_name: Optional[str] = None


@app.post("/api/curation/filter-and-tag")
async def filter_and_tag(req: CurationFilterRequest):
    """Sàng lọc và gắn tag chi tiết cho các khuyết tật được chọn."""
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

    curated = tagger.curate_batch(enriched_items)
    return {"status": "SUCCESS", "curated_items": curated}


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

    for it in req.curated_items:
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
        curated_items=req.curated_items,
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

