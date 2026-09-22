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
