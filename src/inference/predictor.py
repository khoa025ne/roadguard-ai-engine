"""
src/inference/predictor.py — Module thực thi mô hình YOLOv11 & Trực quan hóa
===========================================================================
Tải trọng số mô hình (weights), suy luận trên ảnh/tile và vẽ kết quả bằng chứng.
"""

import cv2
import numpy as np
from pathlib import Path
from ultralytics import YOLO
from typing import List, Dict, Any, Optional
from .tiling_engine import TileSplitter


class RoadDefectPredictor:
    """Wrapper cho YOLOv11 phát hiện khuyết tật mặt đường."""

    # Màu sắc nhận diện trực quan theo lớp đối tượng
    CLASS_COLORS = {
        0: (0, 0, 255),      # pothole       -> Đỏ
        1: (0, 165, 255),    # longitudinal  -> Cam
        2: (0, 255, 255),    # transverse    -> Vàng
        3: (0, 255, 0),      # alligator     -> Xanh lá
        4: (255, 0, 255),    # edge_crack    -> Tím
        5: (255, 0, 0),      # block_crack   -> Xanh dương
        6: (128, 0, 128),    # spalling      -> Tím đậm
        7: (200, 200, 0),    # raveling      -> Vàng xanh
    }

    CLASS_NAMES_VN = {
        0: "Ổ gà",
        1: "Nứt dọc",
        2: "Nứt ngang",
        3: "Nứt chân chim",
        4: "Nứt mép",
        5: "Nứt ô",
        6: "Bong tróc BT",
        7: "Tróc hạt",
    }

    def __init__(self, model_path: str | Path, conf_threshold: float = 0.25):
        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise FileNotFoundError(f"Không tìm thấy file trọng số: {self.model_path}")

        self.model = YOLO(str(self.model_path))
        self.conf_threshold = conf_threshold
        self.tiler = TileSplitter(tile_size=640, overlap=0.2)

    def predict_tile(self, tile_img: np.ndarray) -> List[Dict[str, Any]]:
        """Inference trên 1 tile 640x640 duy nhất."""
        results = self.model.predict(
            source=tile_img,
            conf=self.conf_threshold,
            verbose=False,
            imgsz=640
        )
        detections = []
        if not results:
            return detections

        r = results[0]
        boxes = r.boxes
        if boxes is None or len(boxes) == 0:
            return detections

        for i in range(len(boxes)):
            xyxy = boxes.xyxy[i].cpu().numpy().astype(int).tolist()
            conf = float(boxes.conf[i].cpu().numpy())
            cls_id = int(boxes.cls[i].cpu().numpy())
            cls_name = self.model.names.get(cls_id, str(cls_id))

            detections.append({
                "class_id": cls_id,
                "class_name": cls_name,
                "confidence": round(conf, 4),
                "box": xyxy
            })

        return detections

    def predict_full_frame(self, frame_img: np.ndarray, use_tiling: bool = True) -> List[Dict[str, Any]]:
        """
        Inference trên ảnh độ phân giải cao bằng kỹ thuật cắt tile kết hợp NMS.
        """
        if not use_tiling or frame_img.shape[1] <= 640:
            return self.predict_tile(frame_img)

        # 1. Cắt mảnh
        tiles_with_coords = self.tiler.split_frame(frame_img)

        tile_imgs = [t[0] for t in tiles_with_coords]
        tile_coords = [t[1] for t in tiles_with_coords]

        # 2. Batch inference trên từng tile
        tile_detections = []
        for img in tile_imgs:
            tile_detections.append(self.predict_tile(img))

        # 3. Gom box xuyên tile về không gian gốc
        merged_detections = self.tiler.merge_detections(
            tile_detections,
            tile_coords,
            iou_threshold=0.45
        )
        return merged_detections

    def visualize(
        self,
        image: np.ndarray,
        detections: List[Dict[str, Any]],
        output_path: Optional[str | Path] = None
    ) -> np.ndarray:
        """Vẽ bounding box, nhãn và confidence lên ảnh."""
        vis = image.copy()
        for det in detections:
            x1, y1, x2, y2 = det["box"]
            cls_id = det["class_id"]
            conf = det["confidence"]
            label_vn = self.CLASS_NAMES_VN.get(cls_id, det["class_name"])
            color = self.CLASS_COLORS.get(cls_id, (0, 255, 0))

            # Vẽ box
            cv2.rectangle(vis, (x1, y1), (x2, y2), color, 2)

            # Vẽ tag nhãn
            text = f"{label_vn} {conf:.2f}"
            if "width_mm" in det:
                text += f" | {det['width_mm']:.0f}mm"

            (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(vis, (x1, max(0, y1 - th - 6)), (x1 + tw + 4, y1), color, -1)
            cv2.putText(vis, text, (x1 + 2, max(th, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        if output_path:
            cv2.imwrite(str(output_path), vis)

        return vis
