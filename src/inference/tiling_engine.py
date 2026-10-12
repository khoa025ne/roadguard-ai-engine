"""
src/inference/tiling_engine.py — Cắt mảnh không gian & Hợp nhất xuyên Tile (Cross-Tile NMS)
========================================================================================
Giải quyết bài toán vết nứt mảnh milimet trên ảnh độ phân giải cao 2.7K (2720x1530).
"""

import cv2
import numpy as np
from typing import List, Tuple, Dict, Any


class TileSplitter:
    """
    Chia khung hình độ phân giải cao thành lưới tile 640x640 có overlap 20%.
    Ánh xạ ngược tọa độ và hợp nhất bằng Non-Maximum Suppression (NMS).
    """

    def __init__(self, tile_size: int = 640, overlap: float = 0.2):
        self.tile_size = tile_size
        self.overlap = overlap
        self.stride = int(tile_size * (1.0 - overlap))  # default 512px với 20% overlap

    def split_frame(self, image: np.ndarray) -> List[Tuple[np.ndarray, Tuple[int, int, int, int]]]:
        """
        Cắt ảnh lớn thành danh sách (tile_image, (x1, y1, x2, y2)).
        x1, y1, x2, y2 là tọa độ góc của tile trên khung hình gốc.
        """
        H, W = image.shape[:2]
        tiles = []

        y = 0
        while y < H:
            x = 0
            while x < W:
                x2 = min(x + self.tile_size, W)
                y2 = min(y + self.tile_size, H)
                x1 = max(0, x2 - self.tile_size)
                y1 = max(0, y2 - self.tile_size)

                tile = image[y1:y2, x1:x2]

                # Nếu tile sát mép nhỏ hơn 640x640, áp dụng zero padding
                if tile.shape[0] < self.tile_size or tile.shape[1] < self.tile_size:
                    padded = np.zeros((self.tile_size, self.tile_size, 3), dtype=np.uint8)
                    padded[:tile.shape[0], :tile.shape[1]] = tile
                    tile = padded

                tiles.append((tile, (x1, y1, x2, y2)))

                x += self.stride
                if x >= W:
                    break

            y += self.stride
            if y >= H:
                break

        return tiles

    def merge_detections(
        self,
        tile_detections: List[List[Dict[str, Any]]],
        tile_coords: List[Tuple[int, int, int, int]],
        iou_threshold: float = 0.45
    ) -> List[Dict[str, Any]]:
        """
        Ánh xạ tọa độ từng tile về không gian ảnh gốc 2.7K và chạy NMS để loại bỏ box trùng.
        """
        all_boxes = []
        all_scores = []
        all_class_ids = []
        all_metadata = []

        for dets, (x1, y1, x2, y2) in zip(tile_detections, tile_coords):
            for det in dets:
                bx1, by1, bx2, by2 = det["box"]
                # Dịch chuyển tọa độ theo offset của tile
                gx1 = bx1 + x1
                gy1 = by1 + y1
                gx2 = bx2 + x1
                gy2 = by2 + y1

                w = max(0, gx2 - gx1)
                h = max(0, gy2 - gy1)
                if w < 3 or h < 3:
                    continue

                all_boxes.append([gx1, gy1, w, h])  # định dạng cho cv2.dnn.NMSBoxes
                all_scores.append(float(det["confidence"]))
                all_class_ids.append(int(det["class_id"]))
                all_metadata.append(det)

        if not all_boxes:
            return []

        # Chạy Non-Maximum Suppression (NMS)
        indices = cv2.dnn.NMSBoxes(all_boxes, all_scores, score_threshold=0.2, nms_threshold=iou_threshold)
        merged = []

        if len(indices) > 0:
            indices = indices.flatten() if hasattr(indices, "flatten") else [i[0] for i in indices]
            for idx in indices:
                meta = all_metadata[idx]
                gx, gy, gw, gh = all_boxes[idx]
                meta_copy = {**meta}
                meta_copy["box"] = [gx, gy, gx + gw, gy + gh]
                meta_copy["box_xywh"] = [gx, gy, gw, gh]
                merged.append(meta_copy)

        return merged


class TargetBandClassifier:
    """
    Phân loại TargetBand tuân thủ quy tắc bất biến của Domain Model v1 (dòng 132):
    'TargetBand in {Surface, LeftEdge, RightEdge}; trái/phải nhìn theo chiều tăng lý trình, không đổi khi bay ngược.'
    """

    @staticmethod
    def calculate_azimuth_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Tính góc phương vị (Azimuth) giữa 2 tọa độ GPS (0 - 360 độ)."""
        import math
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        dlon_rad = math.radians(lon2 - lon1)

        y = math.sin(dlon_rad) * math.cos(lat2_rad)
        x = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlon_rad)
        azimuth_deg = (math.degrees(math.atan2(y, x)) + 360) % 360
        return azimuth_deg

    @staticmethod
    def is_forward_flight(flight_heading_deg: float, road_azimuth_deg: float) -> bool:
        """
        Kiểm tra drone bay xuôi chiều hay ngược chiều lý trình.
        Góc chênh lệch <= 90 độ -> Bay xuôi (True).
        Góc chênh lệch > 90 độ -> Bay ngược (False).
        """
        diff = abs(flight_heading_deg - road_azimuth_deg) % 360
        if diff > 180:
            diff = 360 - diff
        return diff <= 90.0

    @classmethod
    def classify(
        cls,
        box_xyxy: List[float],
        frame_width: int = 2720,
        is_forward: bool = True,
        left_ratio: float = 0.15,
        right_ratio: float = 0.85
    ) -> str:
        """
        Phân loại detection thuộc SURFACE, LEFT_EDGE hay RIGHT_EDGE.
        - box_xyxy: [x1, y1, x2, y2]
        - is_forward: True nếu bay xuôi chiều lý trình, False nếu bay ngược chiều lý trình.
        """
        x_center = (box_xyxy[0] + box_xyxy[2]) / 2.0
        ratio = x_center / float(frame_width)

        if ratio < left_ratio:
            cam_side = "CAM_LEFT"
        elif ratio > right_ratio:
            cam_side = "CAM_RIGHT"
        else:
            return "SURFACE"

        # Quy tắc Domain Model: Trái/phải nhìn theo chiều tăng lý trình, không đổi khi bay ngược
        if is_forward:
            return "LEFT_EDGE" if cam_side == "CAM_LEFT" else "RIGHT_EDGE"
        else:
            # Khi bay ngược: Mép trái của camera là mép phải của con đường theo chiều lý trình
            return "RIGHT_EDGE" if cam_side == "CAM_LEFT" else "LEFT_EDGE"


class ContextOverlapHandler:
    """Xử lý dải đệm biên giữa các ProcessingBlock/Segment (10-20% overlap)."""

    @staticmethod
    def is_overlap_detection(
        projected_station_m: float,
        start_station_m: float,
        end_station_m: float
    ) -> bool:
        """
        Trả về True nếu detection nằm ngoài phạm vi chính [start_station_m, end_station_m],
        tức nằm trong dải đệm biên (Context Overlap).
        """
        return (projected_station_m < start_station_m) or (projected_station_m > end_station_m)

