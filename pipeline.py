"""
pipeline.py — Master CLI Runner cho Hệ Thống RoadGuard AI (Kiến Trúc A)
=======================================================================
Kết nối toàn bộ 7 giai đoạn tuyến tính:
  01_segment -> 02_detect -> 03_filter -> 04_dedup -> 05_measure -> 06_inspect -> 07_report

CÁCH SỬ DỤNG:
  # 1. Phân tích video flycam với mô hình 15k:
  python pipeline.py --video data/raw_videos/DJI_0057.MP4 --model weights/trained/roadguard_best_15k.pt --output outputs/reports/run1

  # 2. Phân tích video kèm file phụ đề viễn thám SRT:
  python pipeline.py --video flight.mp4 --srt flight.srt --output outputs/reports/flight_run

  # 3. Chạy chế độ giả lập (Mock mode cho Backend ASP.NET Core test nhanh):
  python pipeline.py --mock --output outputs/reports/mock_run
"""

import sys
import json
import argparse
from pathlib import Path

# Thêm root vào path
sys.path.append(str(Path(__file__).resolve().parent))

from src.pipeline.pipeline import run_video_analysis_task, LinearPipeline, load_pipeline_config
from src.contracts.mock_ai_adapter import MockAIAdapter


def main():
    parser = argparse.ArgumentParser(description="RoadGuard AI — Linear Pipeline Runner (Kiến Trúc A)")
    parser.add_argument("--video", type=str, default="", help="Đường dẫn file video (.mp4)")
    parser.add_argument("--srt", type=str, default="", help="Đường dẫn file phụ đề telemetry (.srt)")
    parser.add_argument("--model", type=str, default="weights/trained/roadguard_best_15k.pt", help="Đường dẫn file trọng số model (.pt)")
    parser.add_argument("--output", type=str, default="outputs/reports", help="Thư mục xuất báo cáo")
    parser.add_argument("--conf", type=float, default=0.25, help="Ngưỡng confidence nhận diện")
    parser.add_argument("--fps", type=int, default=2, help="Tần suất trích xuất khung hình (FPS)")
    parser.add_argument("--duration", type=int, default=30, help="Số giây tối đa cần phân tích (0 = toàn bộ)")
    parser.add_argument("--no-tiling", action="store_true", help="Không dùng tiling 640x640")
    parser.add_argument("--config", type=str, default="configs/pipeline.yaml", help="Đường dẫn file config pipeline")
    parser.add_argument("--mock", action="store_true", help="Chạy chế độ mock cho kiểm thử Backend")
    args = parser.parse_args()

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("🚀 ROADGUARD AI — KIẾN TRÚC A (LINEAR PIPELINE 7 STAGES)")
    print("=" * 70)

    # Chế độ Mock Adapter
    if args.mock:
        print("ℹ️ Chế độ Mock Adapter: Đang sinh dữ liệu giả lập cho Backend...")
        adapter = MockAIAdapter()
        res = adapter.process_mock_job(processing_job_id="job-mock-test-001")
        out_file = out_dir / "inspection_report.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2, ensure_ascii=False)
        print(f"✅ Đã tạo kết quả mock tại: {out_file}")
        print("=" * 70)
        return

    if not args.video:
        print("❌ Vui lòng chỉ định đường dẫn video bằng cờ --video <path.mp4> hoặc --mock.")
        print("Ví dụ: python pipeline.py --video data/raw_videos/DJI_0057.MP4")
        sys.exit(1)

    print(f"📹 Video đầu vào: {args.video}")
    if args.srt:
        print(f"🛰️ Telemetry SRT: {args.srt}")
    print(f"🧠 Trọng số AI  : {args.model}")
    print(f"📁 Thư mục xuất : {args.output}")
    print("-" * 70)

    try:
        report = run_video_analysis_task(
            video_path=args.video,
            model_path=args.model,
            output_dir=args.output,
            srt_path=args.srt if args.srt else None,
            conf_threshold=args.conf,
            max_duration_seconds=args.duration,
            sampling_rate_fps=args.fps,
            use_tiling=not args.no_tiling,
            config_path=args.config
        )
        print("=" * 70)
        print("✅ HOÀN TẤT PHÂN TÍCH!")
        summary = report.get("summary", {})
        print(f"🎯 Tổng khuyết tật: {summary.get('total_detections', 0)}")
        print(f"   - Ổ gà (pothole): {summary.get('pothole_count', 0)}")
        print(f"   - Vết nứt (crack): {summary.get('crack_count', 0)}")
        print(f"   - Khẩn cấp (critical): {summary.get('critical_count', 0)}")
        print(f"📄 Báo cáo JSON: {out_dir / 'inspection_report.json'}")
        print("=" * 70)
    except Exception as e:
        print(f"❌ Xảy ra lỗi khi chạy pipeline: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
