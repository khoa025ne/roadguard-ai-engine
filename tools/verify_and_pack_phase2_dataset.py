"""
tools/verify_and_pack_phase2_dataset.py — Kiểm Tra Toàn Vẹn & Xuất Bản Bộ Dữ Liệu Train Lần 2
=============================================================================================
Nhiệm vụ:
1. Quét kiểm tra toàn bộ 15,000 ảnh và nhãn của unified_road_dataset_15k.
2. Kiểm tra tính hợp lệ của bounding box (0.0 <= x, y, w, h <= 1.0).
3. Thống kê tỷ lệ phân bổ lớp: Pothole (0), Crack (1), Hard Negatives (Empty).
4. Tạo file cấu hình data_phase2.yaml linh hoạt (hỗ trợ cả đường dẫn tương đối và tuyệt đối).
5. Tự động đóng gói file zip chuẩn nếu cần upload lên Google Colab / Kaggle / Drive.
"""

import sys
import os
import json
import zipfile
import time
from pathlib import Path
from collections import Counter

# Console UTF-8 cho Windows
sys.stdout.reconfigure(encoding='utf-8')

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
DATASET_DIR = WORKSPACE_ROOT / "data" / "unified_road_dataset_15k"

def verify_dataset():
    print("=" * 80)
    print("📋 ROADGUARD AI — KIỂM TRA TOÀN VẸN DỮ LIỆU HUẤN LUYỆN LẦN 2 (PHASE 2)")
    print("=" * 80)
    print(f"• Thư mục dataset: {DATASET_DIR}")

    if not DATASET_DIR.exists():
        print(f"❌ LỖI: Không tìm thấy thư mục {DATASET_DIR}")
        sys.exit(1)

    splits = ["train", "valid", "test"]
    manifest = {}

    total_all_images = 0
    total_all_labels = 0
    total_all_potholes = 0
    total_all_cracks = 0
    total_all_negatives = 0

    for split in splits:
        img_dir = DATASET_DIR / split / "images"
        lbl_dir = DATASET_DIR / split / "labels"

        images = list(img_dir.glob("*.*"))
        labels = list(lbl_dir.glob("*.txt"))

        img_stems = {p.stem: p for p in images}
        lbl_stems = {p.stem: p for p in labels}

        # Kiểm tra khớp cặp 1:1
        missing_lbls = [s for s in img_stems if s not in lbl_stems]
        orphan_lbls = [s for s in lbl_stems if s not in img_stems]

        class_counter = Counter()
        empty_count = 0
        invalid_box_count = 0

        for lbl_stem, lbl_path in lbl_stems.items():
            content = lbl_path.read_text(encoding="utf-8").strip()
            if not content:
                empty_count += 1
                continue

            for line in content.splitlines():
                parts = line.strip().split()
                if len(parts) >= 5:
                    cls_id = parts[0]
                    class_counter[cls_id] += 1
                    try:
                        xc, yc, w, h = map(float, parts[1:5])
                        if not (0.0 <= xc <= 1.0 and 0.0 <= yc <= 1.0 and 0.0 < w <= 1.0 and 0.0 < h <= 1.0):
                            invalid_box_count += 1
                    except ValueError:
                        invalid_box_count += 1

        pothole_cnt = class_counter.get("0", 0)
        crack_cnt = class_counter.get("1", 0)

        manifest[split] = {
            "total_images": len(images),
            "total_labels": len(labels),
            "missing_labels": len(missing_lbls),
            "orphan_labels": len(orphan_lbls),
            "pothole_boxes": pothole_cnt,
            "crack_boxes": crack_cnt,
            "negative_images": empty_count,
            "invalid_boxes": invalid_box_count
        }

        total_all_images += len(images)
        total_all_labels += len(labels)
        total_all_potholes += pothole_cnt
        total_all_cracks += crack_cnt
        total_all_negatives += empty_count

        print(f"\n📁 Phân vùng: [{split.upper()}]")
        print(f"   • Số lượng ảnh:            {len(images):,}")
        print(f"   • Bounding Box Ổ Gà (0):   {pothole_cnt:,}")
        print(f"   • Bounding Box Vết Nứt (1):{crack_cnt:,}")
        print(f"   • Mẫu âm tính sạch (Bóng): {empty_count:,} ({empty_count/max(1,len(images))*100:.1f}%)")
        print(f"   • Bounding Box không hợp lệ: {invalid_box_count}")

    print("\n" + "=" * 80)
    print("📊 TỔNG KẾT TOÀN DIỆN BỘ DỮ LIỆU 15K")
    print("=" * 80)
    print(f"• Tổng số ảnh toàn bộ:            {total_all_images:,} ảnh")
    print(f"• Tổng số nhãn tương ứng:         {total_all_labels:,} file .txt")
    print(f"• Tổng BBox Ổ Gà (Class 0):       {total_all_potholes:,} đối tượng")
    print(f"• Tổng BBox Vết Nứt (Class 1):    {total_all_cracks:,} đối tượng")
    print(f"• Tổng ảnh Âm tính / Khử bóng râm:{total_all_negatives:,} ảnh sạch")
    print("=" * 80)

    # 1. Tạo file cấu hình data_phase2.yaml (Local)
    local_yaml_path = DATASET_DIR / "data_phase2.yaml"
    local_yaml_content = f"""# RoadGuard AI — Cấu hình Dataset Huấn Luyện Lần 2 (Phase 2 Fine-Tuning)
# Phiên bản: Unified 2-Class (Pothole + Crack + Hard Negatives)
# Ngày tạo: {time.strftime('%Y-%m-%d %H:%M:%S')}

path: {DATASET_DIR.as_posix()}
train: train/images
val:   valid/images
test:  test/images

nc: 2
names:
  0: pothole
  1: crack

# Metadata đặc tả phục vụ đánh giá:
metadata:
  total_images: {total_all_images}
  classes:
    0: "Ổ gà, sụt lún mặt đường (Pothole)"
    1: "Vết nứt mặt đường (Crack - dọc, ngang, lưới mai rùa)"
  negative_ratio: "{total_all_negatives/max(1, total_all_images)*100:.1f}%"
"""
    with open(local_yaml_path, "w", encoding="utf-8") as f:
        f.write(local_yaml_content)
    print(f"✓ Đã tạo file cấu hình Local: {local_yaml_path}")

    # 2. Tạo file cấu hình data_colab.yaml (Đường dẫn tương đối cho Google Colab)
    colab_yaml_path = DATASET_DIR / "data_colab.yaml"
    colab_yaml_content = f"""# RoadGuard AI — Cấu hình Dataset dành cho Google Colab
# Lưu ý: Khi giải nén vào thư mục ./dataset trên Colab

path: ./dataset
train: train/images
val:   valid/images
test:  test/images

nc: 2
names:
  0: pothole
  1: crack
"""
    with open(colab_yaml_path, "w", encoding="utf-8") as f:
        f.write(colab_yaml_content)
    print(f"✓ Đã tạo file cấu hình Colab: {colab_yaml_path}")

    # 3. Xuất file manifest json
    manifest_path = DATASET_DIR / "dataset_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"✓ Đã xuất bảng đặc tả Manifest: {manifest_path}")

    return manifest

if __name__ == "__main__":
    verify_dataset()
