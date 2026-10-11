"""
tools/cleanup_tasks.py — Công Cụ Dọn Dẹp Định Kỳ Thư Mục Task Web Runs Theo RETENTION
====================================================================================
Tự động quét results/web_runs/, bảo vệ các task có junction trỏ tới hoặc được ghi trong docs,
giữ lại N task mới nhất và chuyển các task cũ vào _trash_YYYYMMDD/.

Cách dùng:
    python tools/cleanup_tasks.py --dry-run
    python tools/cleanup_tasks.py --keep 5
"""

import os
import sys
import time
import shutil
import argparse
from pathlib import Path
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
WEB_RUNS_DIR = WORKSPACE_ROOT / "results" / "web_runs"

# Danh sách task bảo vệ vĩnh viễn (do junction trỏ tới hoặc tài liệu tham chiếu)
PERMANENT_PROTECTED = {
    "task_ds_1790603381_f0cab9",  # Đích đến của NTFS Junction data/road_crack
    "task_1791271365_faa20d",     # Mẫu test API trong docs/project_export/03_api_ui.md
}


def find_junction_targets() -> set[str]:
    """Tìm tất cả các target task được trỏ bởi Junction trong thư mục data/."""
    targets = set()
    data_dir = WORKSPACE_ROOT / "data"
    if not data_dir.exists():
        return targets

    for item in data_dir.iterdir():
        try:
            # Kiểm tra nếu là junction/reparse point
            if item.is_symlink() or (item.stat().st_file_attributes & 0x0400):
                resolved = str(item.resolve())
                if "web_runs" in resolved:
                    for part in resolved.split(os.sep):
                        if part.startswith("task_"):
                            targets.add(part)
        except Exception:
            pass
    return targets


def main():
    parser = argparse.ArgumentParser(description="Dọn dẹp định kỳ results/web_runs theo chính sách RETENTION")
    parser.add_argument("--keep", type=int, default=5, help="Số lượng task mới nhất cần giữ lại (mặc định: 5)")
    parser.add_argument("--dry-run", action="store_true", help="Chỉ quét và in thống kê, không di chuyển file")
    args = parser.parse_args()

    if not WEB_RUNS_DIR.exists():
        print(f"Thư mục {WEB_RUNS_DIR} không tồn tại.")
        return

    junction_targets = find_junction_targets()
    protected_set = PERMANENT_PROTECTED.union(junction_targets)

    # Liệt kê tất cả task folders
    tasks = []
    for item in WEB_RUNS_DIR.iterdir():
        if item.is_dir() and item.name.startswith("task_"):
            tasks.append({
                "name": item.name,
                "path": item,
                "mtime": item.stat().st_mtime,
                "mtime_str": datetime.fromtimestamp(item.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            })

    # Sắp xếp mới nhất lên trước
    tasks.sort(key=lambda x: x["mtime"], reverse=True)

    keep_count = max(1, args.keep)
    top_n_names = set(t["name"] for t in tasks[:keep_count])

    tasks_to_keep = []
    tasks_to_trash = []

    for t in tasks:
        t_name = t["name"]
        if t_name in top_n_names or t_name in protected_set:
            tasks_to_keep.append(t)
        else:
            tasks_to_trash.append(t)

    print("=" * 70)
    print("🧹 ROADGUARD TASK CLEANUP TOOL (RETENTION POLICY)")
    print(f"📂 Thư mục kiểm tra: {WEB_RUNS_DIR}")
    print(f"🎯 Quy tắc giữ lại  : {keep_count} task mới nhất + Task Junction/Docs bảo vệ")
    print(f"📊 Tổng số task     : {len(tasks)}")
    print(f"✅ Số task GIỮ LẠI  : {len(tasks_to_keep)}")
    print(f"🗑️ Số task DI DỜI   : {len(tasks_to_trash)}")
    print("=" * 70)

    print("\n[DANH SÁCH GIỮ LẠI]:")
    for t in tasks_to_keep:
        note = " (⛔ Junction / Docs Protected)" if t["name"] in protected_set else ""
        print(f"  🟢 {t['name']:<35} ({t['mtime_str']}){note}")

    if not tasks_to_trash:
        print("\n✨ Không có task nào cần dọn dẹp. Dung lượng đang ở trạng thái tối ưu.")
        return

    print(f"\n[DANH SÁCH DI CHUYỂN VÀO _trash_]:")
    for t in tasks_to_trash:
        print(f"  🗑️ {t['name']:<35} ({t['mtime_str']})")

    if args.dry_run:
        print("\nℹ️ Chế độ DRY RUN: Chưa có thao tác di chuyển nào được thực hiện.")
        return

    # Thực hiện di chuyển sang _trash_YYYYMMDD/
    date_str = datetime.now().strftime("%Y%m%d")
    trash_dest = WORKSPACE_ROOT / f"_trash_{date_str}" / "web_runs"
    trash_dest.mkdir(parents=True, exist_ok=True)

    print(f"\n🚀 Đang di chuyển {len(tasks_to_trash)} task sang: {trash_dest}...")
    moved_cnt = 0
    for t in tasks_to_trash:
        dest_item = trash_dest / t["name"]
        try:
            shutil.move(str(t["path"]), str(dest_item))
            moved_cnt += 1
        except Exception as e:
            print(f"  ❌ Lỗi khi di chuyển {t['name']}: {e}")

    print(f"✅ Hoàn tất dọn dẹp! Đã chuyển thành công {moved_cnt} task vào _trash.")


if __name__ == "__main__":
    main()
