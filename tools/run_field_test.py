"""
tools/run_field_test.py — Chạy Kiểm Thử Thực Địa Đầy Đủ (Field Test) Cho RoadGuard AI
====================================================================================
Mục tiêu:
1. Chạy full pipeline trên video drone đầy đủ (data/raw_videos/DJI_0059.MP4, ~120s, 3598 frames).
2. Tần suất 1 FPS (120 khung hình thực tế trải dài toàn bộ chuyến bay).
3. Thu thập đầy đủ số liệu đo lường:
   - Tổng thời gian, FPS trung bình toàn pipeline và từng stage.
   - Số detections ban đầu (Stage 02).
   - Số detections sau khi lọc Road Mask (Stage 03) và tỷ lệ % bị lọc bỏ.
   - Số detections sau Dedup (Stage 04).
   - Phân bố mức độ nghiêm trọng Severity (Stage 05).
   - Số detections sau thẩm định KTV tầng 2 (Stage 06).
   - Xuất Báo cáo JSON, GeoJSON và PDF (Stage 07).
4. Phân tích & trích xuất 3 Best Cases + 3 Worst / Challenging Cases kèm ảnh minh họa.
"""

import sys
import os
import time
import json
from pathlib import Path
import cv2
import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.append(str(WORKSPACE))

from src.utils.io import safe_imread, safe_imwrite
from src.pipeline.pipeline import LinearPipeline, load_pipeline_config
from src.ingestion.srt_parser import DJISRTParser


