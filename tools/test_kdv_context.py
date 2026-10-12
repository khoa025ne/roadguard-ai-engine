import sys
import json
from pathlib import Path
import cv2
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

# Thêm đường dẫn gốc vào sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.curation.kdv_inspector import KDVInspector

def test_kdv_dual_view():
    print("=== KIỂM THỬ KTV AI (GPT-5.4 VISION) CHẾ ĐỘ DUAL-VIEW CONTEXT ===")
    inspector = KDVInspector()
    print(f"Trạng thái KTV Inspector: is_available = {inspector.is_available}, Model = {inspector.model}")
    
    # 1. Tìm hoặc tạo ảnh Overview giả lập hiện trường khảo sát mặt đường
    overview_path = Path("results/test_prediction.jpg")
    if not overview_path.exists():
        # Thử tìm ảnh bất kỳ trong results
        candidates = list(Path("results").glob("**/*.jpg"))
        if candidates:
            overview_path = candidates[0]
            
    print(f"Ảnh toàn cảnh Overview sử dụng: {overview_path}")
    
    # 2. Tìm các ảnh crop thực tế trong results
    crop_candidates = list(Path("results").glob("**/crop_*.jpg"))[:3]
    if not crop_candidates:
        print("Không tìm thấy ảnh crop có sẵn, sử dụng mẫu dự phòng.")
        return
        
    print(f"Tìm thấy {len(crop_candidates)} ảnh crop để thẩm định:")
    for c in crop_candidates:
        print(f" - {c.name}")
        
    # Tạo danh sách defect_items kèm Bounding Box mô phỏng trên ảnh Overview
    defect_items = [
        {
            "id": 1,
            "crop_path": str(crop_candidates[0]),
            "bbox": [100, 150, 260, 310],
            "class_name": "crack",
            "confidence": 0.88,
            "station_m": 12.5
        }
    ]
    if len(crop_candidates) > 1:
        defect_items.append({
            "id": 2,
            "crop_path": str(crop_candidates[1]),
            "bbox": [320, 200, 480, 360],
            "class_name": "pothole",
            "confidence": 0.91,
            "station_m": 18.2
        })
        
    road_metadata = {
        "road_name": "Đường trục chính nội bộ KCN (Mặt đường bê tông xi măng)",
        "road_width_m": 6.0,
        "pavement_type": "Tấm đan bê tông 4x5m có khe co giãn chèn bitum định kỳ"
    }
    
    print("\nĐang gửi dữ liệu phân tích Dual-View tới GPT-5.4 Vision...")
    results = inspector.inspect_with_context(
        overview_image=overview_path,
        defect_items=defect_items,
        road_metadata=road_metadata,
        batch_size=4
    )
    
    print("\n=== KẾT QUẢ PHÂN TÍCH TỰ NHIÊN CỦA KTV AI (GPT-5.4) ===")
    for i, res in enumerate(results, 1):
        print(f"\n--- KHUYẾT TẬT #{i} ---")
        print(f"Phán quyết: {'HỢP LỆ (LỖI THẬT)' if res.get('is_valid') else 'BÁO ĐỘNG GIẢ / LOẠI BỎ'}")
        print(f"Hành động sửa nhãn (Action): {res.get('action')}")
        print(f"Nhãn chi tiết: {res.get('fine_tag')} ({res.get('fine_tag_code')})")
        print(f"Cấp độ hư hại: {res.get('severity')}")
        print(f"Độ mở rộng: {res.get('crack_width_level')}")
        print(f"Nhận định kỹ thuật của KTV (reasoning):")
        print(f"  \"{res.get('reasoning')}\"")
        if res.get("recommendation"):
            print(f"Khuyến nghị công trình: {res.get('recommendation')}")

if __name__ == "__main__":
    test_kdv_dual_view()
