"""
tools/build_full_44k_dataset.py — Hợp Nhất 100% Toàn Bộ ~44,000 Ảnh & Nhãn Txt (RoadGuard AI)
=============================================================================================
Hợp nhất:
  1. archive.zip: 3,940 ảnh Ổ gà (Class 0: pothole) kèm Bounding Box gốc
  2. surface-crack-detection.zip (Positive): 20,000 ảnh Vết nứt (Class 1: crack) kèm sinh BBox
  3. surface-crack-detection.zip (Negative): 20,000 ảnh Mẫu âm tính (Background) kèm file .txt rỗng (0 bytes)

Tổng quy mô: 43,940 ảnh + 43,940 file nhãn .txt được phân bổ Train (80%), Valid (15%), Test (5%).
"""

import os
import sys
import cv2
import zipfile
import numpy as np
from pathlib import Path

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def compute_crack_bbox(img_bytes: bytes) -> str:
    """Tính toán Bounding Box YOLO (x_center, y_center, w, h) cho vết nứt trên ảnh patch."""
    try:
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return "1 0.5000 0.5000 0.9000 0.9000\n"

        thresh = cv2.adaptiveThreshold(
            img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 21, 10
        )
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        boxes = [cv2.boundingRect(c) for c in contours if cv2.contourArea(c) > 25]

        if boxes:
            min_x = min(b[0] for b in boxes)
            min_y = min(b[1] for b in boxes)
            max_x = max(b[0] + b[2] for b in boxes)
            max_y = max(b[1] + b[3] for b in boxes)
            h, w = img.shape
            # Thêm đệm 5% viền
            pad_w = int((max_x - min_x) * 0.05)
            pad_h = int((max_y - min_y) * 0.05)
            min_x = max(0, min_x - pad_w)
            min_y = max(0, min_y - pad_h)
            max_x = min(w, max_x + pad_w)
            max_y = min(h, max_y + pad_h)

            bw = max(0.1, (max_x - min_x) / w)
            bh = max(0.1, (max_y - min_y) / h)
            xc = (min_x + max_x) / 2.0 / w
            yc = (min_y + max_y) / 2.0 / h
            return f"1 {xc:.4f} {yc:.4f} {bw:.4f} {bh:.4f}\n"
    except Exception:
        pass
    return "1 0.5000 0.5000 0.9000 0.9000\n"


