"""
tools/remap_merge.py — Remap Class ID và Hợp nhất Dataset về Taxonomy Chung
=============================================================================
Đọc taxonomy từ class_map.json (không hardcode class ID), remap nhãn của từng
dataset thành phần về ID chuẩn hóa, hợp nhất ảnh và nhãn vào thư mục data/merged/,
bảo toàn cấu trúc phân chia train/valid/test và sinh file data/merged/data.yaml.

Sử dụng:
    python tools/remap_merge.py
    python tools/remap_merge.py --dry-run
    python tools/remap_merge.py --output data/merged
"""

import os
import sys
import json
import shutil
import hashlib
import argparse
from pathlib import Path
from collections import Counter
import yaml

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
CLASS_MAP_FILE = WORKSPACE_ROOT / "class_map.json"


def load_taxonomy(class_map_path: Path = CLASS_MAP_FILE) -> tuple[dict[int, str], dict[str, int]]:
    """Đọc class_map.json tại root dự án, trả về (id_to_name, name_to_id)."""
    if not class_map_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file taxonomy tại: {class_map_path}")
    
    with open(class_map_path, "r", encoding="utf-8") as f:
        raw_map = json.load(f)
    
    id_to_name = {int(k): str(v) for k, v in raw_map.items()}
    name_to_id = {str(v): int(k) for k, v in raw_map.items()}
    return id_to_name, name_to_id


