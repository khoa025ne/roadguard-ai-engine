"""
tools/extract_testcases_and_export_dataset.py — Trích Xuất Test Case Các Class Còn Thiếu & Đóng Gói Dataset Train
=================================================================================================================
Tự động quét bộ dữ liệu 15K, phân tích hình thái khuyết tật chuyên sâu (KTV / CrackAnalyzer),
phân loại thành các thư mục Test Case chuyên biệt cho MVP và xuất cấu trúc dataset YOLO chuẩn:
  - 01_pothole_deep (Ổ gà sâu nguy hiểm)
  - 02_pothole_shallow (Ổ gà nông bề mặt)
  - 03_crack_alligator (Vết nứt chân chim / lưới mai rùa)
  - 04_crack_longitudinal (Vết nứt dọc theo tim đường)
  - 05_crack_transverse (Vết nứt ngang tuyến do co ngót nhiệt)
  - 06_joint_gap_or_edge (Mối nối khe co giãn / nứt mép)
  - 07_hard_negatives (Bóng râm cây cối, xe cộ, cột điện, mặt đường sạch không nhầm)
"""

import sys
import os
import shutil
import json
import time
from pathlib import Path
from collections import defaultdict
import cv2
import numpy as np

# Thiết lập mã hóa UTF-8 console Windows
sys.stdout.reconfigure(encoding='utf-8')

# Root project
WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE_ROOT))

from src.curation.crack_analyzer import CrackAnalyzer
from src.curation.auto_tagger import AIAutoTagger

