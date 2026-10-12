"""
tools/train_upgrade_model.py — Kịch Bản Nâng Cấp Model roadguard_crack_yolo11n_v1.pt Thành 2-Class Unified
========================================================================================================
Mục tiêu:
  - Giữ nguyên tri thức nhận diện Vết Nứt (Crack) đã có từ roadguard_crack_yolo11n_v1.pt.
  - Mở rộng thêm năng lực nhận biết Ổ Gà (Pothole - nông/sâu) và khử Báo động giả (Hard Negatives/Bóng râm).
  - Sử dụng chiến thuật Transfer Learning / Fine-Tuning với Learning Rate thấp + Freeze Backbone.
"""

import sys
import argparse
from pathlib import Path

# Thiết lập mã hóa UTF-8 console Windows
sys.stdout.reconfigure(encoding='utf-8')

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser(description="Nâng cấp Fine-tune mô hình RoadGuard từ 1-Class sang 2-Class")
    parser.add_argument(
        "--weights", type=str,
        default=str(WORKSPACE_ROOT / "weights/trained/roadguard_crack_yolo11n_v1.pt"),
        help="Trọng số xuất phát (Mặc định: roadguard_crack_yolo11n_v1.pt)"
    )
    parser.add_argument(
        "--data", type=str,
        default=str(WORKSPACE_ROOT / "data/unified_road_dataset_15k/data.yaml"),
        help="File cấu hình dataset (data/unified_road_dataset_15k/data.yaml hoặc data/curated_export/...)"
    )
    parser.add_argument("--epochs", type=int, default=30, help="Số epochs fine-tuning (khuyên dùng 25 - 40)")
    parser.add_argument("--batch", type=int, default=16, help="Kích thước batch (16 cho Colab T4, 8 nếu VRAM yếu)")
    parser.add_argument("--imgsz", type=int, default=640, help="Kích thước ảnh đầu vào (640)")
    parser.add_argument("--freeze", type=int, default=10, help="Số layer đóng băng để tránh quên tri thức vết nứt")
    parser.add_argument("--device", type=str, default="0", help="Thiết bị GPU (0) hoặc CPU (cpu)")

    args = parser.parse_args()

    print("=" * 75)
    print("🚀 ROADGUARD AI — KỊCH BẢN NÂNG CẤP MÔ HÌNH V2 (POTHOLE + CRACK)")
    print("=" * 75)
    print(f"• Trọng số gốc:      {args.weights}")
    print(f"• Tập dữ liệu train: {args.data}")
    print(f"• Số Epochs:         {args.epochs}")
    print(f"• Batch size:        {args.batch}")
    print(f"• Freeze layers:     {args.freeze} (Bảo toàn đặc trưng vết nứt đã học)")
    print("-" * 75)

    from ultralytics import YOLO
    import torch

    device_str = args.device
    if device_str == "0" and not torch.cuda.is_available():
        print("⚠️ Không tìm thấy GPU CUDA, tự động chuyển về thiết bị CPU.")
        device_str = "cpu"

    print("1. Nạp trọng số mô hình hiện tại...")
    model = YOLO(args.weights)
    print(f"   ✓ Classes hiện tại của model: {model.names}")

    print("\n2. Bắt đầu quá trình Fine-tuning...")
    results = model.train(
        data=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        lr0=0.001,          # Learning rate khởi điểm thấp hơn scratch (0.01 -> 0.001)
        lrf=0.01,           # Cosine annealing LR decay
        freeze=args.freeze, # Đóng băng backbone
        warmup_epochs=2,
        device=device_str,
        project=str(WORKSPACE_ROOT / "runs/upgrade_v2"),
        name="roadguard_yolo11n_pothole_crack",
        exist_ok=True,
        save=True,
        val=True,
        plots=True
    )

    best_pt = WORKSPACE_ROOT / "runs/upgrade_v2/roadguard_yolo11n_pothole_crack/weights/best.pt"
    if best_pt.exists():
        dest_pt = WORKSPACE_ROOT / "weights/trained/roadguard_v2_pothole_crack.pt"
        import shutil
        shutil.copy2(best_pt, dest_pt)
        print("\n" + "=" * 75)
        print("🎉 NÂNG CẤP THÀNH CÔNG!")
        print(f"• File trọng số mới đã lưu tại: {dest_pt}")
        print("=" * 75)


if __name__ == "__main__":
    main()