def resolve_dataset_class_mapping(
    dataset_yaml_path: Path,
    target_name_to_id: dict[str, int]
) -> dict[int, int]:
    """
    Đọc data.yaml của dataset nguồn, ánh xạ từng class ID nguồn sang class ID đích
    dựa vào tên lớp tương ứng trong taxonomy chung (hoàn toàn không hardcode ID).
    """
    if not dataset_yaml_path.exists():
        raise FileNotFoundError(f"Không tìm thấy data.yaml tại: {dataset_yaml_path}")

    with open(dataset_yaml_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    raw_names = cfg.get("names", [])
    src_id_to_name = {}
    if isinstance(raw_names, list):
        for idx, name in enumerate(raw_names):
            src_id_to_name[idx] = str(name).strip().lower()
    elif isinstance(raw_names, dict):
        for k, v in raw_names.items():
            src_id_to_name[int(k)] = str(v).strip().lower()
    else:
        raise ValueError(f"Định dạng 'names' không hợp lệ trong {dataset_yaml_path}")

    remap_dict = {}
    for src_id, src_name in src_id_to_name.items():
        if src_name in target_name_to_id:
            remap_dict[src_id] = target_name_to_id[src_name]
        else:
            raise ValueError(
                f"Lớp '{src_name}' (ID {src_id}) từ {dataset_yaml_path} không tồn tại trong class_map.json!"
            )
    return remap_dict


def compute_file_hash(path: Path) -> str:
    """Tính MD5 hash để kiểm tra trùng lặp nội dung ảnh."""
    hasher = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def merge_datasets(
    datasets_info: list[dict],
    output_dir: Path,
    target_id_to_name: dict[int, str],
    target_name_to_id: dict[str, int],
    deduplicate: bool = True,
    dry_run: bool = False
):
    print("=" * 75)
    print("🚀 BẮT ĐẦU TIẾN TRÌNH REMAP CLASS ID & HỢP NHẤT DATASET (MERGE)")
    print(f"📁 Thư mục xuất: {output_dir}")
    print(f"🎯 Taxonomy đích (class_map.json): {target_id_to_name}")
    print(f"⚙️ Chế độ khử trùng lặp (Deduplication): {'BẬT' if deduplicate else 'TẮT'}")
    print(f"⚙️ Chế độ chạy thử (Dry Run): {'BẬT' if dry_run else 'TẮT'}")
    print("=" * 75)

    splits = ["train", "valid", "test"]
    if not dry_run:
        for s in splits:
            (output_dir / s / "images").mkdir(parents=True, exist_ok=True)
            (output_dir / s / "labels").mkdir(parents=True, exist_ok=True)

    # Thống kê tổng hợp
    merged_stats = {
        s: {
            "images": 0,
            "labels": 0,
            "empty": 0,
            "classes": Counter(),
            "duplicates_skipped": 0,
        }
        for s in splits
    }

    # Bảng băm theo dõi trùng lặp ảnh theo từng split
    seen_hashes_by_split: dict[str, set[str]] = {s: set() for s in splits}
    seen_filenames_by_split: dict[str, set[str]] = {s: set() for s in splits}

    for d_idx, ds in enumerate(datasets_info, 1):
        ds_name = ds["name"]
        ds_root = Path(ds["path"])
        ds_yaml = ds_root / "data.yaml"
        remap_map = resolve_dataset_class_mapping(ds_yaml, target_name_to_id)

        print(f"\n📦 [{d_idx}/{len(datasets_info)}] Xử lý: {ds_name}")
        print(f"   - Thư mục nguồn: {ds_root}")
        print(f"   - Quy tắc Remap: {remap_map} ({', '.join(f'Lớp nguồn {k} -> Lớp đích {v}' for k, v in remap_map.items())})")

        for s in splits:
            src_img_dir = ds_root / s / "images"
            src_lbl_dir = ds_root / s / "labels"

            # Hỗ trợ trường hợp roboflow đặt tên folder 'val' thay vì 'valid'
            if not src_img_dir.exists():
                alt_split = "val" if s == "valid" else "valid"
                if (ds_root / alt_split / "images").exists():
                    src_img_dir = ds_root / alt_split / "images"
                    src_lbl_dir = ds_root / alt_split / "labels"

            if not src_img_dir.exists():
                continue

            img_files = sorted([f for f in src_img_dir.glob("*.*") if f.suffix.lower() in [".jpg", ".jpeg", ".png", ".bmp", ".webp"]])
            copied_in_split = 0
            skipped_in_split = 0

            for img_p in img_files:
                lbl_p = src_lbl_dir / f"{img_p.stem}.txt"
                f_hash = compute_file_hash(img_p) if deduplicate else None

                # Kiểm tra trùng lặp
                if deduplicate:
                    if f_hash in seen_hashes_by_split[s] or img_p.name in seen_filenames_by_split[s]:
                        skipped_in_split += 1
                        merged_stats[s]["duplicates_skipped"] += 1
                        continue
                    seen_hashes_by_split[s].add(f_hash)
                    seen_filenames_by_split[s].add(img_p.name)

                # Đọc và remap nhãn
                remapped_lines = []
                is_empty = True
                if lbl_p.exists():
                    content = lbl_p.read_text(encoding="utf-8", errors="ignore").strip()
                    if content:
                        is_empty = False
                        for line in content.splitlines():
                            parts = line.strip().split()
                            if parts:
                                try:
                                    old_cid = int(parts[0])
                                    new_cid = remap_map[old_cid]
                                    remapped_lines.append(f"{new_cid} {' '.join(parts[1:])}\n")
                                    merged_stats[s]["classes"][new_cid] += 1
                                except (ValueError, KeyError) as e:
                                    print(f"⚠️ Lỗi remap dòng nhãn '{line}' tại {lbl_p}: {e}")

                if is_empty:
                    merged_stats[s]["empty"] += 1

                # Sao chép và ghi file nếu không phải dry_run
                if not dry_run:
                    dest_img_p = output_dir / s / "images" / img_p.name
                    dest_lbl_p = output_dir / s / "labels" / f"{img_p.stem}.txt"
                    shutil.copy2(img_p, dest_img_p)
                    with open(dest_lbl_p, "w", encoding="utf-8") as f_lbl:
                        if remapped_lines:
                            f_lbl.writelines(remapped_lines)

                copied_in_split += 1
                merged_stats[s]["images"] += 1
                merged_stats[s]["labels"] += 1

            print(f"   👉 Split '{s}': Nạp {copied_in_split} ảnh | Bỏ qua {skipped_in_split} ảnh trùng lặp.")

    # Sinh file data.yaml cho thư mục merged
    yaml_dict = {
        "path": str(output_dir.resolve()).replace("\\", "/"),
        "train": "train/images",
        "val": "valid/images",
        "test": "test/images",
        "nc": len(target_id_to_name),
        "names": {int(k): str(v) for k, v in target_id_to_name.items()}
    }

    yaml_dest = output_dir / "data.yaml"
    if not dry_run:
        with open(yaml_dest, "w", encoding="utf-8") as f_y:
            yaml.dump(yaml_dict, f_y, default_flow_style=False, sort_keys=False)

    print("\n" + "=" * 75)
    print("📊 BẢNG TỔNG KẾT SAU KHI HỢP NHẤT (MERGED DATASET):")
    total_imgs_all = 0
    total_lbls_all = 0
    total_empty_all = 0
    total_classes_all = Counter()

    for s in splits:
        st = merged_stats[s]
        total_imgs_all += st["images"]
        total_lbls_all += st["labels"]
        total_empty_all += st["empty"]
        total_classes_all.update(st["classes"])
        print(f" - Split [{s:5s}]: {st['images']:,} ảnh | {st['labels']:,} file nhãn | {st['empty']:,} mẫu âm tính (0 byte)")
        print(f"     BBox: {dict(st['classes'])} (0={target_id_to_name.get(0)}, 1={target_id_to_name.get(1)}, 2={target_id_to_name.get(2)})")
        if deduplicate:
            print(f"     Đã lọc trùng: {st['duplicates_skipped']:,} ảnh trùng lặp.")

    print("-" * 75)
    print(f"🔥 TỔNG TOÀN BỘ DATASET: {total_imgs_all:,} ẢNH | {total_lbls_all:,} NHÃN | {total_empty_all:,} MẪU ÂM TÍNH")
    print(f"🎯 PHÂN BỐ LỚP TOÀN DIỆN:")
    for cid, cname in target_id_to_name.items():
        print(f"   - Class {cid} ({cname}): {total_classes_all[cid]:,} Bounding Boxes")
    if not dry_run:
        print(f"📄 File cấu hình YOLO: {yaml_dest.resolve()}")
    print("=" * 75)
    return merged_stats


def main():
    parser = argparse.ArgumentParser(description="Remap Class ID & Hợp nhất Dataset RoadGuard AI")
    parser.add_argument("--output", type=str, default="data/merged", help="Thư mục xuất dataset hợp nhất")
    parser.add_argument("--no-dedup", action="store_true", help="Không khử trùng lặp ảnh giữa các dataset")
    parser.add_argument("--dry-run", action="store_true", help="Chạy kiểm thử thống kê không ghi file")
    args = parser.parse_args()

    id_to_name, name_to_id = load_taxonomy()

    crack_unzipped = WORKSPACE_ROOT / "results" / "web_runs" / "task_ds_1790603381_f0cab9" / "unzipped"
    crack_in_data = WORKSPACE_ROOT / "data" / "road_crack"
    chosen_crack_path = crack_in_data if crack_in_data.exists() else crack_unzipped

    datasets_to_merge = [
        {
            "name": "unified_road_dataset_15k",
            "path": WORKSPACE_ROOT / "data" / "unified_road_dataset_15k",
        },
        {
            "name": "pothole_dataset_5k",
            "path": WORKSPACE_ROOT / "data" / "pothole_dataset_5k",
        },
        {
            "name": "road_crack (Roboflow v1)",
            "path": chosen_crack_path,
        },
    ]

    out_p = Path(args.output)
    if not out_p.is_absolute():
        out_p = WORKSPACE_ROOT / out_p

    merge_datasets(
        datasets_info=datasets_to_merge,
        output_dir=out_p,
        target_id_to_name=id_to_name,
        target_name_to_id=name_to_id,
        deduplicate=not args.no_dedup,
        dry_run=args.dry_run
    )


if __name__ == "__main__":
    main()
