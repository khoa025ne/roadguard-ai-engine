"""
src/curation/deduplicator.py — Bộ Khử Trùng Lặp Đối Tượng Khuyết Tật (Defect Deduplicator)
========================================================================================
Đảm bảo số lượng khuyết tật khớp được (Matched items) KHÔNG BỊ TRÙNG LẶP:
1. Trùng lặp đa khung hình (Temporal Multi-frame):
   Khi flycam/drone bay ở 2 fps, cùng một ổ gà hoặc vết nứt xuất hiện liên tiếp trong 2-4 giây.
2. Trùng lặp do gối đầu lưới (Spatial Tiling Overlap):
   Khi cắt mảnh 640x640 gối đầu 20%, cùng một khuyết tật ở vùng biên có thể bị cắt làm 2 ảnh cận cảnh.
3. So sánh độ tương đồng thị giác (Computer Vision Visual Similarity):
   Phân tích tương quan biểu đồ màu (Color Histogram Correlation) & cấu trúc viền để gom các góc chụp của cùng 1 khuyết tật.
4. Tích hợp chỉ định từ KTV AI (Semantic Deduplication):
   Tôn trọng trường duplicate_of / is_duplicate từ KTV gpt-5.4.
"""

import math
import cv2
import numpy as np
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional


class DefectDeduplicator:
    """Bộ giải thuật gom cụm và khử trùng lặp đối tượng khuyết tật đường."""

    def __init__(
        self,
        time_threshold_s: float = 2.0,
        frame_threshold: int = 4,
        spatial_dist_norm_threshold: float = 0.20,
        visual_similarity_threshold: float = 0.76
    ):
        self.time_threshold_s = time_threshold_s
        self.frame_threshold = frame_threshold
        self.spatial_dist_norm_threshold = spatial_dist_norm_threshold
        self.visual_similarity_threshold = visual_similarity_threshold

    def _calc_visual_similarity(self, path1: Optional[str], path2: Optional[str]) -> float:
        """Tính độ tương đồng thị giác giữa 2 ảnh crop qua tương quan biểu đồ màu."""
        if not path1 or not path2:
            return 0.0
        p1, p2 = Path(path1), Path(path2)
        if not p1.exists() or not p2.exists():
            return 0.0

        try:
            img1 = cv2.imdecode(np.fromfile(str(p1), dtype=np.uint8), cv2.IMREAD_COLOR)
            img2 = cv2.imdecode(np.fromfile(str(p2), dtype=np.uint8), cv2.IMREAD_COLOR)
            if img1 is None or img2 is None:
                return 0.0

            img1 = cv2.resize(img1, (64, 64), interpolation=cv2.INTER_AREA)
            img2 = cv2.resize(img2, (64, 64), interpolation=cv2.INTER_AREA)

            hsv1 = cv2.cvtColor(img1, cv2.COLOR_BGR2HSV)
            hsv2 = cv2.cvtColor(img2, cv2.COLOR_BGR2HSV)

            hist1 = cv2.calcHist([hsv1], [0, 1], None, [16, 16], [0, 180, 0, 256])
            hist2 = cv2.calcHist([hsv2], [0, 1], None, [16, 16], [0, 180, 0, 256])

            cv2.normalize(hist1, hist1, 0, 1, cv2.NORM_MINMAX)
            cv2.normalize(hist2, hist2, 0, 1, cv2.NORM_MINMAX)

            corr = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)
            return float(max(0.0, corr))
        except Exception:
            return 0.0

    def _is_same_defect(self, it1: Dict[str, Any], it2: Dict[str, Any]) -> Tuple[bool, str]:
        """Xác định xem 2 item có phải là cùng một khuyết tật hay không."""
        # 1. Nếu KTV đã chỉ định tường minh
        dup_of = it2.get("duplicate_of")
        if dup_of is not None and str(dup_of) in [str(it1.get("index")), str(it1.get("id")), str(it1.get("crop_id"))]:
            return True, "KTV AI xác nhận cùng đối tượng"

        # 2. Kiểm tra loại khuyết tật cơ bản
        cls1 = (it1.get("class_name") or "crack").lower()
        cls2 = (it2.get("class_name") or "crack").lower()
        # Chuẩn hóa nếu là pothole vs crack
        is_pothole1 = "pothole" in cls1 or "ổ gà" in str(it1.get("fine_tag", "")).lower()
        is_pothole2 = "pothole" in cls2 or "ổ gà" in str(it2.get("fine_tag", "")).lower()
        if is_pothole1 != is_pothole2:
            return False, "Khác loại khuyết tật"

        # 3. Kiểm tra mốc thời gian / frame
        t1 = float(it1.get("timestamp_s", 0.0))
        t2 = float(it2.get("timestamp_s", 0.0))
        f1 = int(it1.get("frame_index", 0))
        f2 = int(it2.get("frame_index", 0))

        delta_t = abs(t1 - t2)
        delta_f = abs(f1 - f2)

        # Nếu cùng một frame (ví dụ do tiling overlap 20% cắt 2 mảnh)
        b1 = it1.get("box") or []
        b2 = it2.get("box") or []
        if (delta_f == 0 or delta_t < 0.2) and len(b1) == 4 and len(b2) == 4:
            # Tính IOU giữa 2 box
            xA = max(b1[0], b2[0])
            yA = max(b1[1], b2[1])
            xB = min(b1[2], b2[2])
            yB = min(b1[3], b2[3])
            interArea = max(0, xB - xA) * max(0, yB - yA)
            boxAArea = max(1, (b1[2] - b1[0]) * (b1[3] - b1[1]))
            boxBArea = max(1, (b2[2] - b2[0]) * (b2[3] - b2[1]))
            iou = interArea / float(boxAArea + boxBArea - interArea)
            if iou > 0.25:
                return True, f"Trùng lặp vùng gối đầu (IOU={iou:.2f})"

        # 4. Nếu trong khung thời gian gần nhau (<= threshold)
        if delta_t <= self.time_threshold_s or delta_f <= self.frame_threshold:
            # Kiểm tra khoảng cách tọa độ chuẩn hóa
            box_dist = 1.0
            if len(b1) == 4 and len(b2) == 4:
                c1_x = (b1[0] + b1[2]) / 2.0
                c1_y = (b1[1] + b1[3]) / 2.0
                c2_x = (b2[0] + b2[2]) / 2.0
                c2_y = (b2[1] + b2[3]) / 2.0
                # Khoảng cách Euclide chuẩn hóa theo khung hình (ước lượng 1280x720)
                box_dist = math.hypot((c1_x - c2_x) / 1280.0, (c1_y - c2_y) / 720.0)

            # Kiểm tra tương quan thị giác giữa 2 ảnh crop
            crop1 = it1.get("crop_path") or it1.get("crop_file")
            crop2 = it2.get("crop_path") or it2.get("crop_file")
            sim = self._calc_visual_similarity(crop1, crop2)

            if box_dist <= self.spatial_dist_norm_threshold and sim >= 0.65:
                return True, f"Trùng vết nứt/ổ gà qua frame liên tiếp (Khoảng cách={box_dist:.2f}, Độ giống={sim:.2f})"

            if sim >= self.visual_similarity_threshold:
                return True, f"Cùng hình thái khuyết tật thị giác (Độ giống={sim:.2f})"

        return False, "Khuyết tật khác biệt"

    def deduplicate(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Khử trùng lặp danh sách khuyết tật:
        - Gom các ảnh cùng 1 đối tượng vào chung 1 nhóm (Cluster).
        - Chọn 1 ảnh tốt nhất (độ tin cậy cao nhất) làm Đại diện chính (Primary).
        - Đính kèm các ảnh góc nhìn khác vào mảng `duplicate_views`.
        - Đảm bảo số lượng mục match được KHÔNG BỊ TRÙNG LẶP.
        """
        if not items:
            return {
                "deduplicated_items": [],
                "unique_items": [],
                "total_items": 0,
                "unique_count": 0,
                "duplicate_count": 0
            }

        clusters: List[List[Dict[str, Any]]] = []

        for it in items:
            item_copy = dict(it)
            matched_cluster_idx = -1

            # Tìm xem item có thuộc cluster nào đã có không
            for c_idx, cluster in enumerate(clusters):
                # So sánh với đại diện đầu tiên của cluster
                rep = cluster[0]
                is_same, reason = self._is_same_defect(rep, item_copy)
                if is_same:
                    matched_cluster_idx = c_idx
                    item_copy["duplicate_reason"] = reason
                    break

            if matched_cluster_idx >= 0:
                clusters[matched_cluster_idx].append(item_copy)
            else:
                clusters.append([item_copy])

        processed_all: List[Dict[str, Any]] = []
        unique_items: List[Dict[str, Any]] = []

        for c_idx, cluster in enumerate(clusters):
            # Sắp xếp cluster theo confidence giảm dần để lấy ảnh rõ nhất làm đại diện
            cluster.sort(key=lambda x: float(x.get("confidence_verified") or x.get("confidence") or 0.0), reverse=True)
            primary = cluster[0]
            cluster_id = f"defect_cluster_{c_idx + 1:04d}"

            dup_views = []
            for other in cluster[1:]:
                dup_views.append({
                    "crop_id": other.get("crop_id"),
                    "url": other.get("url") or other.get("crop_url"),
                    "frame_index": other.get("frame_index"),
                    "timestamp_s": other.get("timestamp_s"),
                    "confidence": other.get("confidence"),
                    "box": other.get("box"),
                    "reason": other.get("duplicate_reason", "Quan sát lặp")
                })

            primary["cluster_id"] = cluster_id
            primary["is_primary"] = True
            primary["is_duplicate"] = False
            primary["duplicate_count"] = len(cluster) - 1
            primary["duplicate_views"] = dup_views

            unique_items.append(primary)
            processed_all.append(primary)

            # Các ảnh trùng lặp được đánh dấu rõ ràng
            for other in cluster[1:]:
                other["cluster_id"] = cluster_id
                other["is_primary"] = False
                other["is_duplicate"] = True
                other["parent_cluster_id"] = cluster_id
                other["parent_crop_id"] = primary.get("crop_id")
                processed_all.append(other)

        return {
            "deduplicated_items": processed_all,
            "unique_items": unique_items,
            "total_items": len(items),
            "unique_count": len(unique_items),
            "duplicate_count": len(items) - len(unique_items)
        }
