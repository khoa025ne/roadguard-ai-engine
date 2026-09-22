"""
src/training/train_crack.py — Huấn luyện mô hình 8 Classes khuyết tật cầu đường
=============================================================================
Cấu hình tối ưu cho góc nhìn từ trên cao của Flycam (Drone Nadir View).
"""

import shutil
import argparse
from pathlib import Path
from ultralytics import YOLO


def train_crack_8classes_model(
    config_path: str = "configs/crack_8classes.yaml",
    epochs: int = 100,
    batch: int = 16,
    imgsz: int = 640,
    device: str = ""
):
    """Huấn luyện mô hình 8 classes khuyết tật cầu đường."""
    base_model = Path("weights/base/best.pt").resolve()
    config_yaml = Path(config_path).resolve()
    output_dir = Path("weights/trained")
    output_dir.mkdir(parents=True, exist_ok=True)

    if not base_model.exists():
        raise FileNotFoundError(f"Không tìm thấy base weights tại {base_model}")
    if not config_yaml.exists():
        raise FileNotFoundError(f"Không tìm thấy file config tại {config_yaml}")

    print("=" * 60)
    print("🚀 BẮT ĐẦU HUẤN LUYỆN 8 CLASSES KHUYẾT TẬT ĐƯỜNG BỘ")
    print(f"📦 Base model : {base_model}")
    print(f"📄 Config     : {config_yaml}")
    print("=" * 60)

    model = YOLO(str(base_model))
    results = model.train(
        data=str(config_yaml),
        epochs=epochs,
        batch=batch,
        imgsz=imgsz,
        device=device if device else None,
        project="runs/crack_detection",
        name="crack_8classes_v1",
        exist_ok=True,
        save=True,
        plots=True,
        optimizer="AdamW",
        lr0=0.001,
        degrees=45.0,  # Xoay ngẫu nhiên cho drone view
        flipud=0.5,    # Lật dọc
        fliplr=0.5,    # Lật ngang
        scale=0.5,     # Co giãn mô phỏng độ cao bay
        hsv_v=0.5,     # Thích nghi độ sáng biến thiên
        patience=20,
        workers=2
    )

    trained_best = Path("runs/crack_detection/crack_8classes_v1/weights/best.pt")
    target_path = output_dir / "crack_8classes_best.pt"

    if trained_best.exists():
        shutil.copy(str(trained_best), str(target_path))
        print("=" * 60)
        print(f"🎉 HUẤN LUYỆN THÀNH CÔNG! Model lưu tại: {target_path}")
        print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train 8-Class Crack Model")
    parser.add_argument("--config", type=str, default="configs/crack_8classes.yaml")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--device", type=str, default="")
    args = parser.parse_args()

    train_crack_8classes_model(
        config_path=args.config,
        epochs=args.epochs,
        batch=args.batch,
        imgsz=args.imgsz,
        device=args.device
    )
