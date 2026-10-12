"""
run_ui.py — Khởi chạy Giao diện Web Kiểm thử Video RoadGuard AI
==============================================================
Chạy lệnh: python run_ui.py
Trình duyệt sẽ tự động mở trang web tại địa chỉ: http://127.0.0.1:8080
"""

import sys
import time
import webbrowser
import threading
import uvicorn

# Đảm bảo console Windows hỗ trợ in tiếng Việt và emoji UTF-8 không bị lỗi
try:
    if sys.stdout:
        sys.stdout.reconfigure(encoding='utf-8')
    if sys.stderr:
        sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

HOST = "127.0.0.1"
PORT = 8080
URL = f"http://{HOST}:{PORT}"



def open_browser():
    time.sleep(1.5)
    print(f"\n🌐 Đang tự động mở trình duyệt tại: {URL}")
    webbrowser.open(URL)


def main():
    print("=" * 65)
    print("🚀 ROADGUARD AI — TEST BENCH KIỂM THỬ VIDEO & ĐÁNH GIÁ MÔ HÌNH")
    print("=" * 65)
    print(f"📍 Địa chỉ máy chủ: {URL}")
    print("💡 Bạn có thể chọn video có sẵn hoặc kéo thả video mới để phân tích.")
    print("   Nhấn Ctrl + C để dừng máy chủ bất kỳ lúc nào.")
    print("=" * 65)

    # Mở trình duyệt ở luồng phụ
    threading.Thread(target=open_browser, daemon=True).start()

    # Khởi chạy server
    uvicorn.run(
        "src.api.ui_server:app",
        host=HOST,
        port=PORT,
        log_level="info",
        reload=False
    )


if __name__ == "__main__":
    main()
