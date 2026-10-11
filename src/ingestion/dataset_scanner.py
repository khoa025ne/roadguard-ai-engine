"""
src/ingestion/dataset_scanner.py — Công cụ Quét & Đánh Giá Hiệu Năng Dataset (ZIP / Folder)
=========================================================================================
Cung cấp giải pháp tự động hoá cho phép người dùng đưa vào file nén Dataset (.ZIP)
hoặc thư mục chứa ảnh mặt đường:
1. Tự động giải nén thông minh và an toàn (chống Zip Slip).
2. Tự động quét đệ quy tìm kiếm toàn bộ định dạng ảnh (.jpg, .png, .jpeg, .bmp, .webp).
3. Chạy mô hình YOLO dò quét từng ảnh: xác định có vết nứt (crack), ổ gà (pothole) hay không.
4. Đánh giá hiệu năng định lượng:
   - Tỷ lệ phát hiện khuyết tật (Detection Hit Rate %).
   - Số lượng khuyết tật phân loại theo từng class.
   - Tốc độ xử lý trung bình (ms/ảnh, FPS).
5. Trích xuất ảnh vẽ Bounding Box trực quan và lưu ảnh cắt (Crops) để phục vụ luồng thẩm định KDV.
"""

import os
import sys
import time
import json
import zipfile
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
import cv2
import numpy as np


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def safe_imread(file_path: Path | str) -> Optional[np.ndarray]:
    """Đọc ảnh an toàn hỗ trợ đường dẫn tiếng Việt UTF-8 trên Windows."""
    try:
        p = Path(file_path)
        if not p.exists():
            return None
        data = np.fromfile(str(p), dtype=np.uint8)
        return cv2.imdecode(data, cv2.IMREAD_COLOR)
    except Exception:
        return None


