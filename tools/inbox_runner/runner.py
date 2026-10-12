#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RoadGuard Inbox Runner — mỗi tick (Task Scheduler gọi mỗi 30 phút):
  git pull -> tìm task pending trong inbox/ -> chạy 1 task bằng `agy -p` headless.

Yêu cầu trên máy Windows:
  - `agy` CLI đã cài + đăng nhập Google (https://antigravity.google)
  - Python 3.9+
  - Repo đã clone, remote origin trỏ đúng github.com/khoa025ne/roadguard-ai-engine
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
INBOX = REPO / "inbox"
DONE_DIR = INBOX / "done"
FAILED_DIR = INBOX / "failed"
LOG = INBOX / "_runner.log"
LOCK = INBOX / ".lock"
ATTEMPTS = INBOX / "_attempts.json"
BRANCH = "feature/target-band-api-worker"

AGY_FLAGS = ["--print-timeout", "6h", "--dangerously-skip-permissions"]
# --dangerously-skip-permissions: cho agent chạy tự hành, không dừng hỏi approve.
#   Tương đương mức tin tưởng đã dùng khi cho agent chạy mission qua đêm.
#   Muốn chặt hơn: bỏ flag này -> task nào cần approve sẽ đứng chờ (mất tự hành).


def agy_cmd():
    # --add-dir: BẮT BUỘC. Không có nó, agy chạy trong scratch dir riêng
    # (~/.gemini/antigravity-cli/scratch) thay vì repo -> mọi file agent tạo
    # rơi sai chỗ, git push trong repo fail, task "xong" mà repo trống trơn.
    # cwd= của subprocess KHÔNG có tác dụng với agy.
    return ["agy", "--add-dir", str(REPO), "-p", "-", *AGY_FLAGS]

MAX_ATTEMPTS = 3          # task fail 3 lần -> chuyển sang inbox/failed/
STALE_LOCK_HOURS = 8      # lock quá cũ -> coi như tick trước crash, tự gỡ
AGY_TIMEOUT = 6.5 * 3600  # phải lớn hơn --print-timeout của agy

SUPERVISOR = """Bạn là agent Antigravity (headless) làm việc trong repo roadguard-ai-engine.
- Workspace root (= thư mục repo): {repo}  -- mọi file tạo/sửa phải nằm trong này
- Branch: {branch}
- BẮT BUỘC đọc và tuân thủ .agents/rules/git_workflow.md (LUẬT SẮT: báo cáo -> git add/commit/push -> verify).
- Dùng sequential-thinking. Trích dẫn file:dòng cho mọi khẳng định kỹ thuật.
- KHÔNG xóa file khi chưa được duyệt. KHÔNG đụng file ngoài repo này.
- Nhiệm vụ chi tiết trong TASK bên dưới. Làm đúng spec, đủ điều kiện nghiệm thu.

KHI HOÀN THÀNH (bắt buộc, không được bỏ bước nào):
1. Viết báo cáo vào reports/agent_reports/<ten-task>.md
2. Sửa frontmatter task file thành status: done, chuyển file sang inbox/done/
3. git add -A reports inbox && git commit && git push origin {branch}
4. Verify: git log origin/{branch} --oneline -1
Bước nào fail: ghi rõ lý do vào báo cáo rồi mới kết thúc.
"""


def log(msg):
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line, flush=True)
    try:
        INBOX.mkdir(parents=True, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def sh(args, check=False):
    return subprocess.run(args, cwd=REPO, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def load_attempts():
    try:
        return json.loads(ATTEMPTS.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_attempts(d):
    ATTEMPTS.write_text(json.dumps(d, indent=1), encoding="utf-8")


def pending_tasks():
    tasks = []
    if not INBOX.exists():
        return tasks
    for p in sorted(INBOX.glob("*.md")):
        if p.name.startswith("_"):
            continue
        head = p.read_text(encoding="utf-8")[:800]
        if "status: pending" in head:
            tasks.append(p)
    return tasks


def ensure_branch():
    """Đảm bảo đang đứng trên BRANCH. Clone mặc định ở main: nếu pull
    origin/BRANCH khi đang ở main sẽ merge nhầm feature branch vào main."""
    cur = sh(["git", "rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()
    if cur == BRANCH:
        return True
    r = sh(["git", "checkout", BRANCH])
    if r.returncode != 0:
        r = sh(["git", "checkout", "-b", BRANCH, f"origin/{BRANCH}"])
    if r.returncode != 0:
        log(f"checkout {BRANCH} fail: {r.stderr.strip()[:200]}")
        return False
    log(f"checkout -> {BRANCH} (dang o {cur})")
    return True


def git_sync():
    """Pull task mới về. Không đè việc đang dở: repo bẩn -> bỏ tick này."""
    dirty = sh(["git", "status", "--porcelain"]).stdout.strip()
    if dirty:
        log(f"repo dirty, skip tick de khong de mat viec do:\n{dirty[:500]}")
        return False
    if not ensure_branch():
        return False
    r = sh(["git", "pull", "--ff-only", "origin", BRANCH])
    if r.returncode != 0:
        log(f"git pull fail: {r.stderr.strip()[:300]}")
        return False
    return True


def commit_state(msg):
    sh(["git", "add", "-A", "inbox", "reports"])
    r = sh(["git", "commit", "-m", msg])
    if r.returncode == 0:
        p = sh(["git", "push", "origin", BRANCH])
        if p.returncode != 0:
            log(f"git push fail: {p.stderr.strip()[:300]}")
    # returncode != 0 thường là "nothing to commit" -> bình thường


def main():
    log("=== tick ===")
    if not shutil.which("agy"):
        log("ERROR: khong tim thay `agy` tren PATH. Cai tai https://antigravity.google roi dang nhap.")
        return 1
    if LOCK.exists():
        age_h = (time.time() - LOCK.stat().st_mtime) / 3600
        if age_h < STALE_LOCK_HOURS:
            log(f"lock con hieu luc ({LOCK.read_text()[:50]}), tick khac dang chay -> skip")
            return 0
        log("lock qua cu, coi nhu tick truoc crash -> go lock")
        LOCK.unlink()

    if not git_sync():
        commit_state("inbox-runner: tick (skip, repo dirty hoac pull fail)")
        return 0

    tasks = pending_tasks()
    if not tasks:
        log("inbox empty")
        commit_state("inbox-runner: tick (inbox empty)")
        return 0

    task = tasks[0]
    attempts = load_attempts()
    n = attempts.get(task.name, 0)
    log(f"lay task: {task.name} (attempt {n + 1})")
    LOCK.write_text(
        f"{task.name} pid={os.getpid()} at={time.strftime('%Y-%m-%d %H:%M:%S')}",
        encoding="utf-8")

    prompt = (SUPERVISOR.format(repo=REPO, branch=BRANCH)
              + f"\n--- TASK FILE: inbox/{task.name} ---\n\n"
              + task.read_text(encoding="utf-8"))
    try:
        r = subprocess.run(agy_cmd(),
                           input=prompt, cwd=REPO,
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace",
                           timeout=AGY_TIMEOUT)
        log(f"agy exit={r.returncode}")
        if r.stdout:
            log(f"agy stdout tail: {r.stdout[-600:]}")
        if r.returncode != 0 and r.stderr:
            log(f"agy stderr tail: {r.stderr[-600:]}")
    except subprocess.TimeoutExpired:
        log("agy timeout 6.5h")
        r = None
    finally:
        LOCK.unlink(missing_ok=True)

    ok = (r is not None and r.returncode == 0)
    if ok and (INBOX / task.name).exists():
        # agent quen chuyen file -> runner don dep giup
        log("agent chua chuyen task sang done/, runner tu chuyen")
        DONE_DIR.mkdir(exist_ok=True)
        (INBOX / task.name).rename(DONE_DIR / task.name)
        attempts.pop(task.name, None)
    elif not ok:
        n += 1
        attempts[task.name] = n
        if n >= MAX_ATTEMPTS:
            log(f"task fail {n} lan -> chuyen sang inbox/failed/")
            FAILED_DIR.mkdir(exist_ok=True)
            (INBOX / task.name).rename(FAILED_DIR / task.name)
            attempts.pop(task.name, None)
        else:
            log(f"task fail lan {n}, de pending de tick sau thu lai")
    else:
        attempts.pop(task.name, None)
    save_attempts(attempts)

    commit_state(f"inbox-runner: {task.name} ({'done' if ok else 'failed attempt'})")
    log("=== het tick ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
