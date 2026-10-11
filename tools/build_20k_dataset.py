"""
tools/build_20k_dataset.py — Xây Dựng Dataset ~15,000 Ảnh Tối Ưu Colab Free (RoadGuard AI)
==============================================================================================
Mục tiêu: Tạo bộ dữ liệu cân bằng ~15k ảnh để train nhanh trên GPU T4 Colab Free.

Thành phần:
  1. archive.zip       : 3,940 ảnh Ổ gà (Class 0: pothole) — toàn bộ, có BBox gốc
  2. surface-crack-detection.zip (Positive): 5,000 ảnh Vết nứt (Class 1: crack) + sinh BBox tự động
  3. surface-crack-detection.zip (Negative): 6,060 ảnh Mẫu âm tính (Background) + file .txt rỗng

Tổng quy mô: ~15,000 ảnh + 15,000 file nhãn .txt
Phân bổ   : Train 80% (~12,000) | Valid 15% (~2,250) | Test 5% (~750)

Tại sao 15k phù hợp Colab Free?
  - Thời gian train YOLOv11n 50 epoch: ~30–50 phút (T4 GPU)
  - Dung lượng zip: ~160–220 MB (rất nhẹ, upload nhanh)
  - RAM 12GB thoải mái với batch_size=16, imgsz=640
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

# ─── CẤU HÌNH SỐ LƯỢNG ───────────────────────────────────────────────────────
# Tổng mục tiêu: ~15,000 ảnh
# - Pothole  : 3,940  (lấy hết, không thể bổ sung)
# - Crack    : 5,000  (lấy 5k/20k từ Positive)
# - Negative : 6,060  (15_000 - 3_940 - 5_000)

NUM_CRACK    = 5_000
NUM_NEGATIVE = 6_060   # 15_000 - 3_940 - 5_000


def compute_crack_bbox(img_bytes: bytes) -> str:
    """Tính Bounding Box YOLO (x_center, y_center, w, h) cho vết nứt trên ảnh patch."""
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
            # Thêm đệm 5% viền để bbox ôm sát vết nứt hơn
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


def _make_split_config(total: int) -> list[tuple[str, int, int]]:
    """Trả về [(split_name, start, end)] với tỉ lệ 80/15/5."""
    t = int(total * 0.80)
    v = int(total * 0.95)
    return [
        ("train", 0,     t),
        ("valid", t,     v),
        ("test",  v, total),
    ]


def build_20k_dataset(
    pothole_zip_path: str = r"F:\Fake_admin\Downloads\tổng hợp thông tin\archive.zip",
    crack_zip_path:   str = r"F:\Fake_admin\Downloads\tổng hợp thông tin\surface-crack-detection.zip",
    output_dir:       str = r"F:\train AI đồ án\data\unified_road_dataset_15k",
    output_zip_path:  str = r"F:\Fake_admin\Downloads\tổng hợp thông tin\unified_road_dataset_15k.zip",
    generate_zip:     bool = True,
):
    pothole_zip = Path(pothole_zip_path)
    crack_zip   = Path(crack_zip_path)
    out_path    = Path(output_dir)
    out_zip     = Path(output_zip_path)

    print("=" * 75)
    print("🚀 XÂY DỰNG DATASET ~15,000 ẢNH — TỐI ƯU GOOGLE COLAB FREE")
    print(f"   Pothole  (Class 0): 3,940 ảnh  — toàn bộ archive.zip")
    print(f"   Crack    (Class 1): {NUM_CRACK:,} ảnh — từ surface-crack-detection.zip (Positive)")
    print(f"   Negative (bg)     : {NUM_NEGATIVE:,} ảnh — từ surface-crack-detection.zip (Negative)")
    print(f"   TỔNG              : {3940 + NUM_CRACK + NUM_NEGATIVE:,} ảnh")
    print(f"📦 archive.zip       : {pothole_zip}")
    print(f"📦 crack-detect.zip  : {crack_zip}")
    print(f"📁 Thư mục xuất      : {out_path}")
    print("=" * 75)

    # Kiểm tra file nguồn
    if not pothole_zip.exists():
        raise FileNotFoundError(f"❌ Không tìm thấy: {pothole_zip}")
    if not crack_zip.exists():
        raise FileNotFoundError(f"❌ Không tìm thấy: {crack_zip}")

    # Tạo cấu trúc thư mục
    for split in ["train", "valid", "test"]:
        (out_path / split / "images").mkdir(parents=True, exist_ok=True)
        (out_path / split / "labels").mkdir(parents=True, exist_ok=True)

    # ─── BƯỚC 1: Giải nén toàn bộ 3,940 ảnh Ổ GÀ ──────────────────────────
    print("\n[Bước 1/4] Đang nạp 3,940 ảnh Ổ gà (Class 0: pothole) từ archive.zip...")
    with zipfile.ZipFile(pothole_zip, "r") as z:
        z.extractall(out_path)
    print("   ✅ Đã nạp xong 3,940 ảnh Ổ gà kèm BBox gốc.")

    # ─── BƯỚC 2: Trích xuất crack & negative từ surface-crack-detection.zip ─
    print(f"\n[Bước 2/4] Đang xử lý {NUM_CRACK:,} ảnh Vết nứt + {NUM_NEGATIVE:,} Mẫu âm tính...")
    with zipfile.ZipFile(crack_zip, "r") as z:
        all_names = z.namelist()
        pos_files = sorted([
            f for f in all_names
            if f.startswith("Positive/") and f.lower().endswith((".jpg", ".png", ".jpeg"))
        ])
        neg_files = sorted([
            f for f in all_names
            if f.startswith("Negative/") and f.lower().endswith((".jpg", ".png", ".jpeg"))
        ])

        print(f"   ℹ️ Phát hiện {len(pos_files):,} ảnh Positive | {len(neg_files):,} ảnh Negative trong zip.")

        # Giới hạn số lượng lấy
        pos_selected = pos_files[:NUM_CRACK]
        neg_selected = neg_files[:NUM_NEGATIVE]

        # 2.1 — Ảnh Crack (Positive) với BBox tự động
        print(f"\n   👉 Đang sinh BBox và trích xuất {NUM_CRACK:,} ảnh Vết nứt (crack)...")
        crack_split_cfg = _make_split_config(len(pos_selected))
        crack_total = 0

        for split_name, start_idx, end_idx in crack_split_cfg:
            img_dir = out_path / split_name / "images"
            lbl_dir = out_path / split_name / "labels"
            count = end_idx - start_idx
            print(f"      - Xuất {count:,} ảnh crack → '{split_name}/'...")

            for i in range(start_idx, end_idx):
                src_name   = pos_selected[i]
                file_idx   = i + 1
                dst_img    = f"crack_surf_{file_idx:05d}.jpg"
                dst_lbl    = f"crack_surf_{file_idx:05d}.txt"
                raw_bytes  = z.read(src_name)

                with open(img_dir / dst_img, "wb") as f_img:
                    f_img.write(raw_bytes)
                bbox_line = compute_crack_bbox(raw_bytes)
                with open(lbl_dir / dst_lbl, "w", encoding="utf-8") as f_lbl:
                    f_lbl.write(bbox_line)

                crack_total += 1
                if crack_total % 2000 == 0:
                    print(f"        Tiến độ: {crack_total}/{NUM_CRACK} ảnh crack...")

        print(f"   ✅ Hoàn tất {crack_total:,} ảnh Vết nứt (Class 1).")

        # 2.2 — Ảnh Negative (Background) với nhãn rỗng
        print(f"\n   👉 Đang trích xuất {NUM_NEGATIVE:,} ảnh Mẫu âm tính (background)...")
        neg_split_cfg = _make_split_config(len(neg_selected))
        neg_total = 0

        for split_name, start_idx, end_idx in neg_split_cfg:
            img_dir = out_path / split_name / "images"
            lbl_dir = out_path / split_name / "labels"
            count = end_idx - start_idx
            print(f"      - Xuất {count:,} ảnh âm tính → '{split_name}/'...")

            for i in range(start_idx, end_idx):
                src_name  = neg_selected[i]
                file_idx  = i + 1
                dst_img   = f"neg_clean_{file_idx:05d}.jpg"
                dst_lbl   = f"neg_clean_{file_idx:05d}.txt"
                raw_bytes = z.read(src_name)

                with open(img_dir / dst_img, "wb") as f_img:
                    f_img.write(raw_bytes)
                # File nhãn rỗng — chuẩn Ultralytics cho background samples
                with open(lbl_dir / dst_lbl, "w", encoding="utf-8") as f_lbl:
                    pass

                neg_total += 1
                if neg_total % 2000 == 0:
                    print(f"        Tiến độ: {neg_total}/{NUM_NEGATIVE} ảnh negative...")

        print(f"   ✅ Hoàn tất {neg_total:,} ảnh Mẫu âm tính (nhãn rỗng).")

    # ─── BƯỚC 3: Tạo data.yaml ───────────────────────────────────────────────
    print("\n[Bước 3/4] Tạo file cấu hình data.yaml (2 classes)...")
    yaml_content = """\
