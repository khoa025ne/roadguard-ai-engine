"""
src/ingestion/raw_video_analyzer.py — Công Cụ Xử Lý & Phân Tích Dữ Liệu Video Thô Từ BE
======================================================================================
Nhận đầu vào từ Backend ASP.NET Core (Video .MP4 + Telemetry .SRT hoặc ProcessingInputManifest),
thực thi gác cổng chất lượng (Quality Gate), cắt mảnh không gian, đo đạc vật lý 2D,
theo dõi khử trùng lặp và xuất xưởng bộ sản phẩm:
  1. inspection_report.json   (Khớp 100% Data Dictionary bảng AIDetection)
  2. inspection_layer.geojson (Dành cho bản đồ số hóa Leaflet.js / GIS)
  3. quality_report.json      (Báo cáo chất lượng đầu vào cho PM / QC)
  4. crops/                   (Ảnh chụp cận cảnh từng khuyết tật phục vụ nghiệm thu)
"""

import os
import cv2
import time
import json
import math
import uuid
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from .srt_parser import DJISRTParser, FrameTelemetry
from .video_extractor import VideoFrameExtractor
from ..inference.predictor import RoadDefectPredictor
from ..measurement.metric_estimator import MetricEstimator
from ..measurement.spatial_tracker import SpatialTracker
from ..contracts.aidetection_schema import AIDetectionPayloadFormatter


