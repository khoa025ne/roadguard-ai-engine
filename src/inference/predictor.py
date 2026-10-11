"""
src/inference/predictor.py — Module thực thi mô hình YOLOv11 & Trực quan hóa
===========================================================================
Tải trọng số mô hình (weights), suy luận trên ảnh/tile và vẽ kết quả bằng chứng.
"""

import json
import cv2
import numpy as np
from pathlib import Path
from ultralytics import YOLO
from typing import List, Dict, Any, Optional
from .tiling_engine import TileSplitter


class RoadDefectPredictor:
    """Wrapper cho YOLOv11 phát hiện khuyết tật mặt đường."""

    NAME_TO_VN = {
        "pothole": "Ổ gà",
        "crack": "Vết nứt",
        "bong_troc": "Bong tróc",
        "longitudinal": "Nứt dọc",
        "transverse": "Nứt ngang",
        "alligator": "Nứt chân chim",
        "edge_crack": "Nứt mép",
        "block_crack": "Nứt ô",
        "spalling": "Bong tróc BT",
        "raveling": "Tróc hạt",
    }

    # Bảng màu trực quan theo chu kỳ palette
    PALETTE = [
        (0, 0, 255),      # Đỏ (pothole - ID 0)
        (0, 165, 255),    # Cam (crack - ID 1)
        (255, 0, 255),    # Tím hồng (bong_troc - ID 2)
        (0, 255, 0),      # Xanh lá
        (255, 255, 0),    # Vàng
        (255, 0, 0),      # Xanh dương
    ]

    @classmethod
    def load_class_map(cls, custom_path: Optional[str | Path] = None) -> Dict[int, str]:
        """Tải class_map.json động từ thư mục gốc, hoàn toàn không hardcode class ID."""
        if custom_path is not None and Path(custom_path).exists():
            with open(custom_path, "r", encoding="utf-8") as f:
                return {int(k): str(v) for k, v in json.load(f).items()}

        cur = Path(__file__).resolve().parent
        candidates = [
            cur.parent.parent / "class_map.json",
            Path("class_map.json").resolve(),
        ]
        for c in candidates:
            if c.exists():
                try:
                    with open(c, "r", encoding="utf-8") as f:
                        return {int(k): str(v) for k, v in json.load(f).items()}
                except Exception as e:
                    import warnings
                    warnings.warn(f"[RoadDefectPredictor] Không thể đọc {c}: {e}", UserWarning)
        import warnings
        warnings.warn(
            "[RoadDefectPredictor] CẢNH BÁO: Không tìm thấy file 'class_map.json'! "
            "Đang sử dụng cấu hình lớp dự phòng mặc định {0: 'pothole', 1: 'crack', 2: 'bong_troc'}. "
            "Vui lòng tạo hoặc chỉ định class_map.json để tránh sai lệch nhãn mô hình.",
            UserWarning
        )
        return {0: "pothole", 1: "crack", 2: "bong_troc"}

    def __init__(
        self,
        model_path: str | Path,
        conf_threshold: float = 0.25,
        class_map_path: Optional[str | Path] = None
    ):
        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise FileNotFoundError(f"Không tìm thấy file trọng số: {self.model_path}")

        self.class_map = self.load_class_map(class_map_path)
        self.model = YOLO(str(self.model_path))
        self.conf_threshold = conf_threshold
        self.tiler = TileSplitter(tile_size=640, overlap=0.2)

    def get_class_color(self, cls_id: int) -> tuple[int, int, int]:
        """Lấy mã màu BGR cho class_id từ PALETTE mà không hardcode."""
        return self.PALETTE[cls_id % len(self.PALETTE)]

    def get_class_name(self, cls_id: int) -> str:
        """Lấy tên tiếng Anh chuẩn hóa từ class_map.json hoặc model.names."""
        return self.class_map.get(cls_id, self.model.names.get(cls_id, f"class_{cls_id}"))

    def get_class_name_vn(self, cls_id: int) -> str:
        """Lấy tên tiếng Việt tương ứng."""
        eng_name = self.get_class_name(cls_id)
        return self.NAME_TO_VN.get(eng_name, eng_name)

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
            cls_name = self.get_class_name(cls_id)

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
            label_vn = self.get_class_name_vn(cls_id)
            color = self.get_class_color(cls_id)

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
