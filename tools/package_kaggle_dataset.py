"""
tools/package_kaggle_dataset.py — Đóng Gói Dữ Liệu và Trọng Số Cho Kaggle Dataset
================================================================================
Tập hợp toàn bộ data/merged/ (train/valid/test/data.yaml) và trọng số nền tảng
weights/trained/roadguard_best_15k.pt thành một gói dataset chuẩn cho Kaggle:
- Tạo thư mục outputs/kaggle_dataset/
- Sinh metadata chuẩn dataset-metadata.json (isPrivate: true)
- Nén thành outputs/roadguard_multiclass_dataset.zip
- Tự động gọi Kaggle CLI để đẩy lên nếu đã có xác thực (hoặc hướng dẫn đẩy qua Web).
"""

import os
import sys
import json
import shutil
import zipfile
import subprocess
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
MERGED_DIR = WORKSPACE_ROOT / "data" / "merged"
WEIGHT_FILE = WORKSPACE_ROOT / "weights" / "trained" / "roadguard_best_15k.pt"
OUTPUT_DIR = WORKSPACE_ROOT / "outputs" / "kaggle_dataset"
ZIP_OUTPUT = WORKSPACE_ROOT / "outputs" / "roadguard_multiclass_dataset.zip"


def create_metadata(dest_dir: Path, username: str = "roadguard-ai"):
    """Tạo dataset-metadata.json chuẩn Kaggle."""
    metadata = {
        "title": "RoadGuard Multiclass Road Defect Dataset",
        "id": f"{username}/roadguard-multiclass-dataset",
        "licenses": [{"name": "CC0-1.0"}],
        "isPrivate": True
    }
    meta_path = dest_dir / "dataset-metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    print(f"📄 Đã sinh metadata: {meta_path} (isPrivate=True)")


def package_dataset():
    print("=" * 75)
    print("🚀 BẮT ĐẦU ĐÓNG GÓI KAGGLE DATASET (ROADGUARD MULTICLASS V1)")
    print("=" * 75)

    if not MERGED_DIR.exists():
        raise FileNotFoundError(f"Không tìm thấy thư mục: {MERGED_DIR}")
    if not WEIGHT_FILE.exists():
        raise FileNotFoundError(f"Không tìm thấy trọng số: {WEIGHT_FILE}")

    # Đảm bảo thư mục output tồn tại
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ZIP_OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    # 1. Tạo metadata
    create_metadata(OUTPUT_DIR)

    # 2. Sao chép trọng số
    dest_weight = OUTPUT_DIR / "roadguard_best_15k.pt"
    print(f"\n📦 [1/3] Sao chép file trọng số: {WEIGHT_FILE.name}...")
    shutil.copy2(WEIGHT_FILE, dest_weight)
    print(f"   ✓ Đã sao chép sang: {dest_weight} ({dest_weight.stat().st_size / 1024**2:.2f} MB)")

    # 3. Sao chép data.yaml và cấu trúc train/valid/test
    print(f"\n📦 [2/3] Sao chép cấu trúc dataset từ {MERGED_DIR}...")
    dest_yaml = OUTPUT_DIR / "data.yaml"
    shutil.copy2(MERGED_DIR / "data.yaml", dest_yaml)

    for split in ["train", "valid", "test"]:
        src_split = MERGED_DIR / split
        dest_split = OUTPUT_DIR / split
        if src_split.exists():
            print(f"   • Đang sao chép phân tập '{split}'...")
            dest_split_img = dest_split / "images"
            dest_split_lbl = dest_split / "labels"
            dest_split_img.mkdir(parents=True, exist_ok=True)
            dest_split_lbl.mkdir(parents=True, exist_ok=True)

            # Sao chép images
            for img_f in (src_split / "images").glob("*.*"):
                shutil.copy2(img_f, dest_split_img / img_f.name)
            # Sao chép labels
            for lbl_f in (src_split / "labels").glob("*.txt"):
                shutil.copy2(lbl_f, dest_split_lbl / lbl_f.name)
            print(f"     ✓ Hoàn tất '{split}' ({len(list(dest_split_img.glob('*.*')))} ảnh, {len(list(dest_split_lbl.glob('*.txt')))} nhãn)")

    # 4. Nén zip toàn bộ
    print(f"\n📦 [3/3] Nén file zip: {ZIP_OUTPUT}...")
    with zipfile.ZipFile(ZIP_OUTPUT, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        # Ghi các file trong OUTPUT_DIR
        for root, _, files in os.walk(OUTPUT_DIR):
            for file in files:
                p = Path(root) / file
                rel_path = p.relative_to(OUTPUT_DIR)
                zf.write(p, arcname=str(rel_path))

    zip_size_mb = ZIP_OUTPUT.stat().st_size / (1024 ** 2)
    print(f"🎉 ĐÃ ĐÓNG GÓI THÀNH CÔNG: {ZIP_OUTPUT}")
    print(f"   - Dung lượng nén: {zip_size_mb:.2f} MB")
    print("=" * 75)

    # 5. Kiểm tra khả năng upload qua Kaggle CLI
    print("\n🔍 KIỂM TRA KẾT NỐI KAGGLE CLI:")
    try:
        check_res = subprocess.run(["kaggle", "datasets", "list", "--mine"], capture_output=True, text=True, timeout=10)
        if check_res.returncode == 0:
            print("✓ Kaggle API đã được xác thực! Đang tiến hành tạo Kaggle Dataset...")
            upload_cmd = ["kaggle", "datasets", "create", "-p", str(OUTPUT_DIR), "-r", "zip"]
            up_res = subprocess.run(upload_cmd, capture_output=True, text=True)
            print(up_res.stdout)
            if up_res.returncode != 0:
                print(f"⚠️ Ghi chú CLI: {up_res.stderr}")
        else:
            print("ℹ️ Kaggle API chưa có token xác thực trên máy.")
            print("👉 Bạn có thể tải file zip lên Kaggle bằng một trong 2 cách sau:")
            print("   1. Giao diện Web Kaggle (Khuyên dùng): Truy cập https://www.kaggle.com/datasets -> Nhấn 'New Dataset' -> Kéo thả file 'outputs/roadguard_multiclass_dataset.zip' -> Chọn chế độ 'Private'.")
            print("   2. Qua CLI: Chạy 'kaggle auth login' hoặc lưu token vào '~/.kaggle/kaggle.json' rồi chạy lại lệnh này.")
    except Exception as e:
        print(f"ℹ️ Không thể gọi tự động Kaggle CLI: {e}")


if __name__ == "__main__":
    package_dataset()
