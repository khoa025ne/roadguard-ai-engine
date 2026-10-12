"""
tools/inbox_runner/runner.py — Trình Thực Thi Vòng Lặp Nhận Task Tự Động Cho Antigravity
========================================================================================
Kiến trúc:
1. Đồng bộ git pull để kéo các prompt mới do Muse (Pé) đẩy vào inbox/.
2. Quét thư mục inbox/ tìm file prompt (ưu tiên inbox/NEXT_PROMPT.md hoặc *.md không có tiền tố '_').
3. Nếu không có file mới -> In log chính xác: "[inbox_runner] inbox empty" và kết thúc.
4. Nếu có file mới -> Nạp nội dung, gọi Antigravity CLI (agy) thực thi tự hành.
5. Sau khi xong -> Đổi tên file task thành inbox/_done_<timestamp>_<name>.md.
"""

import os
import sys
import time
import subprocess
from pathlib import Path
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# Định vị thư mục gốc của repository
REPO_DIR = Path(__file__).resolve().parents[2]
INBOX_DIR = REPO_DIR / "inbox"
INBOX_DIR.mkdir(parents=True, exist_ok=True)

# Đảm bảo agy CLI có trong PATH
AGY_BIN_DIR = Path(os.environ.get("LOCALAPPDATA", "C:/Users/ADMIN/AppData/Local")) / "agy" / "bin"
if AGY_BIN_DIR.exists():
    path_env = os.environ.get("PATH", "")
    if str(AGY_BIN_DIR) not in path_env:
        os.environ["PATH"] = f"{AGY_BIN_DIR};{path_env}"


def run_cmd(cmd_list, cwd=REPO_DIR, check=False):
    """Chạy lệnh subprocess với UTF-8 encoding."""
    try:
        res = subprocess.run(
            cmd_list,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=True
        )
        return res.returncode, res.stdout.strip(), res.stderr.strip()
    except Exception as e:
        return -1, "", str(e)


def git_sync_pull():
    """Đồng bộ git pull từ remote để lấy task mới nhất."""
    code, out, err = run_cmd(["git", "pull"])
    if code != 0:
        print(f"[inbox_runner] Cảnh báo git pull thất bại: {err}")
    else:
        print(f"[inbox_runner] Git pull: {out}")


def find_pending_task():
    """Tìm task đang chờ trong inbox/ (ưu tiên NEXT_PROMPT.md)."""
    next_prompt = INBOX_DIR / "NEXT_PROMPT.md"
    if next_prompt.exists() and next_prompt.is_file():
        return next_prompt

    # Quét các file .md khác không có tiền tố '_'
    candidates = []
    for f in INBOX_DIR.glob("*.md"):
        if not f.name.startswith("_"):
            candidates.append(f)

    if candidates:
        # Lấy file có thời gian chỉnh sửa cũ nhất trước (FIFO)
        candidates.sort(key=lambda x: x.stat().st_mtime)
        return candidates[0]

    return None


def execute_task(task_file: Path):
    """Kích hoạt agy CLI thực thi nội dung task."""
    print(f"[inbox_runner] Phát hiện nhiệm vụ mới: {task_file.name}")
    try:
        with open(task_file, "r", encoding="utf-8") as f:
            prompt_content = f.read().strip()
    except Exception as e:
        print(f"[inbox_runner] Lỗi đọc file {task_file}: {e}")
        return False

    if not prompt_content:
        print(f"[inbox_runner] File task rỗng, bỏ qua.")
        archive_task(task_file, status="empty")
        return True

    print(f"[inbox_runner] Kích hoạt Antigravity CLI ('agy') với độ dài prompt: {len(prompt_content)} ký tự...")
    
    # Sử dụng agy CLI với chế độ non-interactive print mode và auto-approve tool permissions
    cmd = [
        "agy",
        "--print",
        "--dangerously-skip-permissions",
        prompt_content
    ]

    t0 = time.time()
    code, out, err = run_cmd(cmd)
    elapsed = time.time() - t0

    if code == 0:
        print(f"[inbox_runner] Hoàn thành nhiệm vụ thành công sau {elapsed:.1f}s.")
        archive_task(task_file, status="done")
        return True
    else:
        print(f"[inbox_runner] Lỗi khi thực thi agy (exit code {code}): {err}")
        archive_task(task_file, status="error")
        return False


def archive_task(task_file: Path, status="done"):
    """Lưu trữ task đã hoàn tất bằng cách đổi tên."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target_name = f"_{status}_{timestamp}_{task_file.name}"
    target_path = INBOX_DIR / target_name
    try:
        task_file.rename(target_path)
        print(f"[inbox_runner] Đã lưu trữ task sang: {target_name}")
    except Exception as e:
        print(f"[inbox_runner] Không thể đổi tên file task: {e}")


def main():
    print(f"[inbox_runner] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} — Bắt đầu kiểm tra hàng đợi...")
    
    # 1. Đồng bộ git
    git_sync_pull()

    # 2. Quét task
    task_file = find_pending_task()
    if not task_file:
        print("[inbox_runner] inbox empty")
        sys.exit(0)

    # 3. Thực thi task
    success = execute_task(task_file)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