def run_extraction(
    dataset_dir: Path,
    output_testcases_dir: Path,
    output_export_dir: Path,
    sample_limit: int = 400
):
    print("=" * 75)
    print("🚀 ROADGUARD DATASET SCANNER & TEST CASE CURATOR")
    print("=" * 75)
    print(f"• Dataset nguồn: {dataset_dir}")
    print(f"• Thư mục Test Case lưu tại: {output_testcases_dir}")
    print(f"• Thư mục Dataset YOLO xuất ra: {output_export_dir}")
    print(f"• Giới hạn mẫu trích xuất: {sample_limit} ảnh")
    print("-" * 75)

    testcases_dir = Path(output_testcases_dir)
    testcases_dir.mkdir(parents=True, exist_ok=True)

    export_dir = Path(output_export_dir)
    train_img_dir = export_dir / "images" / "train"
    train_lbl_dir = export_dir / "labels" / "train"
    val_img_dir = export_dir / "images" / "val"
    val_lbl_dir = export_dir / "labels" / "val"

    for d in [train_img_dir, train_lbl_dir, val_img_dir, val_lbl_dir]:
        d.mkdir(parents=True, exist_ok=True)

    crack_analyzer = CrackAnalyzer()
    auto_tagger = AIAutoTagger()

    # Danh mục các class con trong MVP
    CATEGORIES = {
        "01_pothole_deep": {
            "title": "Ổ gà sâu nguy hiểm (> 5cm)",
            "yolo_class": 0,
            "yolo_name": "pothole",
            "severity": "CRITICAL",
            "desc": "Ổ gà có độ sâu lớn, gờ mép vỡ sắc nét, nguy cơ gây lật xe máy hoặc rách lốp ô tô.",
            "acceptance": "IoU >= 0.50, Confidence >= 0.45, Action: Cảnh báo đỏ tức thời."
        },
        "02_pothole_shallow": {
            "title": "Ổ gà nông bề mặt (< 3cm)",
            "yolo_class": 0,
            "yolo_name": "pothole",
            "severity": "MEDIUM",
            "desc": "Lõm sụt bề mặt giai đoạn đầu do bong bật đá dăm asphalt, cần vá trám sớm.",
            "acceptance": "IoU >= 0.45, Confidence >= 0.35, Action: Lưu trữ theo dõi bảo trì."
        },
        "03_crack_alligator": {
            "title": "Vết nứt chân chim / lưới mai rùa (Alligator Crack)",
            "yolo_class": 1,
            "yolo_name": "crack",
            "severity": "CRITICAL",
            "desc": "Mạng lưới nứt đa giác đan xen, dấu hiệu mỏi mệt nền móng nghiêm trọng, sắp vỡ thành ổ gà.",
            "acceptance": "IoU >= 0.50, Confidence >= 0.40, Action: Cắt bóc vá toàn phần kết cấu."
        },
        "04_crack_longitudinal": {
            "title": "Vết nứt dọc tuyến (Longitudinal Crack)",
            "yolo_class": 1,
            "yolo_name": "crack",
            "severity": "HIGH",
            "desc": "Vết nứt chạy song song tim đường theo vệt bánh xe, nước mưa dễ thấm gây sụt lở nền hạ.",
            "acceptance": "IoU >= 0.50, Confidence >= 0.40, Action: Trám keo nhựa nóng chống thấm."
        },
        "05_crack_transverse": {
            "title": "Vết nứt ngang tuyến (Transverse Crack)",
            "yolo_class": 1,
            "yolo_name": "crack",
            "severity": "MEDIUM",
            "desc": "Vết nứt cắt ngang mặt đường do co ngót nhiệt độ, gây xóc nảy phương tiện di chuyển.",
            "acceptance": "IoU >= 0.45, Confidence >= 0.35, Action: Xẻ rãnh trám bitum đàn hồi."
        },
        "06_joint_gap_or_edge": {
            "title": "Khe co giãn / nứt mép bê tông (Joint Gap / Edge Crack)",
            "yolo_class": 1,
            "yolo_name": "crack",
            "severity": "MEDIUM",
            "desc": "Hở khe mối nối tấm bê tông xi măng hoặc nứt mép lề do xói lở thoát nước biên.",
            "acceptance": "IoU >= 0.45, Confidence >= 0.35, Action: Trám chèn chèn khe ron định kỳ."
        },
        "07_hard_negatives": {
            "title": "Mẫu âm tính: Bóng râm / Cột điện / Mặt đường sạch",
            "yolo_class": -1,
            "yolo_name": "background",
            "severity": "NONE",
            "desc": "Bóng cây, bóng xe, bóng dây điện, vệt cao su lốp hoặc mặt đường không khuyết tật.",
            "acceptance": "Confidence < 0.25 (Suppressed), BBox rỗng, Không báo động giả."
        }
    }

    # Tạo thư mục test cases
    for cat_key in CATEGORIES:
        (testcases_dir / cat_key / "images").mkdir(parents=True, exist_ok=True)
        (testcases_dir / cat_key / "crops").mkdir(parents=True, exist_ok=True)

    # Thu thập ảnh từ dataset 15k
    test_img_dir = dataset_dir / "test" / "images"
    test_lbl_dir = dataset_dir / "test" / "labels"
    train_source_img_dir = dataset_dir / "train" / "images"
    train_source_lbl_dir = dataset_dir / "train" / "labels"

    img_files = []
    if test_img_dir.exists():
        img_files.extend(list(test_img_dir.glob("*.jpg")) + list(test_img_dir.glob("*.png")))
    if train_source_img_dir.exists() and len(img_files) < sample_limit:
        more_imgs = list(train_source_img_dir.glob("*.jpg")) + list(train_source_img_dir.glob("*.png"))
        img_files.extend(more_imgs[:sample_limit - len(img_files)])

    img_files = img_files[:sample_limit]
    print(f"✓ Tìm thấy {len(img_files)} ảnh cần quét và phân loại.")

    stats = defaultdict(int)
    exported_samples = []

    for idx, img_path in enumerate(img_files, start=1):
        if idx % 50 == 0 or idx == len(img_files):
            print(f"  [{idx:3d}/{len(img_files):3d}] Đang quét và phân tích hình thái khuyết tật...")

        # Tìm label tương ứng
        lbl_path = test_lbl_dir / f"{img_path.stem}.txt"
        if not lbl_path.exists():
            lbl_path = train_source_lbl_dir / f"{img_path.stem}.txt"

        try:
            img_bgr = cv2.imdecode(np.fromfile(str(img_path), dtype=np.uint8), cv2.IMREAD_COLOR)
        except Exception:
            continue

        if img_bgr is None:
            continue

        ih, iw = img_bgr.shape[:2]
        labels = []
        if lbl_path.exists():
            with open(lbl_path, "r", encoding="utf-8") as lf:
                for line in lf:
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        cls_id = int(parts[0])
                        xc, yc, nw, nh = map(float, parts[1:5])
                        labels.append((cls_id, xc, yc, nw, nh))

        # Nếu không có nhãn -> Mẫu âm tính (Background / Clean Road / Shadow)
        if not labels:
            assigned_cat = "07_hard_negatives"
            stats[assigned_cat] += 1
            if stats[assigned_cat] <= 30:
                shutil.copy2(img_path, testcases_dir / assigned_cat / "images" / img_path.name)
            
            # Xuất sang dataset YOLO (ảnh âm tính với label 0 byte)
            dest_target = "train" if (idx % 5 != 0) else "val"
            dest_img = (train_img_dir if dest_target == "train" else val_img_dir) / img_path.name
            dest_lbl = (train_lbl_dir if dest_target == "train" else val_lbl_dir) / f"{img_path.stem}.txt"
            shutil.copy2(img_path, dest_img)
            with open(dest_lbl, "w", encoding="utf-8") as lf:
                pass  # file rỗng
            continue

        # Có nhãn -> Cắt crop và phân tích hình thái
        img_has_pothole = False
        img_has_crack = False

        for b_idx, (cls_id, xc, yc, nw, nh) in enumerate(labels):
            x1 = max(0, int((xc - nw / 2.0) * iw))
            y1 = max(0, int((yc - nh / 2.0) * ih))
            x2 = min(iw, int((xc + nw / 2.0) * iw))
            y2 = min(ih, int((yc + nh / 2.0) * ih))

            crop_w = x2 - x1
            crop_h = y2 - y1
            if crop_w < 8 or crop_h < 8:
                continue

            crop_img = img_bgr[y1:y2, x1:x2]
            crop_name = f"{img_path.stem}_box{b_idx}_{cls_id}.jpg"

            if cls_id == 0:
                # Class 0 = Pothole
                img_has_pothole = True
                gray_crop = cv2.cvtColor(crop_img, cv2.COLOR_BGR2GRAY)
                mean_lum = float(np.mean(gray_crop))
                std_lum = float(np.std(gray_crop))

                # Phân loại độ sâu ổ gà
                if mean_lum < 75 or std_lum > 38:
                    assigned_cat = "01_pothole_deep"
                else:
                    assigned_cat = "02_pothole_shallow"

            else:
                # Class 1 = Crack -> Dùng CrackAnalyzer phân tích góc và hình thái
                img_has_crack = True
                analysis = crack_analyzer.analyze_crop_image(crop_img, confidence=0.75)
                fine_code = analysis.get("fine_tag_code", "")

                if fine_code == "crack_alligator":
                    assigned_cat = "03_crack_alligator"
                elif fine_code == "crack_longitudinal":
                    assigned_cat = "04_crack_longitudinal"
                elif fine_code == "crack_transverse":
                    assigned_cat = "05_crack_transverse"
                else:
                    assigned_cat = "06_joint_gap_or_edge"

            stats[assigned_cat] += 1

            # Lưu vào folder test cases (tối đa 25 crop / class để người dùng kiểm chứng)
            if stats[assigned_cat] <= 25:
                crop_save_p = testcases_dir / assigned_cat / "crops" / crop_name
                cv2.imwrite(str(crop_save_p), crop_img)

                # Vẽ khung trên ảnh gốc để làm tài liệu đối chứng
                vis_img = img_bgr.copy()
                box_color = (0, 0, 255) if cls_id == 0 else (0, 165, 255)
                cv2.rectangle(vis_img, (x1, y1), (x2, y2), box_color, 2)
                cv2.putText(vis_img, f"{CATEGORIES[assigned_cat]['title'][:25]}", (x1, max(20, y1 - 8)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, box_color, 1, cv2.LINE_AA)
                cv2.imwrite(str(testcases_dir / assigned_cat / "images" / img_path.name), vis_img)

        # Xuất ảnh và file nhãn chuẩn YOLO vào folder train/val
        dest_target = "train" if (idx % 5 != 0) else "val"
        dest_img = (train_img_dir if dest_target == "train" else val_img_dir) / img_path.name
        dest_lbl = (train_lbl_dir if dest_target == "train" else val_lbl_dir) / f"{img_path.stem}.txt"
        shutil.copy2(img_path, dest_img)

        with open(dest_lbl, "w", encoding="utf-8") as lf:
            for cls_id, xc, yc, nw, nh in labels:
                lf.write(f"{cls_id} {xc:.6f} {yc:.6f} {nw:.6f} {nh:.6f}\n")

    # Tạo tệp README.md và test_case_spec.json cho từng thư mục Test Case
    for cat_key, cat_meta in CATEGORIES.items():
        spec_path = testcases_dir / cat_key / "test_case_spec.json"
        with open(spec_path, "w", encoding="utf-8") as f:
            json.dump({
                "category_key": cat_key,
                "title": cat_meta["title"],
                "yolo_class_id": cat_meta["yolo_class"],
                "yolo_class_name": cat_meta["yolo_name"],
                "severity": cat_meta["severity"],
                "total_samples": stats[cat_key],
                "description": cat_meta["desc"],
                "acceptance_criteria": cat_meta["acceptance"],
            }, f, ensure_ascii=False, indent=2)

        readme_path = testcases_dir / cat_key / "README.md"
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(f"# Test Case: {cat_meta['title']}\n\n")
            f.write(f"- **Mã định danh:** `{cat_key}`\n")
            f.write(f"- **YOLO Class:** ID `{cat_meta['yolo_class']}` (`{cat_meta['yolo_name']}`)\n")
            f.write(f"- **Mức độ rủi ro:** `{cat_meta['severity']}`\n")
            f.write(f"- **Tổng số mẫu trích xuất:** {stats[cat_key]} mẫu\n\n")
            f.write(f"### 1. Đặc điểm nhận dạng & Nguy cơ kỹ thuật\n{cat_meta['desc']}\n\n")
            f.write(f"### 2. Tiêu chuẩn đánh giá nghiệm thu (Acceptance Criteria)\n{cat_meta['acceptance']}\n\n")
            f.write(f"### 3. Cấu trúc thư mục\n")
            f.write(f"- `images/`: Chứa các ảnh toàn cảnh kèm bounding box trực quan hóa.\n")
            f.write(f"- `crops/`: Chứa ảnh cắt cận cảnh đã lọc sạch dùng làm mẫu kiểm thử benchmark.\n")

    # Tạo file dataset.yaml chuẩn cho YOLO
    data_yaml_content = f"""# RoadGuard AI — Curated Multi-Class Dataset (Pothole + Crack + Negatives)
# Tự động xuất xưởng từ Module AI Curation & Test Case Extractor
# Ngày tạo: {time.strftime('%Y-%m-%d %H:%M:%S')}

path: {output_export_dir.as_posix()}
train: images/train
val:   images/val

# Số lượng class cốt lõi cho mô hình YOLOv11
nc: 2
names:
  0: pothole
  1: crack
"""
    with open(export_dir / "dataset.yaml", "w", encoding="utf-8") as f:
        f.write(data_yaml_content)

    print("\n" + "=" * 75)
    print("📊 TỔNG KẾT BỘ TEST CASE & DỮ LIỆU ĐÃ TRÍCH XUẤT THÀNH CÔNG")
    print("=" * 75)
    print(f"{'Mã Test Case / Lớp':<30} | {'Mô tả Chi Tiết':<32} | {'Số Mẫu':<8}")
    print("-" * 75)
    for cat_key, cat_meta in CATEGORIES.items():
        print(f"{cat_key:<30} | {cat_meta['title'][:30]:<32} | {stats[cat_key]:<8}")
    print("=" * 75)
    print(f"📁 Thư mục Test Cases: {testcases_dir}")
    print(f"📦 Thư mục Dataset YOLO: {export_dir}")
    print(f"📄 File cấu hình huấn luyện: {export_dir / 'dataset.yaml'}")
    print("=" * 75)

    return stats


if __name__ == "__main__":
    src_data = WORKSPACE_ROOT / "data" / "unified_road_dataset_15k"
    tc_out = WORKSPACE_ROOT / "data" / "mvp_test_cases"
    export_out = WORKSPACE_ROOT / "data" / "curated_export" / "roadguard_unified_finetune"

    run_extraction(
        dataset_dir=src_data,
        output_testcases_dir=tc_out,
        output_export_dir=export_out,
        sample_limit=450
    )
