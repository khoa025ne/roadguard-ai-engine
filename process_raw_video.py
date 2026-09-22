"""
process_raw_video.py — CLI Tool Xử Lý Dữ Liệu Video Thô Từ Backend (RoadGuard AI)
================================================================================
Dùng để đọc, kiểm định chất lượng và phân tích video Flycam thành các báo cáo chuẩn.

CÁCH DÙNG:
  # 1. Phân tích trực tiếp từ file video và file SRT:
  python process_raw_video.py --video data/sample.mp4 --srt data/sample.srt --output results/run1

  # 2. Phân tích theo ProcessingInputManifest (JSON từ Backend ASP.NET Core):
  python process_raw_video.py --manifest manifest.json --output results/run1

  # 3. Xem báo cáo kiểm định chất lượng (Quality Gate) mà không cần chạy inference:
  python process_raw_video.py --video data/sample.mp4 --srt data/sample.srt --quality-check-only
"""

import sys
import json
import argparse
from pathlib import Path

# Thêm thư mục gốc vào path
sys.path.append(str(Path(__file__).parent))

from src.ingestion.raw_video_analyzer import RawVideoAnalyzer


def main():
    parser = argparse.ArgumentParser(description="Tool xử lý dữ liệu video thô RoadGuard AI")
    parser.add_argument("--video", type=str, default="", help="Đường dẫn file video .MP4")
    parser.add_argument("--srt", type=str, default="", help="Đường dẫn file phụ đề .SRT")
    parser.add_argument("--manifest", type=str, default="", help="Đường dẫn file ProcessingInputManifest.json từ BE")
    parser.add_argument("--model", type=str, default="weights/base/best.pt", help="Đường dẫn file model trọng số (.pt)")
    parser.add_argument("--output", type=str, default="results", help="Thư mục xuất báo cáo và ảnh crop")
    parser.add_argument("--conf", type=float, default=0.25, help="Ngưỡng confidence nhận diện")
    parser.add_argument("--job-id", type=str, default="", help="Mã định danh tác vụ (Backend Job ID)")
    parser.add_argument("--quality-check-only", action="store_true", help="Chỉ kiểm tra chất lượng video (Quality Gate)")
    parser.add_argument("--no-crops", action="store_true", help="Không lưu ảnh crop bằng chứng")
    parser.add_argument("--sample-rate", type=int, default=None, help="Trích xuất mỗi N frame (VD: 30 = 2fps cho 60fps vid)")
    parser.add_argument("--max-frames", type=int, default=None, help="Giới hạn số khung hình tối đa xử lý")
    args = parser.parse_args()

    video_path = args.video
    srt_path = args.srt
    job_id = args.job_id

    # Đọc manifest nếu có
    if args.manifest:
        m_file = Path(args.manifest)
        if not m_file.exists():
            print(f"❌ Không tìm thấy file manifest: {m_file}")
            sys.exit(1)
        with open(m_file, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)
            video_path = manifest_data.get("video_file_uri", video_path)
            srt_path = manifest_data.get("srt_file_uri", srt_path)
            job_id = manifest_data.get("processing_block_id", job_id)
            if "model_path" in manifest_data:
                args.model = manifest_data["model_path"]

    if not video_path:
        print("❌ Vui lòng cung cấp đường dẫn video bằng --video <file.mp4> hoặc --manifest <file.json>")
        sys.exit(1)

    analyzer = RawVideoAnalyzer(
        model_path=args.model,
        conf_threshold=args.conf
    )

    # Nếu chỉ kiểm tra chất lượng
    if args.quality_check_only:
        print(f"🔍 Đang kiểm định chất lượng video: {video_path}...")
        telemetries = analyzer.srt_parser.parse_file(srt_path) if srt_path else []
        report = analyzer.run_quality_gate(Path(video_path), telemetries)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        sys.exit(0 if report["can_proceed"] else 2)

    # Chạy phân tích toàn bộ
    analyzer.process_raw_video(
        video_path=video_path,
        srt_path=srt_path,
        output_dir=args.output,
        job_id=job_id,
        sample_every_n_frames=args.sample_rate,
        max_frames=args.max_frames,
        save_crops=not args.no_crops
    )


if __name__ == "__main__":
    main()
