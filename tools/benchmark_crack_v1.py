"""
tools/benchmark_crack_v1.py
Đo lường toàn diện hiệu năng của mô hình roadguard_crack_yolo11n_v1.pt trên 265 ảnh Test
"""

import sys
import time
from pathlib import Path

# Cấu hình UTF-8 cho Windows terminal
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from ultralytics import YOLO

model_path = Path("weights/trained/roadguard_crack_yolo11n_v1.pt")
yaml_path = Path("data/road_crack_test_eval/test_eval.yaml")

if not model_path.exists():
    print(f"❌ Không tìm thấy model tại {model_path}")
    sys.exit(1)

model = YOLO(str(model_path))

print("=" * 65)
print("🚀 BẮT ĐẦU BENCHMARK ROADGUARD_CRACK_YOLO11N_V1 TRÊN 265 ẢNH TEST...")
print("=" * 65)

t0 = time.time()
metrics = model.val(
    data=str(yaml_path),
    split="test",
    imgsz=640,
    batch=16,
    plots=True,
    project="results/benchmark_crack_v1",
    name="test_eval"
)
total_time = time.time() - t0

mp = metrics.box.mp * 100
mr = metrics.box.mr * 100
map50 = metrics.box.map50 * 100
map50_95 = metrics.box.map * 100
infer_speed = metrics.speed.get("inference", 0.0)
pre_speed = metrics.speed.get("preprocess", 0.0)
post_speed = metrics.speed.get("postprocess", 0.0)
fps = 1000.0 / infer_speed if infer_speed > 0 else 0.0

print("=" * 65)
print("🏆 KẾT QUẢ ĐO LƯỜNG HIỆU NĂNG MÔ HÌNH:")
print(f" - Model:                          {model_path.name}")
print(f" - Kích thước file:                {model_path.stat().st_size / (1024*1024):.2f} MB")
print(f" - Số lượng tham số:               {sum(p.numel() for p in model.model.parameters()):,} params")
print(f" - Lớp nhận diện:                  {model.names}")
print(f" - Precision (Độ chính xác):       {mp:.2f}%")
print(f" - Recall (Độ bao quát / nhạy):    {mr:.2f}%")
print(f" - mAP@50 (Chuẩn IoU 0.5):         {map50:.2f}%")
print(f" - mAP@50-95 (Tổng hợp đa ngưỡng): {map50_95:.2f}%")
print(f" - Tổng thời gian chạy 265 ảnh:    {total_time:.2f}s")
print(f" - Độ trễ Inference CPU:           {infer_speed:.2f} ms/ảnh (~{fps:.1f} FPS)")
print(f" - Độ trễ Preprocess/Postprocess:  Pre={pre_speed:.2f}ms, Post={post_speed:.2f}ms")
print("=" * 65)