def safe_imwrite(file_path: Path | str, img: np.ndarray) -> bool:
    """Ghi ảnh an toàn hỗ trợ đường dẫn tiếng Việt UTF-8 trên Windows."""
    try:
        p = Path(file_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        ext = p.suffix.lower() if p.suffix else ".jpg"
        ret, buf = cv2.imencode(ext, img)
        if ret:
            buf.tofile(str(p))
            return True
        return False
    except Exception:
        return False


class DatasetScanner:
    """Bộ giải nén, quét ảnh và đánh giá hiệu năng dataset khuyết tật đường."""

    def __init__(self, predictor=None):
        self.predictor = predictor

    def extract_zip(self, zip_path: Path | str, target_dir: Path | str) -> List[Path]:
        """
        Giải nén an toàn file .ZIP và trả về danh sách toàn bộ ảnh tìm thấy.
        Chống tấn công Path Traversal (Zip Slip).
        """
        zip_path = Path(zip_path)
        target_dir = Path(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        if not zip_path.exists():
            raise FileNotFoundError(f"Không tìm thấy file ZIP: {zip_path}")

        extracted_paths = []
        with zipfile.ZipFile(str(zip_path), "r") as zf:
            for member in zf.infolist():
                # Bỏ qua thư mục rác hệ điều hành
                if member.filename.startswith("__MACOSX/") or member.filename.endswith("/"):
                    continue

                # Kiểm tra Zip Slip
                member_path = Path(member.filename)
                target_file = (target_dir / member_path).resolve()
                if not str(target_file).startswith(str(target_dir.resolve())):
                    raise ValueError(f"Cảnh báo bảo mật: File zip chứa đường dẫn không an toàn: {member.filename}")

                target_file.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as source, open(target_file, "wb") as target:
                    shutil.copyfileobj(source, target)

                if target_file.suffix.lower() in IMAGE_EXTENSIONS:
                    extracted_paths.append(target_file)

        extracted_paths.sort()
        return extracted_paths

    def find_images_in_folder(self, folder_path: Path | str) -> List[Path]:
        """Tìm kiếm đệ quy toàn bộ file ảnh trong thư mục."""
        folder_path = Path(folder_path)
        if not folder_path.exists():
            return []

        images = []
        for ext in IMAGE_EXTENSIONS:
            images.extend(folder_path.rglob(f"*{ext}"))
            images.extend(folder_path.rglob(f"*{ext.upper()}"))

        # Lọc bỏ file rác và trùng lặp
        valid_images = [
            p for p in set(images)
            if not any(part.startswith(".") or part == "__MACOSX" for part in p.parts)
        ]
        valid_images.sort()
        return valid_images

    def scan_images(
        self,
        image_paths: List[Path],
        output_dir: Path | str,
        predictor=None,
        max_images: Optional[int] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Chạy mô hình AI quét toàn bộ danh sách ảnh và xuất báo cáo hiệu năng.
        """
        output_dir = Path(output_dir)
        vis_dir = output_dir / "visualizations"
        crops_dir = output_dir / "crops"
        vis_dir.mkdir(parents=True, exist_ok=True)
        crops_dir.mkdir(parents=True, exist_ok=True)

        model = predictor or self.predictor
        if model is None:
            raise ValueError("Chưa cung cấp mô hình RoadDefectPredictor để quét ảnh!")

        if max_images and len(image_paths) > max_images:
            image_paths = image_paths[:max_images]

        total_images = len(image_paths)
        if total_images == 0:
            return {
                "status": "EMPTY",
                "message": "Không tìm thấy file ảnh nào trong dataset",
                "summary": {"total_images": 0, "defect_images": 0, "hit_rate_pct": 0.0}
            }

        scanned_results = []
        all_crops = []
        pothole_count = 0
        crack_count = 0
        defect_images_count = 0
        latencies = []

        for idx, img_path in enumerate(image_paths, start=1):
            if progress_callback:
                progress_callback(idx, total_images, img_path.name)

            img = safe_imread(img_path)
            if img is None:
                continue

            h, w = img.shape[:2]

            # Đo độ trễ inference
            t_start = time.perf_counter()
            # Nếu ảnh độ phân giải cao > 1500px -> Dùng Full Frame Tiling; nếu nhỏ -> Dùng predict_tile
            if max(h, w) > 1500:
                detections = model.predict_full_frame(img, use_tiling=True)
            else:
                detections = model.predict_tile(img)
            latency_ms = (time.perf_counter() - t_start) * 1000
            latencies.append(latency_ms)

            has_defect = len(detections) > 0
            if has_defect:
                defect_images_count += 1

            # Vẽ ảnh trực quan (Visualization)
            vis_img = img.copy()
            frame_crops = []

            for det_idx, det in enumerate(detections, start=1):
                cls_name = det.get("class_name", "defect").lower()
                conf = det.get("confidence", 0.0)
                box = det.get("box", [0, 0, 0, 0])
                x1, y1, x2, y2 = [int(v) for v in box]

                # Chuẩn hóa tọa độ trong khung hình
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w, x2), min(h, y2)

                if "crack" in cls_name:
                    is_pothole = False
                elif "pothole" in cls_name:
                    is_pothole = True
                else:
                    is_pothole = (det.get("class_id") == 0)

                if is_pothole:
                    pothole_count += 1
                    color = (0, 0, 255)  # Đỏ
                    label = f"O ga {conf:.2f}"
                    standard_class = "pothole"
                else:
                    crack_count += 1
                    color = (0, 255, 255)  # Vàng
                    label = f"Vet nut {conf:.2f}"
                    standard_class = "crack"

                # Vẽ Bounding Box & Label
                cv2.rectangle(vis_img, (x1, y1), (x2, y2), color, 2)
                cv2.putText(
                    vis_img, label, (x1, max(20, y1 - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2, cv2.LINE_AA
                )

                # Trích xuất ảnh Crop khuyết tật
                if x2 > x1 and y2 > y1:
                    crop_roi = img[y1:y2, x1:x2]
                    crop_filename = f"crop_img{idx:04d}_{det_idx:02d}_{standard_class}.jpg"
                    crop_dest = crops_dir / crop_filename
                    safe_imwrite(crop_dest, crop_roi)

                    crop_item = {
                        "crop_id": f"crop_ds_{idx}_{det_idx}",
                        "crop_filename": crop_filename,
                        "crop_path": str(crop_dest),
                        "crop_url": f"/api/crops/{crop_filename}",
                        "source_image": img_path.name,
                        "source_image_path": str(img_path),
                        "image_index": idx,
                        "class_name": standard_class,
                        "confidence": round(conf, 4),
                        "box": [x1, y1, x2, y2],
                        "timestamp_s": round(idx * 0.5, 2)  # Giả lập mốc thời gian hiển thị
                    }
                    frame_crops.append(crop_item)
                    all_crops.append(crop_item)

            # Lưu ảnh vẽ kết quả
            vis_filename = f"vis_{idx:04d}_{img_path.name}"
            vis_dest = vis_dir / vis_filename
            safe_imwrite(vis_dest, vis_img)

            scanned_results.append({
                "image_index": idx,
                "filename": img_path.name,
                "original_path": str(img_path),
                "vis_path": str(vis_dest),
                "vis_url": f"/api/dataset-vis/{vis_filename}",
                "width": w,
                "height": h,
                "latency_ms": round(latency_ms, 2),
                "has_defect": has_defect,
                "defect_count": len(detections),
                "detections": detections,
                "crops": frame_crops
            })

        # Tổng kết số liệu hiệu năng
        avg_latency = float(np.mean(latencies)) if latencies else 0.0
        fps = 1000.0 / max(1e-3, avg_latency)
        hit_rate = (defect_images_count / max(1, total_images)) * 100.0
        clean_images = total_images - defect_images_count

        summary = {
            "total_images": total_images,
            "defect_images": defect_images_count,
            "clean_images": clean_images,
            "hit_rate_pct": round(hit_rate, 2),
            "total_defects_found": pothole_count + crack_count,
            "crack_count": crack_count,
            "pothole_count": pothole_count,
            "avg_latency_ms": round(avg_latency, 2),
            "fps": round(fps, 2),
            "total_crops_generated": len(all_crops)
        }

        report_data = {
            "status": "COMPLETED",
            "summary": summary,
            "images": scanned_results,
            "all_crops": all_crops
        }

        # Lưu báo cáo JSON
        report_path = output_dir / "dataset_eval_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)

        report_data["report_file"] = str(report_path)
        return report_data