def run_field_test():
    video_path = WORKSPACE / "data" / "raw_videos" / "DJI_0059.MP4"
    if not video_path.exists():
        raise FileNotFoundError(f"Không tìm thấy video drone: {video_path}")

    out_dir = WORKSPACE / "outputs" / "reports" / "field_test_dji0059"
    out_dir.mkdir(parents=True, exist_ok=True)
    cases_dir = out_dir / "cases"
    cases_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 75)
    print("🚁 BẮT ĐẦU FIELD TEST THỰC ĐỊA TOÀN TUYẾN — ROADGUARD AI")
    print(f"📹 Video: {video_path} (Full Drone Flight)")
    print(f"📁 Thư mục kết quả: {out_dir}")
    print("=" * 75)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise IOError(f"Không mở được video: {video_path}")

    orig_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_vid_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    video_duration_s = total_vid_frames / orig_fps
    target_fps = 1
    frame_step = max(1, int(round(orig_fps / target_fps)))

    print(f"📊 Thông số video: {total_vid_frames} frames | FPS gốc: {orig_fps:.2f} | Thời lượng: {video_duration_s:.1f}s")
    print(f"🎯 Tần suất trích xuất: {target_fps} FPS (Bước nhảy: {frame_step} frames)")

    frames_data = []
    processed_count = 0
    t0_extract = time.time()

    for frame_idx in range(0, total_vid_frames, frame_step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret or frame is None:
            break

        processed_count += 1
        t_sec = round(frame_idx / orig_fps, 2)
        frames_data.append({
            "frame_index": processed_count,
            "raw_frame_idx": frame_idx,
            "timestamp_s": t_sec,
            "filename": f"frame_{processed_count:04d}_{t_sec}s.jpg",
            "image": frame,
            "gps": {}
        })

    cap.release()
    extract_time = time.time() - t0_extract
    print(f"✅ Đã trích xuất {len(frames_data)} khung hình trong {extract_time:.2f}s.")

    # Cấu hình Pipeline
    cfg = load_pipeline_config(WORKSPACE / "configs" / "pipeline.yaml")
    model_path = WORKSPACE / "weights" / "trained" / "roadguard_best_15k.pt"

    ctx = {
        "task_id": "field_test_dji0059",
        "video_path": str(video_path).replace("\\", "/"),
        "srt_path": None,
        "model_path": str(model_path).replace("\\", "/"),
        "conf_threshold": 0.25,
        "use_tiling": True,
        "output_dir": str(out_dir).replace("\\", "/"),
        "frames": frames_data,
        "telemetries": [],
        "config": cfg,
        "start_time": time.time()
    }

    pipeline = LinearPipeline(config_dict=cfg)

    # Chạy toàn bộ 7 stages qua LinearPipeline
    total_start = time.time()
    ctx = pipeline.run(ctx)
    total_pipeline_time = time.time() - total_start
    total_fps = len(frames_data) / max(0.01, total_pipeline_time)

    # Thu thập thời gian chi tiết từng stage
    stage_benchmarks = {}
    for s_name, _ in pipeline.stages:
        t_ms = ctx.get(f"timing_{s_name}_ms", 0.0)
        stage_benchmarks[s_name] = round(t_ms / 1000.0, 2)

    # Trích xuất thống kê định lượng
    raw_dets = ctx.get("raw_detections", [])
    filtered_dets = ctx.get("filtered_detections", [])
    deduped_dets = ctx.get("deduped_detections", [])
    inspected_dets = ctx.get("inspected_detections", [])
    final_report = ctx.get("final_report", {})

    total_raw = len(raw_dets)
    total_filtered = len(filtered_dets)
    mask_removed_count = total_raw - total_filtered
    mask_removed_pct = (mask_removed_count / max(1, total_raw)) * 100

    total_deduped = len(deduped_dets)
    dedup_merged_count = total_filtered - total_deduped

    total_inspected = len(inspected_dets)
    ktv_removed_count = total_deduped - total_inspected

    # Phân bố Severity
    sev_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    class_counts = {}
    for d in inspected_dets:
        sev = d.get("severity", "MEDIUM")
        sev_counts[sev] = sev_counts.get(sev, 0) + 1
        cname = d.get("class_name", "unknown")
        class_counts[cname] = class_counts.get(cname, 0) + 1

    print("=" * 75)
    print("📈 TỔNG KẾT KẾT QUẢ THỰC ĐỊA:")
    print(f"⏱️ Tổng thời gian pipeline: {total_pipeline_time:.2f}s ({total_fps:.2f} FPS trên CPU)")
    print(f"🔍 Detections ban đầu (Stage 02)        : {total_raw}")
    print(f"🛡️ Sau lọc Road Mask (Stage 03)        : {total_filtered} (Đã lọc bỏ {mask_removed_count} FP ~ {mask_removed_pct:.1f}%)")
    print(f"🎯 Sau Dedup liên khung (Stage 04)     : {total_deduped} (Gộp {dedup_merged_count} trùng lặp)")
    print(f"🔬 Sau thẩm định KTV (Stage 06)         : {total_inspected} (Lọc {ktv_removed_count} báo động giả)")
    print(f"📊 Phân bố Severity: {sev_counts}")
    print(f"🏷️ Phân bố Lớp     : {class_counts}")
    print("=" * 75)

    # Lựa chọn 3 Best Cases (Verified, Confidence cao, Bbox rõ ràng)
    sorted_verified = sorted(inspected_dets, key=lambda d: d.get("confidence", 0.0), reverse=True)
    best_cases = sorted_verified[:3]

    # Lựa chọn 3 Worst / Challenging Cases:
    # 1. Khuyết tật verified có confidence thấp nhất (vết nứt khó/mảnh)
    # 2. Khuyết tật bị Stage 03 lọc bỏ do rơi trên thảm cỏ (Edge FP)
    # 3. Khuyết tật bị Stage 06 KTV từ chối (bóng râm / bề mặt giả mạo)
    worst_cases = []

    if len(sorted_verified) > 3:
        hardest_verified = sorted_verified[-1]
        worst_cases.append({
            "type": "LOW_CONFIDENCE_VERIFIED",
            "title": "Vết nứt khó/mờ (Độ tin cậy thấp nhưng KTV xác nhận hợp lệ)",
            "det": hardest_verified
        })

    # Tìm case bị Stage 03 loại bỏ
    filtered_out_stage3 = [d for d in raw_dets if d not in filtered_dets]
    if filtered_out_stage3:
        # Chọn 1 case có confidence tương đối cao nhưng bị lọc vì ở ngoài đường
        filtered_out_stage3.sort(key=lambda d: d.get("confidence", 0.0), reverse=True)
        worst_cases.append({
            "type": "MASK_FILTERED_VEGETATION",
            "title": "Báo động giả ngoại cảnh (Bị Road Mask chặn thành công)",
            "det": filtered_out_stage3[0]
        })

    # Tìm case bị Stage 06 loại bỏ
    filtered_out_stage6 = [d for d in deduped_dets if d not in inspected_dets]
    if filtered_out_stage6:
        worst_cases.append({
            "type": "KTV_FILTERED_HARD_NEGATIVE",
            "title": "Nhiễu kết cấu/bóng râm (Bị KTV tầng 2 sàng lọc)",
            "det": filtered_out_stage6[0]
        })
    elif len(sorted_verified) > 4:
        # Nếu không có case bị loại, lấy tiếp case độ tin cậy thấp thứ 2
        worst_cases.append({
            "type": "LOW_CONTRAST_DEFECT",
            "title": "Khuyết tật độ tương phản thấp",
            "det": sorted_verified[-2]
        })

    # Xuất ảnh minh họa cho 3 Best Cases & 3 Worst Cases
    # Map frame_index -> frame image
    frame_map = {f["frame_index"]: f["image"] for f in frames_data}

    saved_best_cases = []
    for idx, c in enumerate(best_cases, 1):
        f_idx = c.get("frame_index", 1)
        orig_img = frame_map.get(f_idx)
        if orig_img is None:
            continue
        box = c.get("box", [0, 0, 50, 50])
        x1, y1, x2, y2 = [int(v) for v in box]
        H, W = orig_img.shape[:2]
        # Crop có padding
        pad = 40
        cx1, cy1 = max(0, x1 - pad), max(0, y1 - pad)
        cx2, cy2 = min(W, x2 + pad), min(H, y2 + pad)
        crop = orig_img[cy1:cy2, cx1:cx2].copy()

        # Vẽ bbox trên crop
        bx1, by1 = x1 - cx1, y1 - cy1
        bx2, by2 = x2 - cx1, y2 - cy1
        cv2.rectangle(crop, (bx1, by1), (bx2, by2), (0, 165, 255), 2)
        label = f"{c.get('class_name')} {c.get('confidence', 0):.2f} [{c.get('severity')}]"
        cv2.putText(crop, label, (bx1, max(15, by1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 165, 255), 1)

        fname = f"best_case_{idx}_frame_{f_idx:04d}_{c.get('class_name')}.jpg"
        fpath = cases_dir / fname
        safe_imwrite(fpath, crop)

        saved_best_cases.append({
            "rank": idx,
            "defect_id": c.get("id"),
            "frame_index": f_idx,
            "timestamp_s": c.get("timestamp_s"),
            "class_name": c.get("class_name"),
            "confidence": round(float(c.get("confidence", 0)), 3),
            "severity": c.get("severity"),
            "estimated_width_mm": round(float(c.get("estimated_width_mm", 0)), 1),
            "estimated_length_m": round(float(c.get("estimated_length_m", 0)), 2),
            "image_file": str(fpath.relative_to(WORKSPACE)).replace("\\", "/")
        })

    saved_worst_cases = []
    for idx, w in enumerate(worst_cases, 1):
        c = w["det"]
        f_idx = c.get("frame_index", 1)
        orig_img = frame_map.get(f_idx)
        if orig_img is None:
            continue
        box = c.get("box", [0, 0, 50, 50])
        x1, y1, x2, y2 = [int(v) for v in box]
        H, W = orig_img.shape[:2]
        pad = 40
        cx1, cy1 = max(0, x1 - pad), max(0, y1 - pad)
        cx2, cy2 = min(W, x2 + pad), min(H, y2 + pad)
        crop = orig_img[cy1:cy2, cx1:cx2].copy()

        bx1, by1 = x1 - cx1, y1 - cy1
        bx2, by2 = x2 - cx1, y2 - cy1
        cv2.rectangle(crop, (bx1, by1), (bx2, by2), (0, 0, 255), 2)
        label = f"{w['type']} {c.get('confidence', 0):.2f}"
        cv2.putText(crop, label, (bx1, max(15, by1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)

        fname = f"worst_case_{idx}_frame_{f_idx:04d}_{w['type']}.jpg"
        fpath = cases_dir / fname
        safe_imwrite(fpath, crop)

        saved_worst_cases.append({
            "rank": idx,
            "type": w["type"],
            "title": w["title"],
            "frame_index": f_idx,
            "timestamp_s": c.get("timestamp_s"),
            "class_name": c.get("class_name"),
            "confidence": round(float(c.get("confidence", 0)), 3),
            "reasoning": c.get("reasoning", "Lọc tự động bởi pipeline"),
            "image_file": str(fpath.relative_to(WORKSPACE)).replace("\\", "/")
        })

    # Lưu metrics file
    metrics_summary = {
        "video_path": str(video_path).replace("\\", "/"),
        "total_video_frames": total_vid_frames,
        "video_duration_seconds": round(video_duration_s, 2),
        "sampled_frames": len(frames_data),
        "sampling_fps": target_fps,
        "total_pipeline_time_seconds": round(total_pipeline_time, 2),
        "fps_cpu": round(total_fps, 2),
        "stage_benchmarks": stage_benchmarks,
        "counts": {
            "stage_02_raw_detections": total_raw,
            "stage_03_filtered_detections": total_filtered,
            "stage_03_mask_removed_fp": mask_removed_count,
            "stage_03_mask_removed_pct": round(mask_removed_pct, 2),
            "stage_04_deduped_detections": total_deduped,
            "stage_04_duplicates_merged": dedup_merged_count,
            "stage_06_inspected_detections": total_inspected,
            "stage_06_ktv_removed_fp": ktv_removed_count
        },
        "severity_distribution": sev_counts,
        "class_distribution": class_counts,
        "best_cases": saved_best_cases,
        "worst_cases": saved_worst_cases,
        "report_json": str((out_dir / "inspection_report.json").relative_to(WORKSPACE)).replace("\\", "/"),
        "report_pdf": str((out_dir / "inspection_report.pdf").relative_to(WORKSPACE)).replace("\\", "/")
    }

    metrics_file = out_dir / "field_test_metrics.json"
    with open(metrics_file, "w", encoding="utf-8") as f:
        json.dump(metrics_summary, f, ensure_ascii=False, indent=2)

    print(f"✅ Đã ghi toàn bộ số liệu vào: {metrics_file}")
    print("=" * 75)
    return metrics_summary


if __name__ == "__main__":
    run_field_test()