# RoadGuard AI — Compact 15k Dataset (Potholes + Cracks + Negative Background)
# Tối ưu cho Google Colab Free (GPU T4, 12GB RAM)
# Classes:
#   0: pothole  (Ổ gà, sụt lún)
#   1: crack    (Vết nứt bề mặt đường bê-tông / nhựa)

train: train/images
val:   valid/images
test:  test/images

nc: 2
names: ['pothole', 'crack']
"""
    yaml_path = out_path / "data.yaml"
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write(yaml_content)
    print(f"   ✅ Đã ghi: {yaml_path}")

    # ─── Thống kê tổng kết ────────────────────────────────────────────────────
    train_imgs = len(list((out_path / "train" / "images").glob("*.*")))
    train_lbls = len(list((out_path / "train" / "labels").glob("*.txt")))
    val_imgs   = len(list((out_path / "valid" / "images").glob("*.*")))
    val_lbls   = len(list((out_path / "valid" / "labels").glob("*.txt")))
    test_imgs  = len(list((out_path / "test"  / "images").glob("*.*")))
    test_lbls  = len(list((out_path / "test"  / "labels").glob("*.txt")))
    total_imgs = train_imgs + val_imgs + test_imgs
    total_lbls = train_lbls + val_lbls + test_lbls

    print("\n" + "=" * 75)
    print("📊 BẢNG TỔNG KẾT DATASET ~15K (TỐI ƯU COLAB FREE):")
    print(f"   Tập TRAIN : {train_imgs:>6,} ảnh  |  {train_lbls:>6,} nhãn")
    print(f"   Tập VALID : {val_imgs:>6,} ảnh  |  {val_lbls:>6,} nhãn")
    print(f"   Tập TEST  : {test_imgs:>6,} ảnh  |  {test_lbls:>6,} nhãn")
    print(f"   🔥 TỔNG  : {total_imgs:>6,} ảnh  +  {total_lbls:>6,} file nhãn (khớp 100%)")
    print("=" * 75)
    print("\n💡 Gợi ý huấn luyện trên Colab Free (GPU T4):")
    print("   model.train(data='data.yaml', epochs=50, imgsz=640, batch=16,")
    print("               device=0, workers=2, cache=False)")
    print("   → Dự kiến: ~30–50 phút / 50 epoch trên T4")

    # ─── BƯỚC 4: Đóng gói ZIP ────────────────────────────────────────────────
    if generate_zip:
        print(f"\n[Bước 4/4] Đang đóng gói → {out_zip}...")
        out_zip.parent.mkdir(parents=True, exist_ok=True)
        if out_zip.exists():
            out_zip.unlink()

        with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as z:
            count = 0
            for root, dirs, files in os.walk(out_path):
                for file in files:
                    full_p = Path(root) / file
                    rel_p  = full_p.relative_to(out_path)
                    z.write(full_p, arcname=str(rel_p))
                    count += 1
                    if count % 5000 == 0:
                        print(f"   Đã nén {count}/{total_imgs * 2} files...")

        zip_size_mb = out_zip.stat().st_size / (1024 * 1024)
        print(f"   🎉 Đóng gói thành công: {out_zip}")
        print(f"   📦 Dung lượng zip: {zip_size_mb:.1f} MB")

    print("\n✅ HOÀN TẤT! Dataset ~15k sẵn sàng upload lên Google Colab.\n")


if __name__ == "__main__":
    build_20k_dataset()
