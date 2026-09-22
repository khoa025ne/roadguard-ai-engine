"""
src/training/train_pothole.py — Huấn luyện mô hình Pothole riêng biệt từ base weights
=====================================================================================
Sử dụng weights/base/best.pt (YOLOv11n) để fine-tune trên data/pothole (3,940 ảnh).
"""

import shutil
import argparse
from pathlib import Path
from ultralytics import YOLO


def train_pothole_model(
    epochs: int = 30,
    batch: int = 16,
    imgsz: int = 640,
    device: str = ""
):
    """Huấn luyện mô hình pothole và xuất trọng số vào weights/trained/pothole_best.pt."""
    base_model = Path("weights/base/best.pt").resolve()
    config_yaml = Path("configs/pothole_dataset.yaml").resolve()
    output_dir = Path("weights/trained")
    output_dir.mkdir(parents=True, exist_ok=True)

    if not base_model.exists():
        raise FileNotFoundError(f"Không tìm thấy base weights tại {base_model}")
    if not config_yaml.exists():
        raise FileNotFoundError(f"Không tìm thấy file config tại {config_yaml}")

    print("=" * 60)
    print("🚀 BẮT ĐẦU HUẤN LUYỆN MODEL POTHOLE")
    print(f"📦 Base model : {base_model}")
    print(f"📄 Config     : {config_yaml}")
    print(f"⚙️ Epochs={epochs}, Batch={batch}, ImgSz={imgsz}, Device={device or 'auto'}")
    print("=" * 60)

    model = YOLO(str(base_model))
    results = model.train(
        data=str(config_yaml),
        epochs=epochs,
        batch=batch,
        imgsz=imgsz,
        device=device if device else None,
        project="runs/pothole",
        name="pothole_v1",
        exist_ok=True,
        save=True,
        plots=True,
        optimizer="AdamW",
        lr0=0.001,
        patience=15,
        workers=2
    )

    trained_best = Path("runs/pothole/pothole_v1/weights/best.pt")
    target_path = output_dir / "pothole_best.pt"

    if trained_best.exists():
        shutil.copy(str(trained_best), str(target_path))
        print("=" * 60)
        print(f"🎉 HUẤN LUYỆN THÀNH CÔNG!")
        print(f"✅ Model đã được xuất ra: {target_path}")
        print("=" * 60)
    else:
        print("⚠️ Không tìm thấy file checkpoint sau khi train.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train Pothole Model")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--device", type=str, default="")
    args = parser.parse_args()

    train_pothole_model(epochs=args.epochs, batch=args.batch, imgsz=args.imgsz, device=args.device)
