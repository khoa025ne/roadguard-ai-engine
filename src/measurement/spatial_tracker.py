"""
src/measurement/spatial_tracker.py — Khử trùng lặp đa khung hình & Gom DefectObservation
========================================================================================
Theo dõi khuyết tật qua nhiều frame liên tiếp (AI08), tránh đếm 1 lỗi nhiều lần.
"""

import math
from typing import List, Dict, Any


class SpatialTracker:
    """
    Theo dõi đối tượng qua chuỗi frame và đề xuất gộp các quan sát trùng lặp.
    AI chỉ đề xuất (DefectObservation), quyền quyết định gộp thuộc về PM (AI08).
    """

    def __init__(self, max_distance_meters: float = 2.0, iou_threshold: float = 0.25):
        self.max_distance_meters = max_distance_meters
        self.iou_threshold = iou_threshold
        self.tracked_defects = []  # Danh sách các cụm khuyết tật duy nhất
        self._next_track_id = 1

    def haversine_distance_m(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Tính khoảng cách đường chim bay giữa 2 tọa độ WGS84 tính bằng mét."""
        R = 6371000.0  # Bán kính Trái Đất (m)
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)

        a = math.sin(delta_phi / 2.0) ** 2 + \
            math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        return R * c

    def update(self, frame_detections: List[Dict[str, Any]], frame_metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Cập nhật tracking cho frame mới.
        Gán track_id cho từng detection và gom vào danh sách observations.
        """
        gps = frame_metadata.get("gps")
        f_lat = gps["latitude"] if gps else 0.0
        f_lon = gps["longitude"] if gps else 0.0

        for det in frame_detections:
            matched_cluster = None
            det_type = det.get("defect_type_code", "pothole")

            if gps:
                # So khớp theo khoảng cách GPS mặt đất
                for cluster in self.tracked_defects:
                    if cluster["defect_type_code"] != det_type:
                        continue
                    dist = self.haversine_distance_m(f_lat, f_lon, cluster["latitude"], cluster["longitude"])
                    if dist <= self.max_distance_meters:
                        matched_cluster = cluster
                        break

            if matched_cluster:
                track_id = matched_cluster["track_id"]
                det["track_id"] = track_id
                matched_cluster["observations"].append({
                    "frame_index": frame_metadata.get("frame_index"),
                    "box": det["box"],
                    "confidence": det["confidence"]
                })
                # Cập nhật tọa độ trung bình
                n = len(matched_cluster["observations"])
                if gps:
                    matched_cluster["latitude"] = (matched_cluster["latitude"] * (n - 1) + f_lat) / n
                    matched_cluster["longitude"] = (matched_cluster["longitude"] * (n - 1) + f_lon) / n
            else:
                # Tạo cụm khuyết tật mới
                track_id = f"TRK_{self._next_track_id:04d}"
                self._next_track_id += 1
                det["track_id"] = track_id

                self.tracked_defects.append({
                    "track_id": track_id,
                    "defect_type_code": det_type,
                    "latitude": f_lat,
                    "longitude": f_lon,
                    "observations": [{
                        "frame_index": frame_metadata.get("frame_index"),
                        "box": det["box"],
                        "confidence": det["confidence"]
                    }]
                })

        return frame_detections

    def get_summary(self) -> List[Dict[str, Any]]:
        """Trả về danh sách các hư hỏng duy nhất sau khi khử trùng lặp."""
        return self.tracked_defects