class RawVideoAnalyzer:
    """Công cụ lõi xử lý và phân tích video thô cho dịch vụ AI RoadGuard."""

    def __init__(
        self,
        model_path: str = "weights/base/best.pt",
        conf_threshold: float = 0.25,
        tile_size: int = 640,
        tile_overlap: float = 0.20
    ):
        self.model_path = Path(model_path)
        self.conf_threshold = conf_threshold
        self.tile_size = tile_size
        self.tile_overlap = tile_overlap

        # Khởi tạo các module nghiệp vụ
        self.srt_parser = DJISRTParser()
        self.video_extractor = VideoFrameExtractor()
        self.metric_estimator = MetricEstimator()
        self.spatial_tracker = SpatialTracker(max_distance_meters=2.0)
        self.predictor = None  # Lazy loading khi bắt đầu phân tích

    def _ensure_predictor(self):
        """Khởi tạo mô hình nhận diện khi cần thiết."""
        if self.predictor is None:
            if not self.model_path.exists():
                raise FileNotFoundError(f"Không tìm thấy file trọng số mô hình: {self.model_path}")
            self.predictor = RoadDefectPredictor(
                model_path=str(self.model_path),
                conf_threshold=self.conf_threshold
            )

    # ─── 1. KIỂM ĐỊNH CHẤT LƯỢNG ĐẦU VÀO (QUALITY GATE - KS08) ───────────────────
    def run_quality_gate(
        self,
        video_path: Path,
        telemetries: List[FrameTelemetry]
    ) -> Dict[str, Any]:
        """
        Kiểm tra độ toàn vẹn, độ rõ nét và an toàn viễn thám của dữ liệu thô.
        Phát hiện cảnh báo hoặc lỗi dữ liệu (DATA_FAILURE) để Backend yêu cầu bay lại.
        """
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return {
                "status": "DATA_FAILURE",
                "reason": f"Không thể giải mã luồng video: {video_path.name}",
                "can_proceed": False
            }

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration_sec = total_frames / fps

        # Lấy mẫu kiểm tra nhanh 30 khung hình trải đều
        sample_indices = np.linspace(0, total_frames - 1, min(30, total_frames), dtype=int)
        blur_scores = []
        brightness_scores = []

        for idx in sample_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
            ret, frame = cap.read()
            if not ret or frame is None:
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            blur_scores.append(float(cv2.Laplacian(gray, cv2.CV_64F).var()))
            brightness_scores.append(float(np.mean(gray)))

        cap.release()

        avg_blur = np.mean(blur_scores) if blur_scores else 0.0
        blurry_ratio = sum(1 for s in blur_scores if s < 100.0) / max(1, len(blur_scores))
        avg_brightness = np.mean(brightness_scores) if brightness_scores else 0.0

        # Kiểm tra độ cao bay từ Telemetry
        altitudes = [t.rel_alt_m for t in telemetries] if telemetries else [10.0]
        avg_altitude = np.mean(altitudes)
        max_altitude = np.max(altitudes)
        has_high_altitude_warning = max_altitude > 20.0

        # Đánh giá trạng thái
        warnings = []
        status = "PASSED"
        can_proceed = True

        if blurry_ratio > 0.35:
            status = "DATA_FAILURE"
            warnings.append(f"Tỷ lệ khung hình mờ nhòe quá cao ({blurry_ratio * 100:.1f}% > 35%). Cần bay lại khi trời lặng gió.")
            can_proceed = False

        if avg_brightness < 40.0:
            status = "DATA_FAILURE"
            warnings.append(f"Video quá tối (độ sáng trung bình {avg_brightness:.1f} < 40). Thiếu ánh sáng khảo sát.")
            can_proceed = False

        if has_high_altitude_warning:
            warnings.append(f"Độ cao bay tối đa {max_altitude:.1f}m vượt ngưỡng khuyến nghị 20m. Vết nứt mảnh (<5mm) có thể bị bỏ sót.")

        if not telemetries:
            warnings.append("Không có dữ liệu telemetry SRT. Hệ thống sẽ sử dụng độ cao giả định 10.0m và vị trí GPS null.")

        return {
            "status": status,
            "can_proceed": can_proceed,
            "video_metadata": {
                "filename": video_path.name,
                "resolution": f"{width}x{height}",
                "fps": round(fps, 2),
                "duration_seconds": round(duration_sec, 2),
                "total_frames": total_frames
            },
            "quality_metrics": {
                "average_blur_score": round(avg_blur, 2),
                "blurry_frames_ratio": round(blurry_ratio, 3),
                "average_brightness": round(avg_brightness, 1),
                "average_altitude_m": round(avg_altitude, 2),
                "max_altitude_m": round(max_altitude, 2)
            },
            "warnings": warnings
        }

    # ─── 2. TÍNH TOÁN TỌA ĐỘ ĐỊA LÝ MẶT ĐẤT (GEOREFERENCING) ────────────────────
    @staticmethod
    def calculate_defect_ground_coords(
        drone_lat: float,
        drone_lon: float,
        altitude_m: float,
        gimbal_pitch_deg: float,
        pixel_x: float,
        pixel_y: float,
        image_w: int = 2720,
        image_h: int = 1530,
        focal_mm: float = 4.26,
        sensor_w_mm: float = 6.17
    ) -> Tuple[float, float, str]:
        """
        Tính toán tọa độ địa lý mặt đất (WGS84) của khuyết tật từ góc nghiêng Gimbal và BBox.
        """
        if drone_lat == 0.0 and drone_lon == 0.0:
            return 0.0, 0.0, "UNKNOWN"

        # Nếu gimbal vuông góc thẳng đứng xuống đất (-90 độ hoặc gần -90)
        # Độ lệch tâm tính từ tâm khung hình
        cx = image_w / 2.0
        cy = image_h / 2.0
        dx_px = pixel_x - cx
        dy_px = pixel_y - cy

        gsd_m = (altitude_m * sensor_w_mm) / (focal_mm * image_w)
        offset_east_m = dx_px * gsd_m
        offset_north_m = -dy_px * gsd_m  # trục Y ảnh ngược hướng Bắc

        # 1 độ vĩ ~ 111,320m; 1 độ kinh ~ 111,320m * cos(lat)
        delta_lat = offset_north_m / 111320.0
        delta_lon = offset_east_m / (111320.0 * math.cos(math.radians(drone_lat)))

        ground_lat = round(drone_lat + delta_lat, 7)
        ground_lon = round(drone_lon + delta_lon, 7)

        return ground_lat, ground_lon, "OBSERVED_FOOTPRINT"

    # ─── 3. TIẾN TRÌNH XỬ LÝ & PHÂN TÍCH TOÀN DIỆN ──────────────────────────────
    def process_raw_video(
        self,
        video_path: str | Path,
        srt_path: Optional[str | Path] = None,
        output_dir: str | Path = "results",
        job_id: Optional[str] = None,
        sample_every_n_frames: Optional[int] = None,
        max_frames: Optional[int] = None,
        save_crops: bool = True,
        save_visualizations: bool = True
    ) -> Dict[str, Any]:
        """
        Quy trình xử lý hoàn chỉnh dữ liệu video thô từ Backend.
        """
        start_time = time.time()
        job_id = job_id or f"job-{uuid.uuid4().hex[:12]}"
        video_path = Path(video_path).resolve()
        output_path = Path(output_dir).resolve()
        output_path.mkdir(parents=True, exist_ok=True)

        crops_dir = output_path / "crops"
        vis_dir = output_path / "visualizations"
        if save_crops:
            crops_dir.mkdir(parents=True, exist_ok=True)
        if save_visualizations:
            vis_dir.mkdir(parents=True, exist_ok=True)

        print("=" * 70)
        print(f"🎬 RAW VIDEO ANALYZER — PROCESSING JOB: {job_id}")
        print(f"📁 Video: {video_path}")
        print(f"📁 Output Directory: {output_path}")
        print("=" * 70)

        # Bước 1: Parse SRT
        telemetries = []
        if srt_path and Path(srt_path).exists():
            print("\n[Bước 1/5] Bóc tách viễn thám DJI SRT...")
            telemetries = self.srt_parser.parse_file(srt_path)
            print(f"   ✅ Đã bóc tách thành công {len(telemetries)} bản ghi viễn thám.")
        else:
            print("\n[Bước 1/5] ⚠️ Không có file SRT, bỏ qua đồng bộ viễn thám.")

        # Bước 2: Quality Gate Audit
        print("\n[Bước 2/5] Đánh giá chất lượng dữ liệu đầu vào (Quality Gate - KS08)...")
        quality_report = self.run_quality_gate(video_path, telemetries)
        quality_file = output_path / "quality_report.json"
        with open(quality_file, "w", encoding="utf-8") as f:
            json.dump(quality_report, f, indent=2, ensure_ascii=False)

        if not quality_report["can_proceed"]:
            print(f"❌ DỮ LIỆU KHÔNG ĐẠT TIÊU CHUẨN: {quality_report['status']}")
            for w in quality_report["warnings"]:
                print(f"   ⚠️ {w}")
            return {
                "processing_job_id": job_id,
                "status": quality_report["status"],
                "quality_report": quality_report,
                "detections": []
            }
        print(f"   ✅ Quality Gate: {quality_report['status']}")

        # Bước 3: Trích xuất khung hình với 2fps sampling & blur filter
        print("\n[Bước 3/5] Trích xuất khung hình và lọc rung mờ...")
        frames_dir = output_path / "extracted_frames"
        frame_metas = self.video_extractor.extract_frames(
            video_path=video_path,
            output_dir=frames_dir,
            telemetries=telemetries,
            sample_every_n_frames=sample_every_n_frames,
            max_frames=max_frames
        )
        print(f"   ✅ Đã trích xuất {len(frame_metas)} khung hình đạt độ sắc nét.")

        # Bước 4: Tiling & YOLO Inference & Metric Estimation
        print(f"\n[Bước 4/5] Chạy suy luận AI trên lưới Tile 640x640 ({self.model_path.name})...")
        self._ensure_predictor()

        all_detections_payload = []
        detection_counter = 0

        for meta in frame_metas:
            f_name = meta["filename"]
            f_img_path = frames_dir / f_name
            frame_img = cv2.imread(str(f_img_path))
            if frame_img is None:
                continue

            H, W = frame_img.shape[:2]
            # Cắt tile và nhận diện
            detections = self.predictor.predict_full_frame(frame_img, use_tiling=True)

            gps = meta.get("gps") or {}
            drone_lat = gps.get("latitude", 0.0)
            drone_lon = gps.get("longitude", 0.0)
            altitude = gps.get("rel_alt_m", 10.0)
            gimbal_pitch = gps.get("gimbal_pitch", -90.0)
            gsd = gps.get("gsd_mm_per_px") or self.srt_parser.calc_gsd(altitude)

            frame_raw_dets = []

            for det in detections:
                detection_counter += 1
                box = det["box"]  # [x1, y1, x2, y2]
                center_x = (box[0] + box[2]) / 2.0
                center_y = (box[1] + box[3]) / 2.0

                # Tính kích thước vật lý 2D
                metrics = self.metric_estimator.estimate_dimensions(
                    box=box,
                    gsd_mm_per_px=gsd,
                    defect_type_code=det.get("class_name", "pothole")
                )

                # Tính tọa độ địa lý mặt đất
                g_lat, g_lon, loc_method = self.calculate_defect_ground_coords(
                    drone_lat=drone_lat,
                    drone_lon=drone_lon,
                    altitude_m=altitude,
                    gimbal_pitch_deg=gimbal_pitch,
                    pixel_x=center_x,
                    pixel_y=center_y,
                    image_w=W,
                    image_h=H
                )

                # Lưu ảnh crop bằng chứng
                crop_rel_path = ""
                if save_crops:
                    pad = 30
                    cx1 = max(0, box[0] - pad)
                    cy1 = max(0, box[1] - pad)
                    cx2 = min(W, box[2] + pad)
                    cy2 = min(H, box[3] + pad)
                    crop_img = frame_img[cy1:cy2, cx1:cx2]
                    crop_filename = f"crop_{job_id}_{detection_counter:04d}.jpg"
                    crop_full_path = crops_dir / crop_filename
                    cv2.imwrite(str(crop_full_path), crop_img)
                    crop_rel_path = f"crops/{crop_filename}"

                # Format record AIDetection chuẩn hóa
                record = AIDetectionPayloadFormatter.create_detection_record(
                    processing_job_id=job_id,
                    model_version_id=str(self.model_path.name),
                    defect_type_code=det.get("class_name", "pothole"),
                    confidence=det["confidence"],
                    estimated_width_mm=metrics["estimated_width_mm"],
                    estimated_length_m=metrics["estimated_length_m"],
                    aircraft_lat=drone_lat if drone_lat != 0.0 else None,
                    aircraft_lon=drone_lon if drone_lon != 0.0 else None,
                    defect_lat=g_lat if g_lat != 0.0 else None,
                    defect_lon=g_lon if g_lon != 0.0 else None,
                    location_method=loc_method,
                    camera_pose={
                        "altitude_m": altitude,
                        "gimbal_pitch": gimbal_pitch,
                        "gsd_mm_per_px": gsd,
                        "frame_index": meta["frame_index"],
                        "timestamp_ms": meta["timestamp_ms"]
                    },
                    raw_box=box,
                    crop_uri=crop_rel_path
                )
                record["severity"] = metrics["severity"]
                all_detections_payload.append(record)

                frame_raw_dets.append({
                    **det,
                    "width_mm": metrics["estimated_width_mm"],
                    "defect_type_code": det.get("class_name", "pothole")
                })

            # Vẽ ảnh trực quan
            if save_visualizations and frame_raw_dets:
                vis_img = self.predictor.visualize(frame_img, frame_raw_dets)
                vis_file = vis_dir / f"vis_{f_name}"
                cv2.imwrite(str(vis_file), vis_img)

        # Bước 5: Đóng gói và xuất kết quả chuẩn hóa
        print("\n[Bước 5/5] Đóng gói báo cáo inspection_report.json và GeoJSON...")
        total_time = time.time() - start_time

        job_response = AIDetectionPayloadFormatter.format_job_response(
            processing_job_id=job_id,
            model_version_id=str(self.model_path.name),
            detections=all_detections_payload,
            execution_time_seconds=total_time,
            status="COMPLETED"
        )
        job_response["quality_gate"] = quality_report["status"]

        # Lưu JSON Report
        report_path = output_path / "inspection_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(job_response, f, indent=2, ensure_ascii=False)

        # Lưu GeoJSON cho Web Map
        geojson_data = AIDetectionPayloadFormatter.format_geojson(all_detections_payload)
        geojson_path = output_path / "inspection_layer.geojson"
        with open(geojson_path, "w", encoding="utf-8") as f:
            json.dump(geojson_data, f, indent=2, ensure_ascii=False)

        print("=" * 70)
        print("🎉 HOÀN THÀNH PHÂN TÍCH VIDEO THÀNH CÔNG!")
        print(f"⏱️ Tổng thời gian: {total_time:.2f} giây")
        print(f"📍 Tổng số phát hiện: {len(all_detections_payload)}")
        print(f"📄 Báo cáo CSDL: {report_path}")
        print(f"🗺️ Lớp GeoJSON: {geojson_path}")
        print(f"🔍 Báo cáo chất lượng: {quality_file}")
        print(f"🖼️ Bằng chứng crop: {crops_dir} ({len(os.listdir(crops_dir)) if crops_dir.exists() else 0} ảnh)")
        print("=" * 70)

        return job_response
