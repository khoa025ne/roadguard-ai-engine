"""
pipeline.py — Master End-to-End Runner cho Hệ Thống RoadGuard AI
================================================================
Kết nối toàn bộ 4 tầng xử lý:
  Video + SRT -> Ingestion -> Tiling 640x640 -> AI Inference -> 2D Metric -> Tracking -> Báo cáo JSON & GeoJSON

CÁCH SỬ DỤNG:
  # Chạy phân tích video flycam:
  python pipeline.py --video flight.mp4 --srt flight.srt --model weights/base/best.pt --output results/

  # Chạy test giả lập (Mock mode cho Backend test sớm):
  python pipeline.py --mock --output results/
"""

import sys
import time
import json
import argparse
from pathlib import Path

# Thêm thư mục gốc vào path để import src
sys.path.append(str(Path(__file__).parent))

from src.ingestion.srt_parser import DJISRTParser
from src.ingestion.video_extractor import VideoFrameExtractor
from src.inference.predictor import RoadDefectPredictor
from src.measurement.metric_estimator import MetricEstimator
from src.measurement.spatial_tracker import SpatialTracker
from src.contracts.aidetection_schema import AIDetectionPayloadFormatter
from src.contracts.mock_ai_adapter import MockAIAdapter


def run_pipeline(
    video_path: str = None,
    srt_path: str = None,
    model_path: str = "weights/base/best.pt",
    output_dir: str = "results",
    conf_threshold: float = 0.25,
    is_mock: bool = False
):
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    start_time = time.time()

    print("=" * 70)
    print("🚀 ROADGUARD AI ANALYSIS PIPELINE — KHỞI ĐỘNG")
    print("=" * 70)

    # ─── NẾU CHẠY CHẾ ĐỘ MOCK (Cho Backend ASP.NET Core kiểm thử) ───────────────
    if is_mock:
        print("ℹ️ Chế độ Mock Adapter: Đang sinh dữ liệu giả lập cho Backend...")
        adapter = MockAIAdapter()
        res = adapter.process_mock_job(processing_job_id="job-mock-test-001")
        out_file = output_path / "inspection_report.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2, ensure_ascii=False)
        print(f"✅ Đã tạo kết quả mock tại: {out_file}")
        print("=" * 70)
        return res

    if not video_path:
        raise ValueError("Vui lòng chỉ định đường dẫn video bằng --video <file.mp4> hoặc dùng cờ --mock")

    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file video: {video_path}")

    # ─── TẦNG 1: PARSE SRT & BÓC TÁCH KHUNG HÌNH ───────────────────────────────
    print("\n[TẦNG 1] Bóc tách viễn thám & Trích xuất khung hình...")
    telemetries = []
    if srt_path and Path(srt_path).exists():
        srt_parser = DJISRTParser()
        telemetries = srt_parser.parse_file(srt_path)
        print(f"   Đã đọc {len(telemetries)} mốc telemetry từ file SRT.")
    else:
        print("   ⚠️ Không có file SRT, sẽ sử dụng thông số độ cao mặc định 10m.")

    extractor = VideoFrameExtractor()
    frames_dir = output_path / "extracted_frames"
    frame_metas = extractor.extract_frames(video_path, frames_dir, telemetries)
    print(f"   Trích xuất thành công {len(frame_metas)} frames đạt chuẩn.")

    # ─── TẦNG 2 & 3: TILING & MÔ HÌNH NHẬN DIỆN AI ─────────────────────────────
    print(f"\n[TẦNG 2 & 3] Khởi chạy mô hình YOLO ({model_path})...")
    predictor = RoadDefectPredictor(model_path, conf_threshold=conf_threshold)
    estimator = MetricEstimator()
    tracker = SpatialTracker(max_distance_meters=2.0)

    all_raw_detections = []
    vis_dir = output_path / "visualized_frames"
    vis_dir.mkdir(parents=True, exist_ok=True)

    import cv2
    for meta in frame_metas:
        f_idx = meta["frame_index"]
        f_img_path = frames_dir / meta["filename"]
        img = cv2.imread(str(f_img_path))
        if img is None:
            continue

        # Cắt mảnh 640x640 và inference
        detections = predictor.predict_full_frame(img, use_tiling=True)

        # Lấy GSD của frame
        gps = meta.get("gps")
        gsd = gps["gsd_mm_per_px"] if gps and "gsd_mm_per_px" in gps else 1.43

        # ─── TẦNG 4: ĐO ĐẠC KÍCH THƯỚC VẬT LÝ & THEO DÕI ────────────────────────
        for det in detections:
            metrics = estimator.estimate_dimensions(det["box"], gsd, det.get("class_name", "pothole"))
            det.update(metrics)
            det["frame_index"] = f_idx
            det["defect_type_code"] = det.get("class_name", "pothole")

        # Cập nhật tracking
        tracked_dets = tracker.update(detections, meta)
        all_raw_detections.extend(tracked_dets)

        # Vẽ ảnh trực quan
        vis_path = vis_dir / f"vis_{meta['filename']}"
        predictor.visualize(img, tracked_dets, vis_path)

    # ─── TẦNG 5: ĐÓNG GÓI JSON BẤT BIẾN & GEOJSON ─────────────────────────────
    print("\n[TẦNG 5] Đóng gói báo cáo chuẩn AIDetection...")
    formatted_detections = []
    job_id = f"job-{int(time.time())}"

    for det in all_raw_detections:
        rec = AIDetectionPayloadFormatter.create_detection_record(
            processing_job_id=job_id,
            model_version_id=str(Path(model_path).name),
            defect_type_code=det.get("defect_type_code", "pothole"),
            confidence=det["confidence"],
            estimated_width_mm=det.get("estimated_width_mm", 0.0),
            estimated_length_m=det.get("estimated_length_m", 0.0),
            raw_box=det["box"],
            location_method="OBSERVED_FOOTPRINT"
        )
        formatted_detections.append(rec)

    duration = time.time() - start_time
    final_report = AIDetectionPayloadFormatter.format_job_response(
        processing_job_id=job_id,
        model_version_id=str(Path(model_path).name),
        detections=formatted_detections,
        execution_time_seconds=duration,
        status="COMPLETED"
    )

    report_file = output_path / "inspection_report.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(final_report, f, indent=2, ensure_ascii=False)

    print("=" * 70)
    print("🎉 HOÀN TẤT TOÀN BỘ PIPELINE PHÂN TÍCH!")
    print(f"⏱️ Tổng thời gian thực thi: {duration:.2f} giây")
    print(f"📊 Phát hiện              : {len(formatted_detections)} khuyết tật")
    print(f"📁 Báo cáo JSON           : {report_file}")
    print(f"🖼️ Ảnh trực quan          : {vis_dir}")
    print("=" * 70)
    return final_report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RoadGuard AI Pipeline")
    parser.add_argument("--video", type=str, default="", help="Đường dẫn file video .MP4")
    parser.add_argument("--srt", type=str, default="", help="Đường dẫn file telemetry .SRT")
    parser.add_argument("--model", type=str, default="weights/base/best.pt", help="Đường dẫn file model .pt")
    parser.add_argument("--output", type=str, default="results", help="Thư mục xuất kết quả")
    parser.add_argument("--conf", type=float, default=0.25, help="Ngưỡng confidence")
    parser.add_argument("--mock", action="store_true", help="Chạy chế độ giả lập Mock AI")
    args = parser.parse_args()

    run_pipeline(
        video_path=args.video,
        srt_path=args.srt,
        model_path=args.model,
        output_dir=args.output,
        conf_threshold=args.conf,
        is_mock=args.mock
    )
