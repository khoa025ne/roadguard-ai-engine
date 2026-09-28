"""
src/curation/dataset_exporter.py — Module Đóng Gói Dataset Chuẩn YOLO
====================================================================
Đóng gói các mẫu đã được thẩm định và gắn nhãn thành một bộ dữ liệu hoàn chỉnh:
- Chuẩn hóa Bounding Box [x1, y1, x2, y2] về không gian [x_center, y_center, w, h] (0.0 - 1.0).
- Phân luồng train / val (80/20) và tạo nhãn rỗng cho mẫu âm tính (Hard Negatives).
- Xuất file cấu hình data.yaml và nén thành tệp .zip sẵn sàng nạp thẳng lên Colab/Kaggle.
"""

import os
import shutil
import zipfile
import json
import time
import cv2
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Optional


class DatasetExporter:
    """Đóng gói dữ liệu khuyết tật đã tinh tuyển thành Dataset chuẩn YOLO."""

    def __init__(self, base_export_dir: Path | str = "F:/train AI đồ án/data/curated_export"):
        self.base_export_dir = Path(base_export_dir)
        self.base_export_dir.mkdir(parents=True, exist_ok=True)

    def export_yolo_dataset(
        self,
        curated_items: List[Dict[str, Any]],
        frames_lookup: Dict[str, Path | str],
        export_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Đóng gói danh sách khuyết tật thành Dataset YOLO.
        """
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        exp_id = export_name or f"curated_batch_{timestamp}"
        target_dir = self.base_export_dir / exp_id

        # Tạo cấu trúc thư mục
        train_img_dir = target_dir / "train" / "images"
        train_lbl_dir = target_dir / "train" / "labels"
        val_img_dir = target_dir / "val" / "images"
        val_lbl_dir = target_dir / "val" / "labels"
        neg_img_dir = target_dir / "hard_negatives" / "images"
        neg_lbl_dir = target_dir / "hard_negatives" / "labels"

        for d in [train_img_dir, train_lbl_dir, val_img_dir, val_lbl_dir, neg_img_dir, neg_lbl_dir]:
            d.mkdir(parents=True, exist_ok=True)

        # Gom nhóm các khuyết tật theo frame_id/frame_path để không bị ghi đè nhãn
        frame_detections: Dict[str, List[Dict[str, Any]]] = {}
        hard_negatives: List[Dict[str, Any]] = []

        for item in curated_items:
            if not item.get("is_valid", True) or item.get("status") == "FALSE_ALARM":
                hard_negatives.append(item)
            else:
                f_key = str(item.get("frame_index") or item.get("frame_file") or item.get("frame_path"))
                if f_key not in frame_detections:
                    frame_detections[f_key] = []
                frame_detections[f_key].append(item)

        total_frames = len(frame_detections)
        all_keys = list(frame_detections.keys())
        # Phân chia 80% train, 20% val
        split_idx = max(1, int(len(all_keys) * 0.8)) if len(all_keys) > 1 else len(all_keys)
        train_keys = set(all_keys[:split_idx])

        pos_count = 0
        pothole_count = 0
        crack_count = 0

        # Xử lý các mẫu khuyết tật hợp lệ
        for f_key, dets in frame_detections.items():
            first_det = dets[0]
            raw_frame_path = first_det.get("frame_path") or frames_lookup.get(f_key)

            if not raw_frame_path or not Path(raw_frame_path).exists():
                # Nếu không có frame gốc thì dùng ảnh crop của từng detection
                for d in dets:
                    crop_p = Path(d["crop_path"])
                    if crop_p.exists():
                        is_train = (f_key in train_keys)
                        dest_img = (train_img_dir if is_train else val_img_dir) / crop_p.name
                        dest_lbl = (train_lbl_dir if is_train else val_lbl_dir) / f"{crop_p.stem}.txt"
                        shutil.copy2(crop_p, dest_img)

                        cls_id = d.get("yolo_class_id", 0)
                        if cls_id == 0:
                            pothole_count += 1
                        else:
                            crack_count += 1
                        pos_count += 1

                        # Bounding box chiếm trọn ảnh crop: center 0.5, 0.5, w 0.9, h 0.9
                        with open(dest_lbl, "w", encoding="utf-8") as lf:
                            lf.write(f"{cls_id} 0.500000 0.500000 0.900000 0.900000\n")
                continue

            # Đọc frame gốc để lấy kích thước W, H
            raw_frame_path = Path(raw_frame_path)
            try:
                frame_mat = cv2.imdecode(np.fromfile(str(raw_frame_path), dtype=np.uint8), cv2.IMREAD_COLOR)
            except Exception:
                frame_mat = None

            if frame_mat is None:
                continue

            fh, fw = frame_mat.shape[:2]
            is_train = (f_key in train_keys)
            dest_img = (train_img_dir if is_train else val_img_dir) / raw_frame_path.name
            dest_lbl = (train_lbl_dir if is_train else val_lbl_dir) / f"{raw_frame_path.stem}.txt"

            shutil.copy2(raw_frame_path, dest_img)

            # Tạo file nhãn YOLO chuẩn hóa
            with open(dest_lbl, "w", encoding="utf-8") as lf:
                for d in dets:
                    box = d.get("box", [0, 0, 0, 0])
                    x1, y1, x2, y2 = box
                    # Giới hạn tọa độ trong ảnh
                    x1 = max(0, min(fw - 1, x1))
                    y1 = max(0, min(fh - 1, y1))
                    x2 = max(0, min(fw, x2))
                    y2 = max(0, min(fh, y2))

                    bw = x2 - x1
                    bh = y2 - y1
                    if bw <= 1 or bh <= 1:
                        continue

                    # Chuyển đổi sang normalized xywh
                    x_center = (x1 + bw / 2.0) / fw
                    y_center = (y1 + bh / 2.0) / fh
                    norm_w = bw / fw
                    norm_h = bh / fh
                    cls_id = d.get("yolo_class_id", 0)

                    if cls_id == 0:
                        pothole_count += 1
                    else:
                        crack_count += 1
                    pos_count += 1

                    lf.write(f"{cls_id} {x_center:.6f} {y_center:.6f} {norm_w:.6f} {norm_h:.6f}\n")

        # Xử lý các mẫu âm tính (Hard Negatives)
        neg_count = 0
        for neg in hard_negatives:
            crop_p = Path(neg.get("crop_path", ""))
            if crop_p.exists():
                dest_neg_img = neg_img_dir / crop_p.name
                dest_neg_lbl = neg_lbl_dir / f"{crop_p.stem}.txt"
                shutil.copy2(crop_p, dest_neg_img)
                # File rỗng (0 bytes) cho nhãn âm tính
                with open(dest_neg_lbl, "w", encoding="utf-8") as lf:
                    pass
                neg_count += 1

        # Tạo file data.yaml
        data_yaml_content = f"""# RoadGuard AI — Curated Fine-Tuning Dataset Patch
# Tự động xuất xưởng từ Module AI Curation & Auto-Tagger
# Ngày tạo: {time.strftime("%Y-%m-%d %H:%M:%S")}

train: train/images
val:   val/images

nc: 2
names: ['pothole', 'crack']

# Phân bổ mẫu:
# - Mẫu Ổ gà (pothole): {pothole_count}
# - Mẫu Vết nứt (crack): {crack_count}
# - Mẫu Báo động giả (hard negatives): {neg_count}
"""
        yaml_path = target_dir / "data.yaml"
        with open(yaml_path, "w", encoding="utf-8") as yf:
            yf.write(data_yaml_content)

        # Xuất file báo cáo chi tiết
        summary_data = {
            "export_id": exp_id,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_items_curated": len(curated_items),
            "positive_defects_count": pos_count,
            "pothole_count": pothole_count,
            "crack_count": crack_count,
            "hard_negatives_count": neg_count,
            "target_dir": str(target_dir).replace("\\", "/"),
            "items": curated_items
        }
        summary_path = target_dir / "curation_summary.json"
        with open(summary_path, "w", encoding="utf-8") as sf:
            json.dump(summary_data, sf, ensure_ascii=False, indent=2)

        # Nén toàn bộ thư mục thành file .zip
        zip_output_path = self.base_export_dir / f"{exp_id}.zip"
        with zipfile.ZipFile(zip_output_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(target_dir):
                for f in files:
                    file_path = Path(root) / f
                    arcname = file_path.relative_to(target_dir)
                    zipf.write(file_path, arcname=str(arcname))

        zip_size_bytes = zip_output_path.stat().st_size
        zip_size_mb = round(zip_size_bytes / (1024 * 1024), 3)

        return {
            "status": "SUCCESS",
            "export_id": exp_id,
            "zip_file": str(zip_output_path).replace("\\", "/"),
            "zip_filename": zip_output_path.name,
            "zip_size_bytes": zip_size_bytes,
            "zip_size_mb": zip_size_mb,
            "summary": summary_data
        }
