"""
tools/benchmark_road_seg_model.py — Đánh Giá Pretrained Road Segmentation Model
================================================================================
Kiểm thử mô hình pretrained yolo11m-road-seg trên 50 khung hình Flycam thực tế:
- Đo thời gian suy luận (Latency / FPS)
- Đo tỷ lệ nhận diện mặt đường (Road detection rate)
- Đo độ che phủ mặt đường (Road area ratio)
- Phân tích hiện tượng lẹm sang cỏ/cây/vỉa hè và hiện tượng thủng mask
- Xuất ảnh trực quan hóa overlay vào outputs/road_seg_eval_overlays/
"""

import sys
import time
import json
from pathlib import Path
import cv2
import numpy as np
from ultralytics import YOLO

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.append(str(WORKSPACE))
from src.utils.io import safe_imread, safe_imwrite

MODEL_PATH = WORKSPACE / "weights" / "pretrained" / "yolo11m-road-seg.pt"
FRAMES_DIR = WORKSPACE / "outputs" / "drone_benchmark_50_frames"
OVERLAY_DIR = WORKSPACE / "outputs" / "road_seg_eval_overlays"

OVERLAY_DIR.mkdir(parents=True, exist_ok=True)


def evaluate_model():
    print("=" * 75)
    print("🚀 BẮT ĐẦU ĐÁNH GIÁ MÔ HÌNH PRETRAINED YOLO11 ROAD SEGMENTATION")
    print(f"📦 Trọng số: {MODEL_PATH}")
    print(f"🖼️ Tập mẫu thử: 50 frames tại {FRAMES_DIR}")
    print(f"🎨 Thư mục lưu overlay: {OVERLAY_DIR}")
    print("=" * 75)

    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Không tìm thấy model tại {MODEL_PATH}")

    model = YOLO(str(MODEL_PATH))
    print(f"✓ Đã tải mô hình. Task: {model.task} | Classes: {model.names}")

    frame_files = sorted(list(FRAMES_DIR.glob("*.jpg")))
    if not frame_files:
        raise FileNotFoundError(f"Không tìm thấy frame nào trong {FRAMES_DIR}")

    results_summary = []
    total_time = 0.0
    detected_count = 0

    for idx, f_path in enumerate(frame_files, 1):
        img_bgr = safe_imread(f_path)
        if img_bgr is None:
            continue

        H, W = img_bgr.shape[:2]
        t0 = time.perf_counter()
        preds = model(img_bgr, conf=0.25, imgsz=640, verbose=False)
        dt_ms = (time.perf_counter() - t0) * 1000
        total_time += dt_ms

        r = preds[0]
        has_mask = r.masks is not None and len(r.masks) > 0

        road_mask_full = np.zeros((H, W), dtype=np.uint8)
        road_area_ratio = 0.0

        if has_mask:
            detected_count += 1
            # Gộp tất cả các polygon / mask của class 0 (road)
            for m_idx, cls_tensor in enumerate(r.boxes.cls):
                cls_id = int(cls_tensor.cpu().numpy())
                # Mask tensor từ ultralytics có kích thước tương ứng r.masks.data
                m_data = r.masks.data[m_idx].cpu().numpy()
                m_resized = cv2.resize(m_data, (W, H), interpolation=cv2.INTER_NEAREST)
                road_mask_full = np.maximum(road_mask_full, (m_resized > 0.5).astype(np.uint8) * 255)

            road_pixels = np.count_nonzero(road_mask_full)
            road_area_ratio = road_pixels / (H * W)

        # Tạo ảnh trực quan hóa Overlay theo Palette Thủy Mệnh (#0A2540 / #1E88C7)
        vis = img_bgr.copy()
        if has_mask and np.any(road_mask_full > 0):
            # Tạo overlay màu xanh dương đậm (B: 199, G: 136, R: 30)
            overlay = vis.copy()
            overlay[road_mask_full > 0] = [199, 136, 30]  # Accent #1E88C7
            cv2.addWeighted(overlay, 0.45, vis, 0.55, 0, vis)

            # Vẽ đường bao mép đường (contour biên) màu trắng bạc #AEB9C6
            contours, _ = cv2.findContours(road_mask_full, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(vis, contours, -1, (198, 185, 174), 2)

        # Ghi thông số lên góc ảnh
        status_txt = f"ROAD MASK: {'YES' if has_mask else 'NO'} | Area: {road_area_ratio*100:.1f}% | Latency: {dt_ms:.1f}ms"
        cv2.rectangle(vis, (10, 10), (700, 45), (10, 37, 6), -1)
        cv2.putText(vis, status_txt, (15, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        out_vis_path = OVERLAY_DIR / f"eval_{idx:02d}_{f_path.name}"
        safe_imwrite(out_vis_path, vis)

        results_summary.append({
            "index": idx,
            "filename": f_path.name,
            "detected": has_mask,
            "latency_ms": round(dt_ms, 2),
            "road_area_ratio": round(road_area_ratio, 4),
        })

        if idx % 10 == 0 or idx == len(frame_files):
            print(f"[{idx:02d}/50] {f_path.name}: Mask={'CÓ' if has_mask else 'KHÔNG'} | Diện tích đường={road_area_ratio*100:.1f}% | Thời gian={dt_ms:.1f}ms")

    mean_latency = total_time / len(frame_files)
    detection_rate = detected_count / len(frame_files) * 100
    mean_area = np.mean([r["road_area_ratio"] for r in results_summary]) * 100

    report = {
        "model": str(MODEL_PATH.name),
        "total_test_frames": len(frame_files),
        "detection_rate_pct": round(detection_rate, 2),
        "mean_latency_ms": round(mean_latency, 2),
        "fps_estimate": round(1000 / mean_latency, 1) if mean_latency > 0 else 0,
        "mean_road_area_pct": round(mean_area, 2),
        "details": results_summary
    }

    report_path = WORKSPACE / "outputs" / "road_seg_benchmark_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 75)
    print("📊 BẢNG TỔNG KẾT ĐÁNH GIÁ PRETRAINED ROAD SEGMENTATION:")
    print("=" * 75)
    print(f" - Tổng số khung hình kiểm thử: {len(frame_files)} frames")
    print(f" - Tỷ lệ phát hiện mặt đường:    {detection_rate:.1f}% ({detected_count}/{len(frame_files)} frames)")
    print(f" - Tốc độ suy luận trung bình:  {mean_latency:.1f} ms/frame (~{report['fps_estimate']} FPS)")
    print(f" - Diện tích lòng đường chiếm:  {mean_area:.1f}% diện tích khung hình")
    print(f" - Thư mục ảnh overlay:         {OVERLAY_DIR}")
    print(f" - Báo cáo JSON chi tiết:       {report_path}")
    print("=" * 75)
    return report


if __name__ == "__main__":
    evaluate_model()
