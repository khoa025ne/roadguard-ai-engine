"""
tools/eval_dataset_zip.py — CLI Tool Quét & Đánh Giá Hiệu Năng Dataset (ZIP / Folder)
=====================================================================================
Sử dụng:
    python tools/eval_dataset_zip.py --zip path/to/dataset.zip
    python tools/eval_dataset_zip.py --folder path/to/image_folder --max-images 50
"""

import sys
import argparse
import time
from pathlib import Path

# Thêm thư mục gốc vào PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding='utf-8')

from src.ingestion.dataset_scanner import DatasetScanner
from src.inference.predictor import RoadDefectPredictor


def main():
    parser = argparse.ArgumentParser(
        description="Tool tự động giải nén, quét ảnh và đánh giá hiệu năng phát hiện khuyết tật trên Dataset (.ZIP / Folder)."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--zip", type=str, help="Đường dẫn tới file dataset dạng nén .ZIP")
    group.add_argument("--folder", type=str, help="Đường dẫn tới thư mục chứa ảnh trực tiếp")

    parser.add_argument(
        "--model", type=str, default="weights/trained/roadguard_best_15k.pt",
        help="Đường dẫn file trọng số YOLO (Mặc định: weights/trained/roadguard_best_15k.pt)"
    )
    parser.add_argument(
        "--conf", type=float, default=0.25,
        help="Ngưỡng tin cậy confidence threshold (Mặc định: 0.25)"
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Thư mục xuất kết quả (Mặc định: results/dataset_eval_<timestamp>)"
    )
    parser.add_argument(
        "--max-images", type=int, default=None,
        help="Giới hạn số lượng ảnh quét tối đa để test nhanh (Ví dụ: 50, 100)"
    )

    args = parser.parse_args()

    print("=" * 75)
    print("🚀 ROADGUARD DATASET SCANNER & PERFORMANCE EVALUATOR")
    print("=" * 75)

    # 1. Kiểm tra mô hình
    model_path = Path(args.model)
    if not model_path.exists():
        fallback_model = Path("weights/trained/crack_best.pt")
        if fallback_model.exists():
            print(f"⚠️ Không thấy {model_path}, chuyển sang dùng {fallback_model}")
            model_path = fallback_model
        else:
            print(f"❌ LỖI: Không tìm thấy file trọng số: {model_path}")
            sys.exit(1)

    print(f"• Mô hình sử dụng: {model_path}")
    print(f"• Ngưỡng Confidence: {args.conf}")

    t0_load = time.time()
    predictor = RoadDefectPredictor(model_path=str(model_path), conf_threshold=args.conf)
    print(f"✓ Đã tải mô hình YOLO ({((time.time() - t0_load) * 1000):.1f} ms)")

    # 2. Chuẩn bị thư mục xuất
    if args.output:
        out_dir = Path(args.output)
    else:
        out_dir = Path(f"results/dataset_eval_{int(time.time())}")
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"• Thư mục lưu kết quả: {out_dir}")

    scanner = DatasetScanner(predictor=predictor)

    # 3. Nạp danh sách ảnh
    image_paths = []
    if args.zip:
        zip_path = Path(args.zip)
        print(f"\n[1/3] Đang giải nén an toàn file: {zip_path.name}...")
        extract_dir = out_dir / "unzipped"
        t0_zip = time.time()
        image_paths = scanner.extract_zip(zip_path, extract_dir)
        print(f"✓ Giải nén xong trong {(time.time() - t0_zip):.2f}s")
        print(f"✓ Tìm thấy tổng cộng {len(image_paths)} file ảnh hợp lệ")
    else:
        folder_path = Path(args.folder)
        print(f"\n[1/3] Đang quét đệ quy thư mục: {folder_path}...")
        image_paths = scanner.find_images_in_folder(folder_path)
        print(f"✓ Tìm thấy tổng cộng {len(image_paths)} file ảnh hợp lệ")

    if not image_paths:
        print("❌ Không tìm thấy file ảnh nào để đánh giá!")
        sys.exit(1)

    if args.max_images and len(image_paths) > args.max_images:
        print(f"• Giới hạn quét: {args.max_images} / {len(image_paths)} ảnh")
        image_paths = image_paths[:args.max_images]

    # 4. Quét từng ảnh và đánh giá hiệu năng
    print(f"\n[2/3] Đang tiến hành quét và phân tích khuyết tật...")
    def print_progress(current, total, filename):
        pct = (current / total) * 100
        bar = "█" * int(pct // 4) + "-" * (25 - int(pct // 4))
        print(f"\r  [{bar}] {pct:5.1f}% ({current}/{total}) - {filename[:30]:<30}", end="", flush=True)

    t0_scan = time.time()
    report = scanner.scan_images(
        image_paths=image_paths,
        output_dir=out_dir,
        predictor=predictor,
        progress_callback=print_progress
    )
    scan_duration = time.time() - t0_scan
    print(f"\n✓ Quét hoàn tất trong {scan_duration:.2f} giây")

    # 5. In bảng báo cáo tổng kết
    summary = report["summary"]
    total_imgs = str(summary['total_images'])
    defect_imgs = f"{summary['defect_images']} ảnh"
    hit_rate_str = f"Hit Rate: {summary['hit_rate_pct']} %"
    clean_imgs = f"{summary['clean_images']} ảnh"
    total_defects = f"{summary['total_defects_found']} mục"
    cracks_str = f"{summary['crack_count']} vết"
    potholes_str = f"{summary['pothole_count']} hố"
    latency_str = f"{summary['avg_latency_ms']} ms"
    fps_str = f"~{summary['fps']} FPS"
    crops_str = f"{summary['total_crops_generated']} ảnh"

    print("\n" + "=" * 75)
    print("📊 BẢNG TỔNG KẾT ĐÁNH GIÁ HIỆU NĂNG DATASET")
    print("=" * 75)
    print(f"{'Chỉ Số Đo Lường':<38} | {'Giá Trị':<18} | {'Ghi Chú':<15}")
    print("-" * 75)
    print(f"{'1. Tổng số ảnh quét':<38} | {total_imgs:<18} | {'Tập dữ liệu':<15}")
    print(f"{'2. Số ảnh PHÁT HIỆN THÀNH CÔNG':<38} | {defect_imgs:<18} | {hit_rate_str:<15}")
    print(f"{'3. Số ảnh MẶT ĐƯỜNG SẠCH (Clean)':<38} | {clean_imgs:<18} | {'Âm tính':<15}")
    print(f"{'4. Tổng số khuyết tật tìm thấy':<38} | {total_defects:<18} | {'Tất cả các lớp':<15}")
    print(f"{'   - Vết nứt (Crack)':<38} | {cracks_str:<18} | {'Nứt dọc/ngang/lưới':<15}")
    print(f"{'   - Ổ gà (Pothole)':<38} | {potholes_str:<18} | {'Hố nông/sâu':<15}")
    print(f"{'5. Tốc độ trung bình / ảnh':<38} | {latency_str:<18} | {fps_str:<15}")
    print(f"{'6. Số ảnh cận cảnh đã cắt (Crops)':<38} | {crops_str:<18} | {'Sẵn sàng KDV':<15}")
    print("=" * 75)
    print(f"📁 Báo cáo chi tiết: {report.get('report_file')}")
    print(f"🖼️ Ảnh vẽ BBox: {out_dir / 'visualizations'}")
    print(f"✂️ Ảnh cắt cận cảnh: {out_dir / 'crops'}")
    print("=" * 75)


if __name__ == "__main__":
    main()
