"""
src/pipeline/stages/07_report.py — Giai đoạn 7: Đóng Gói Báo Cáo JSON, GeoJSON & Bằng Chứng Trực Quan
===================================================================================================
Nhiệm vụ:
  - Lưu ảnh cắt cận cảnh (crops) từng khuyết tật phục vụ thẩm định.
  - Vẽ Bounding Box trực quan hóa lên khung hình (annotated frames).
  - Đóng gói báo cáo inspection_report.json chuẩn hóa theo AIDetectionPayloadFormatter.
  - Xuất tệp inspection_layer.geojson phục vụ số hóa bản đồ GIS / Leaflet.
  - Giữ đầy đủ cấu trúc dữ liệu tương thích 100% cho Web UI Test Bench.

Interface:
  def run(ctx: dict) -> dict
"""

import time
import json
from pathlib import Path
from typing import Dict, Any, List
import cv2
import numpy as np
from src.contracts.aidetection_schema import AIDetectionPayloadFormatter
from src.utils.io import safe_imwrite


def run(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Thực thi Stage 07: Report.
    """
    cfg = ctx.get("config", {}).get("stages", {}).get("07_report", {})
    if not cfg.get("enabled", True):
        return ctx

    task_id = ctx.get("task_id", f"task_{int(time.time())}")
    output_dir = Path(ctx.get("output_dir") or f"outputs/reports/{task_id}")
    output_dir.mkdir(parents=True, exist_ok=True)

    crops_dir = output_dir / "crops"
    frames_dir = output_dir / "frames"
    crops_dir.mkdir(parents=True, exist_ok=True)
    frames_dir.mkdir(parents=True, exist_ok=True)

    items = ctx.get("inspected_detections", [])
    model_name = ctx.get("model_name") or Path(ctx.get("model_path", "roadguard_model")).name
    save_crops = bool(cfg.get("save_crops", True))
    save_frames = bool(cfg.get("save_annotated_frames", True))

    formatted_detections: List[Dict[str, Any]] = []
    crops_list: List[Dict[str, Any]] = []
    all_defects: List[Dict[str, Any]] = []

    pothole_count = 0
    crack_count = 0

    # 1. Lưu ảnh Crop bằng chứng & chuẩn hóa detections
    for idx, det in enumerate(items, 1):
        crop_img = det.get("crop_image")
        cls_name = det.get("class_name", "defect")
        cls_vn = "Ổ gà" if "pothole" in cls_name else "Vết nứt"
        if "pothole" in cls_name:
            pothole_count += 1
        else:
            crack_count += 1

        crop_filename = f"crop_{idx:04d}_{cls_name}.jpg"
        crop_dest = crops_dir / crop_filename

        if save_crops and crop_img is not None and isinstance(crop_img, np.ndarray) and crop_img.size > 0:
            safe_imwrite(crop_dest, crop_img)
            crop_path_str = str(crop_dest).replace("\\", "/")
            crop_url = f"/static_results/{task_id}/crops/{crop_filename}"
        else:
            crop_path_str = ""
            crop_url = ""

        det["crop_path"] = crop_path_str
        det["crop_url"] = crop_url

        crop_info = {
            "url": crop_url,
            "filename": crop_filename,
            "class_name": cls_name,
            "class_vn": cls_vn,
            "fine_tag": det.get("fine_tag", cls_vn),
            "confidence": det.get("confidence", 0.0),
            "timestamp_s": det.get("timestamp_s", 0.0),
            "box": det.get("box", [0, 0, 0, 0]),
            "severity": det.get("severity", "MEDIUM")
        }
        crops_list.append(crop_info)

        defect_record = {
            "id": det.get("id", f"det_{idx:04d}"),
            "frame_index": det.get("frame_index", 0),
            "timestamp_s": det.get("timestamp_s", 0.0),
            "class_name": cls_name,
            "class_vn": cls_vn,
            "fine_tag": det.get("fine_tag", cls_vn),
            "confidence": det.get("confidence", 0.0),
            "box": det.get("box", [0, 0, 0, 0]),
            "crop_url": crop_url,
            "severity": det.get("severity", "MEDIUM"),
            "ground_latitude": det.get("ground_latitude", 0.0),
            "ground_longitude": det.get("ground_longitude", 0.0)
        }
        all_defects.append(defect_record)

        raw_box = det.get("box", [0, 0, 0, 0])
        rec = AIDetectionPayloadFormatter.create_detection_record(
            processing_job_id=task_id,
            model_version_id=model_name,
            defect_type_code=cls_name,
            confidence=det.get("confidence", 0.0),
            estimated_width_mm=det.get("estimated_width_mm", 0.0),
            estimated_length_m=det.get("estimated_length_m", 0.0),
            raw_box=raw_box,
            location_method=det.get("location_method", "OBSERVED_FOOTPRINT"),
            defect_lat=det.get("ground_latitude") or None,
            defect_lon=det.get("ground_longitude") or None,
            target_band=det.get("target_band", "SURFACE"),
            crop_uri=crop_url
        )
        rec["severity"] = det.get("severity", "MEDIUM")
        rec["fine_tag"] = det.get("fine_tag", cls_vn)
        rec["structural_risk"] = det.get("structural_risk", "")
        rec["recommendation"] = det.get("recommendation", "")
        rec["crop_url"] = crop_url
        formatted_detections.append(rec)

    # 2. Vẽ Annotated Frames
    detected_frames: List[Dict[str, Any]] = []
    predictor = ctx.get("predictor")

    for f_info in ctx.get("frames", []):
        f_idx = f_info.get("frame_index", 0)
        t_sec = f_info.get("timestamp_s", 0.0)
        frame_mat = f_info.get("image")
        f_dets = [d for d in items if d.get("frame_index") == f_idx]

        frame_filename = f"frame_{f_idx:04d}_{t_sec}s.jpg"
        if save_frames and frame_mat is not None and predictor is not None:
            ann_frame = predictor.visualize(frame_mat.copy(), f_dets)
            safe_imwrite(frames_dir / frame_filename, ann_frame)

        if len(f_dets) > 0:
            detected_frames.append({
                "frame_index": f_idx,
                "timestamp_s": t_sec,
                "annotated_url": f"/static_results/{task_id}/frames/{frame_filename}",
                "defects_count": len(f_dets),
                "pothole_count": sum(1 for d in f_dets if "pothole" in d.get("class_name", "")),
                "crack_count": sum(1 for d in f_dets if "crack" in d.get("class_name", ""))
            })

    # 3. Xuất Inspection Report JSON
    start_time = ctx.get("start_time", time.time())
    duration_sec = round(time.time() - start_time, 2)
    processed_count = len(ctx.get("frames", []))
    fps_calc = round(processed_count / max(0.01, duration_sec), 2)

    final_report = AIDetectionPayloadFormatter.format_job_response(
        processing_job_id=task_id,
        model_version_id=model_name,
        detections=formatted_detections,
        execution_time_seconds=duration_sec,
        status="COMPLETED"
    )
    final_report["task_id"] = task_id
    final_report["video_path"] = ctx.get("video_path", "")
    final_report["model_path"] = str(ctx.get("model_path", model_name))
    final_report["summary"] = {
        "processed_frames": processed_count,
        "total_defects": len(formatted_detections),
        "pothole_count": pothole_count,
        "crack_count": crack_count,
        "critical_count": sum(1 for d in formatted_detections if d.get("severity") == "CRITICAL"),
        "fps": fps_calc,
        "total_time_seconds": duration_sec
    }
    final_report["frames"] = detected_frames
    final_report["crops"] = crops_list
    final_report["all_defects"] = all_defects

    report_json_path = output_dir / "inspection_report.json"
    with open(report_json_path, "w", encoding="utf-8") as jf:
        json.dump(final_report, jf, ensure_ascii=False, indent=2)

    # 4. Xuất GeoJSON
    if bool(cfg.get("save_inspection_geojson", True)):
        geojson_data = AIDetectionPayloadFormatter.format_geojson(formatted_detections)
        geojson_path = output_dir / "inspection_layer.geojson"
        with open(geojson_path, "w", encoding="utf-8") as gf:
            json.dump(geojson_data, gf, ensure_ascii=False, indent=2)

    # 5. Xuất Báo Cáo PDF & HTML (Design Tokens Thủy Mệnh)
    if bool(cfg.get("save_inspection_pdf", True)):
        try:
            from src.reporting.pdf_exporter import export_pdf_report
            pdf_path = output_dir / "inspection_report.pdf"
            export_pdf_report(final_report, pdf_path)
            ctx["report_pdf_path"] = str(pdf_path).replace("\\", "/")
        except Exception as pe:
            print(f"  [07_report] Cảnh báo không thể xuất file PDF: {pe}")

    ctx["final_report"] = final_report
    ctx["output_dir"] = str(output_dir).replace("\\", "/")
    ctx["report_json_path"] = str(report_json_path).replace("\\", "/")
    ctx["stage_07_completed"] = True
    return ctx
