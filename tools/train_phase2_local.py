"""
tools/train_phase2_local.py — Script Chạy Huấn Luyện Lần 2 Trên Máy Local (Windows / GPU)
========================================================================================
Sử dụng:
    python tools/train_phase2_local.py
    python tools/train_phase2_local.py --epochs 35 --batch 16 --device 0
"""

import sys
import argparse
import shutil
import time
from pathlib import Path

# Cấu hình UTF-8 console Windows
sys.stdout.reconfigure(encoding='utf-8')

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser(description="Chạy huấn luyện lần 2 (Phase 2 Upgrade) mô hình RoadGuard AI")
    parser.add_argument(
        "--weights", type=str,
        default=str(WORKSPACE_ROOT / "weights/trained/roadguard_crack_yolo11n_v1.pt"),
        help="Đường dẫn file trọng số v1 hiện tại"
    )
    parser.add_argument(
        "--data", type=str,
        default=str(WORKSPACE_ROOT / "data/unified_road_dataset_15k/data_phase2.yaml"),
        help="Đường dẫn file data_phase2.yaml"
    )
    parser.add_argument("--epochs", type=int, default=35, help="Số epochs huấn luyện (30 - 40)")
    parser.add_argument("--batch", type=int, default=16, help="Kích thước batch (16 hoặc 8 nếu VRAM yếu)")
    parser.add_argument("--imgsz", type=int, default=640, help="Độ phân giải ảnh đầu vào")
    parser.add_argument("--freeze", type=int, default=10, help="Số layer đóng băng backbone (Mặc định: 10)")
    parser.add_argument("--device", type=str, default="0", help="Thiết bị: '0' (NVIDIA GPU) hoặc 'cpu'")

    args = parser.parse_args()

    print("=" * 80)
    print("🚀 ROADGUARD AI — KỊCH BẢN HUẤN LUYỆN LẦN 2 (PHASE 2 LOCAL)")
    print("=" * 80)
    print(f"• Trọng số gốc (V1):         {args.weights}")
    print(f"• Tập dữ liệu (15K):         {args.data}")
    print(f"• Số Epochs:                 {args.epochs}")
    print(f"• Batch size:                {args.batch}")
    print(f"• Đóng băng Backbone:        {args.freeze} layers (Bảo vệ đặc trưng vết nứt)")
    print("=" * 80)

    import torch
    from ultralytics import YOLO

    device = args.device
    if device == "0" and not torch.cuda.is_available():
        print("⚠️ Không tìm thấy GPU CUDA, chuyển sang thiết bị CPU (tốc độ sẽ chậm hơn).")
        device = "cpu"
    elif torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        print(f"✓ Đã phát hiện GPU: {gpu_name} ({vram_gb:.2f} GB VRAM)")

    weights_path = Path(args.weights)
    if not weights_path.exists():
        print(f"❌ LỖI: Không tìm thấy file trọng số gốc {weights_path}!")
        sys.exit(1)

    print("\n[BƯỚC 1/3] Đang nạp mô hình checkpoint v1...")
    model = YOLO(str(weights_path))
    print(f"✓ Classes hiện có trong model gốc: {model.names}")

    print("\n[BƯỚC 2/3] Bắt đầu quá trình Fine-tuning lần 2...")
    t0 = time.time()
    results = model.train(
        data=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=device,
        freeze=args.freeze,
        lr0=0.001,          # Learning Rate khởi điểm 0.001 (thấp hơn 10x so với train từ đầu)
        lrf=0.01,           # Cosine scheduler
        warmup_epochs=3,    # 3 epoch làm ấm gradient cho lớp mới
        box=7.5,
        cls=0.5,
        dfl=1.5,
        mosaic=0.5,
        close_mosaic=5,
        project=str(WORKSPACE_ROOT / "runs/phase2_train"),
        name="roadguard_yolo11n_v2",
        exist_ok=True,
        save=True,
        val=True,
        plots=True
    )
    total_time = (time.time() - t0) / 60
    print(f"\n✓ Huấn luyện hoàn thành trong {total_time:.1f} phút!")

    print("\n[BƯỚC 3/3] Xuất xưởng và đánh giá trọng số mới...")
    best_pt = WORKSPACE_ROOT / "runs/phase2_train/roadguard_yolo11n_v2/weights/best.pt"
    if best_pt.exists():
        target_pt = WORKSPACE_ROOT / "weights/trained/roadguard_v2_pothole_crack.pt"
        shutil.copy2(best_pt, target_pt)
        print(f"✓ Đã sao lưu mô hình xuất xưởng vào: {target_pt}")

        # Đánh giá trên tập test
        print("\n📊 Đang đánh giá trên tập Test độc lập (751 ảnh)...")
        v2_eval = YOLO(str(target_pt))
        metrics = v2_eval.val(data=args.data, split="test")
        print("=" * 80)
        print("🏆 BẢNG ĐIỂM ĐÁNH GIÁ MÔ HÌNH V2 XUẤT XƯỞNG:")
        print(f"• mAP@50 (Overall): {metrics.box.map50 * 100:.2f}%")
        print(f"• mAP@50-95:        {metrics.box.map * 100:.2f}%")
        print(f"• Precision:        {metrics.box.mp * 100:.2f}%")
        print(f"• Recall:           {metrics.box.mr * 100:.2f}%")
        print("=" * 80)

if __name__ == "__main__":
    main()
