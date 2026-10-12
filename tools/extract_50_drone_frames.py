"""
tools/extract_50_drone_frames.py — Trích Xuất 50 Khung Hình Drone Thật
=====================================================================
Trích xuất 50 frames đại diện đa dạng góc quay, bóng râm, mép cỏ, vỉa hè
từ 4 video flycam thực tế tại Việt Nam (data/raw_videos/*.MP4).
"""

import sys
import cv2
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.append(str(WORKSPACE))

from src.utils.io import safe_imwrite
RAW_VIDEOS_DIR = WORKSPACE / "data" / "raw_videos"
OUTPUT_DIR = WORKSPACE / "outputs" / "drone_benchmark_50_frames"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Kế hoạch lấy mẫu 50 frames
video_plan = [
    {"name": "DJI_0057.MP4", "count": 15},
    {"name": "DJI_0059.MP4", "count": 10},
    {"name": "DJI_0061.MP4", "count": 15},
    {"name": "DJI_0064.MP4", "count": 10},
]

total_saved = 0

print("=" * 70)
print("🚀 BẮT ĐẦU TRÍCH XUẤT 50 KHUNG HÌNH FLYCAM ĐẠI DIỆN ĐA DẠNG...")
print(f"📁 Thư mục lưu: {OUTPUT_DIR}")
print("=" * 70)

for plan in video_plan:
    v_name = plan["name"]
    v_path = RAW_VIDEOS_DIR / v_name
    count_to_extract = plan["count"]

    if not v_path.exists():
        print(f"⚠️ Không tìm thấy {v_name}, bỏ qua.")
        continue

    cap = cv2.VideoCapture(str(v_path))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)

    # Lấy mẫu cách đều, bỏ 5% đầu và 5% cuối
    start_frame = int(total_frames * 0.05)
    end_frame = int(total_frames * 0.95)
    step = max(1, (end_frame - start_frame) // count_to_extract)

    saved_for_video = 0
    for idx in range(count_to_extract):
        target_f = start_frame + idx * step
        cap.set(cv2.CAP_PROP_POS_FRAMES, target_f)
        ret, frame = cap.read()
        if not ret:
            break

        timestamp_s = target_f / fps if fps > 0 else 0
        stem = v_path.stem
        out_name = f"{stem}_frame_{target_f:05d}_t{int(timestamp_s)}s.jpg"
        out_path = OUTPUT_DIR / out_name

        from src.utils.io import safe_imwrite
        safe_imwrite(out_path, frame)
        saved_for_video += 1
        total_saved += 1

    cap.release()
    print(f"✓ Video {v_name}: Đã trích xuất {saved_for_video} frames (từ {total_frames} frames, {total_frames/fps:.1f}s)")

print("-" * 70)
print(f"🎉 HOÀN TẤT! Đã trích xuất tổng cộng {total_saved} frames vào {OUTPUT_DIR}")
print("=" * 70)
