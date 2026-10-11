"""
tools/create_video_from_dataset.py — Ghép chuỗi ảnh Dataset thành Video Kiểm thử Thực tế
========================================================================================
Tạo video MP4 từ các ảnh khuyết tật (ổ gà, vết nứt, mặt đường sạch) trong dataset
để đưa trực tiếp vào Test Bench UI kiểm tra hiệu năng nhận diện của mô hình.
"""

import sys
import cv2
import numpy as np
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DATASET_IMG_DIR = Path("F:/train AI đồ án/data/unified_road_dataset_15k/test/images")
OUTPUT_DIR = Path("F:/train AI đồ án/results/test_videos")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_VIDEO_PATH = OUTPUT_DIR / "dataset_road_survey_test.mp4"


def letterbox_image(img, target_w=1280, target_h=720):
    """Giữ nguyên tỷ lệ ảnh và thêm viền đen (padding) để khớp kích thước video chuẩn."""
    h, w = img.shape[:2]
    scale = min(target_w / w, target_h / h)
    new_w, new_h = int(w * scale), int(h * scale)
    resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

    canvas = np.zeros((target_h, target_w, 3), dtype=np.uint8)
    top = (target_h - new_h) // 2
    left = (target_w - new_w) // 2
    canvas[top:top + new_h, left:left + new_w] = resized
    return canvas


def main():
    print("=" * 65)
    print("[ROADGUARD AI] GHEP CHUOI ANH THANH VIDEO KIEM THU MP4")
    print("=" * 65)

    if not DATASET_IMG_DIR.exists():
        print(f"❌ Không tìm thấy thư mục ảnh: {DATASET_IMG_DIR}")
        return

    # Quét ảnh
    all_imgs = sorted(list(DATASET_IMG_DIR.glob("*.jpg")) + list(DATASET_IMG_DIR.glob("*.png")))
    print(f"📦 Tìm thấy tổng cộng: {len(all_imgs)} ảnh trong tập dữ liệu.")

    # Lấy phân loại: pothole, crack, và nền sạch (để video sinh động và đa dạng)
    pothole_imgs = [p for p in all_imgs if not p.name.startswith("crack_") and not p.name.startswith("neg_")]
    crack_imgs = [p for p in all_imgs if p.name.startswith("crack_")]
    neg_imgs = [p for p in all_imgs if p.name.startswith("neg_")]

    print(f"   • Ảnh Ổ gà (Potholes):   {len(pothole_imgs)} ảnh")
    print(f"   • Ảnh Vết nứt (Cracks):  {len(crack_imgs)} ảnh")
    print(f"   • Ảnh Mặt đường sạch:    {len(neg_imgs)} ảnh")

    # Chọn xen kẽ 60 ảnh đại diện (khoảng 30 giây video với 2 fps)
    selected_sequence = []
    max_count = 20
    for i in range(max_count):
        if i < len(pothole_imgs):
            selected_sequence.append(pothole_imgs[i])
        if i < len(crack_imgs):
            selected_sequence.append(crack_imgs[i])
        if i < len(neg_imgs):
            selected_sequence.append(neg_imgs[i])

    print(f"🎯 Đã chọn chuỗi {len(selected_sequence)} ảnh đại diện để tạo video.")

    # Cấu hình video: 1280x720, 2 khung hình mỗi ảnh để mô phỏng flycam bay quét (1 fps chuyển cảnh, video 10 fps mượt)
    target_w, target_h = 1280, 720
    video_fps = 10  # 10 fps
    frames_per_image = 10  # mỗi ảnh hiển thị 1.0 giây (10 frames)

    # Thử codec avc1 hoặc mp4v
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(OUTPUT_VIDEO_PATH), fourcc, video_fps, (target_w, target_h))

    for idx, img_p in enumerate(selected_sequence):
        try:
            img = cv2.imdecode(np.fromfile(str(img_p), dtype=np.uint8), cv2.IMREAD_COLOR)
        except Exception:
            continue
        if img is None:
            continue

        frame = letterbox_image(img, target_w, target_h)

        # Chèn watermark telemetry mô phỏng trên góc video
        cv2.putText(
            frame,
            f"RoadGuard AI Synthetic Flight | Frame {idx+1}/{len(selected_sequence)} | {img_p.name[:25]}",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 255),
            2
        )

        for _ in range(frames_per_image):
            out.write(frame)

    out.release()
    print("=" * 65)
    print(f"[SUCCESS] DA TAO VIDEO THANH CONG: {OUTPUT_VIDEO_PATH}")
    file_size_mb = round(OUTPUT_VIDEO_PATH.stat().st_size / (1024 * 1024), 2)
    print(f"Dung luong: {file_size_mb} MB | Thoi luong: ~{len(selected_sequence)} giay.")
    print("=" * 65)


if __name__ == "__main__":
    main()