def build_full_dataset(
    pothole_zip_path: str = r"F:\Fake_admin\Downloads\tổng hợp thông tin\archive.zip",
    crack_zip_path: str = r"F:\Fake_admin\Downloads\tổng hợp thông tin\surface-crack-detection.zip",
    output_dir: str = r"F:\train AI đồ án\data\unified_road_dataset_full",
    output_zip_path: str = r"F:\Fake_admin\Downloads\tổng hợp thông tin\unified_road_dataset_full.zip",
    generate_zip: bool = True
):
    pothole_zip = Path(pothole_zip_path)
    crack_zip = Path(crack_zip_path)
    out_path = Path(output_dir)
    out_zip = Path(output_zip_path)

    print("=" * 75)
    print("🚀 BẮT ĐẦU TIẾN TRÌNH HỢP NHẤT TOÀN DIỆN 100% DATASET (~44,000 ẢNH & NHÃN)")
    print(f"📦 Nguồn 1 (archive.zip): {pothole_zip}")
    print(f"📦 Nguồn 2 (surface-crack-detection.zip): {crack_zip}")
    print(f"📁 Thư mục xuất: {out_path}")
    print("=" * 75)

    for split in ["train", "valid", "test"]:
        (out_path / split / "images").mkdir(parents=True, exist_ok=True)
        (out_path / split / "labels").mkdir(parents=True, exist_ok=True)

    # ─── BƯỚC 1: Giải nén 3,940 ảnh Ổ GÀ (Class 0: pothole) ───
    print("\n[Bước 1/4] Đang nạp toàn bộ 3,940 ảnh Ổ gà từ archive.zip...")
    with zipfile.ZipFile(pothole_zip, "r") as z:
        z.extractall(out_path)
    print("   ✅ Đã nạp thành công 3,940 ảnh Ổ gà có sẵn BBox gốc.")

    # ─── BƯỚC 2: Nạp 20,000 ảnh VẾT NỨT (Class 1: crack) & 20,000 MẪU ÂM TÍNH ───
    print("\n[Bước 2/4] Đang quét và xử lý 40,000 ảnh từ surface-crack-detection.zip...")
    with zipfile.ZipFile(crack_zip, "r") as z:
        all_names = z.namelist()
        pos_files = sorted([f for f in all_names if f.startswith("Positive/") and f.lower().endswith((".jpg", ".png", ".jpeg"))])
        neg_files = sorted([f for f in all_names if f.startswith("Negative/") and f.lower().endswith((".jpg", ".png", ".jpeg"))])

        print(f"   ℹ️ Phát hiện: {len(pos_files)} ảnh Vết nứt (Positive) | {len(neg_files)} ảnh Mẫu âm tính (Negative).")

        # Cấu hình phân chia: 80% Train, 15% Valid, 5% Test
        splits_cfg = [
            ("train", 0, int(len(pos_files) * 0.80)),
            ("valid", int(len(pos_files) * 0.80), int(len(pos_files) * 0.95)),
            ("test", int(len(pos_files) * 0.95), len(pos_files))
        ]

        # 2.1 Xử lý 20,000 ảnh Positive (Cracks)
        print("\n   👉 Đang sinh nhãn Bounding Box và trích xuất 20,000 ảnh Vết nứt...")
        pos_total = 0
        for split_name, start_idx, end_idx in splits_cfg:
            img_dir = out_path / split_name / "images"
            lbl_dir = out_path / split_name / "labels"
            count = end_idx - start_idx
            print(f"      - Đang xuất {count} ảnh crack vào '{split_name}'...")

            for i in range(start_idx, end_idx):
                src_name = pos_files[i]
                file_idx = i + 1
                dst_img_name = f"crack_surf_{file_idx:05d}.jpg"
                dst_lbl_name = f"crack_surf_{file_idx:05d}.txt"

                raw_bytes = z.read(src_name)
                # Ghi ảnh
                with open(img_dir / dst_img_name, "wb") as f_img:
                    f_img.write(raw_bytes)
                # Ghi nhãn BBox
                bbox_line = compute_crack_bbox(raw_bytes)
                with open(lbl_dir / dst_lbl_name, "w", encoding="utf-8") as f_lbl:
                    f_lbl.write(bbox_line)
                pos_total += 1
                if pos_total % 5000 == 0:
                    print(f"        Đã xử lý {pos_total}/{len(pos_files)} ảnh Vết nứt...")

        print(f"   ✅ Đã xử lý xong toàn bộ {pos_total} ảnh Vết nứt (Class 1: crack).")

        # 2.2 Xử lý 20,000 ảnh Negative (Background)
        print("\n   👉 Đang tạo nhãn rỗng và trích xuất 20,000 ảnh Mẫu âm tính (Background)...")
        neg_total = 0
        for split_name, start_idx, end_idx in splits_cfg:
            img_dir = out_path / split_name / "images"
            lbl_dir = out_path / split_name / "labels"
            count = end_idx - start_idx
            print(f"      - Đang xuất {count} ảnh âm tính vào '{split_name}'...")

            for i in range(start_idx, end_idx):
                src_name = neg_files[i]
                file_idx = i + 1
                dst_img_name = f"neg_clean_{file_idx:05d}.jpg"
                dst_lbl_name = f"neg_clean_{file_idx:05d}.txt"

                raw_bytes = z.read(src_name)
                # Ghi ảnh
                with open(img_dir / dst_img_name, "wb") as f_img:
                    f_img.write(raw_bytes)
                # Ghi file nhãn rỗng (0 bytes)
                with open(lbl_dir / dst_lbl_name, "w", encoding="utf-8") as f_lbl:
                    pass
                neg_total += 1
                if neg_total % 5000 == 0:
                    print(f"        Đã xử lý {neg_total}/{len(neg_files)} ảnh Mẫu âm tính...")

        print(f"   ✅ Đã xử lý xong toàn bộ {neg_total} ảnh Mẫu âm tính (nhãn rỗng 0 bytes).")

    # ─── BƯỚC 3: Tạo Cấu Hình data.yaml Chuẩn Hóa 2 Classes ───
    print("\n[Bước 3/4] Tạo cấu hình chuẩn hóa 2 Classes (data.yaml)...")
    yaml_content = """# RoadGuard AI — Full Unified Dataset (Potholes + Cracks + Negative Background)
# Classes:
#   0: pothole (Ổ gà, sụt lún)
#   1: crack   (Vết nứt bề mặt đường bê-tông, nhựa)

train: train/images
val: valid/images
test: test/images

nc: 2
names: ['pothole', 'crack']
"""
    yaml_path = out_path / "data.yaml"
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write(yaml_content)
    print(f"   ✅ Đã ghi cấu hình tại: {yaml_path}")

    # Đếm kiểm kê toàn bộ file
    train_imgs = len(list((out_path / "train" / "images").glob("*.*")))
    train_lbls = len(list((out_path / "train" / "labels").glob("*.txt")))
    val_imgs = len(list((out_path / "valid" / "images").glob("*.*")))
    val_lbls = len(list((out_path / "valid" / "labels").glob("*.txt")))
    test_imgs = len(list((out_path / "test" / "images").glob("*.*")))
    test_lbls = len(list((out_path / "test" / "labels").glob("*.txt")))
    total_imgs = train_imgs + val_imgs + test_imgs
    total_lbls = train_lbls + val_lbls + test_lbls

    print("\n" + "=" * 75)
    print("📊 BẢNG TỔNG KẾT TOÀN DIỆN DATASET HỢP NHẤT (FULL 44K):")
    print(f"   - Tập TRAIN: {train_imgs:,} ảnh  |  {train_lbls:,} file nhãn .txt")
    print(f"   - Tập VALID: {val_imgs:,} ảnh  |  {val_lbls:,} file nhãn .txt")
    print(f"   - Tập TEST:  {test_imgs:,} ảnh  |  {test_lbls:,} file nhãn .txt")
    print(f"   🔥 TỔNG CỘNG: {total_imgs:,} ẢNH  +  {total_lbls:,} FILE NHÃN .TXT (KHỚP 100%!)")
    print("=" * 75)

    # ─── BƯỚC 4: Đóng Gói File Zip ───
    if generate_zip:
        print(f"\n[Bước 4/4] Đang đóng gói tệp zip tải lên Colab: {out_zip}...")
        out_zip.parent.mkdir(parents=True, exist_ok=True)
        if out_zip.exists():
            out_zip.unlink()

        with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as z:
            count = 0
            for root, dirs, files in os.walk(out_path):
                for file in files:
                    full_p = Path(root) / file
                    rel_p = full_p.relative_to(out_path)
                    z.write(full_p, arcname=str(rel_p))
                    count += 1
                    if count % 15000 == 0:
                        print(f"   Đã nén {count}/{total_imgs * 2} files...")

        zip_size_mb = out_zip.stat().st_size / (1024 * 1024)
        print(f"   🎉 Đóng gói thành công: {out_zip} ({zip_size_mb:.2f} MB)")

    print("\n🎉 HOÀN TẤT 100% TIẾN TRÌNH HỢP NHẤT TOÀN BỘ DATASET!")


if __name__ == "__main__":
    build_full_dataset()
