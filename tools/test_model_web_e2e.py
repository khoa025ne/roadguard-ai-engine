"""
tools/test_model_web_e2e.py
Kiểm thử tích hợp model mới roadguard_crack_yolo11n_v1.pt qua API Web UI
"""

import sys
import time
import json
import urllib.request

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

payload = {
    "zip_path": None,
    "folder_path": "F:/train AI đồ án/data/road_crack_test_eval/test/images",
    "model_path": "F:/train AI đồ án/weights/trained/roadguard_crack_yolo11n_v1.pt",
    "conf_threshold": 0.25,
    "max_images": 5
}

print("🚀 Gửi yêu cầu quét 5 ảnh vết nứt với model roadguard_crack_yolo11n_v1.pt...")
req = urllib.request.Request(
    "http://127.0.0.1:8080/api/start-dataset-analysis",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)
res = urllib.request.urlopen(req)
data = json.loads(res.read())
task_id = data["task_id"]
print(f"✅ Đã tạo tác vụ: {task_id}")

status_data = {}
for i in range(30):
    time.sleep(0.8)
    status_res = urllib.request.urlopen(f"http://127.0.0.1:8080/api/task-status/{task_id}")
    status_data = json.loads(status_res.read())
    pct = status_data.get("progress_pct", 0)
    st = status_data.get("status", "")
    msg = status_data.get("message", "")
    print(f"[{i+1}] Tiến độ: {pct:.1f}% | Trạng thái: {st} | {msg}")
    if st in ["COMPLETED", "FAILED"]:
        break

if status_data.get("status") == "COMPLETED":
    results_res = urllib.request.urlopen(f"http://127.0.0.1:8080/api/task-results/{task_id}")
    results_data = json.loads(results_res.read())
    summary = results_data.get("summary", {})
    print("=" * 60)
    print("🎉 KIỂM THỬ WEB UI THÀNH CÔNG VỚI MODEL MỚI:")
    print(f" - Tổng ảnh quét:       {summary.get('total_frames')}")
    print(f" - Tổng khuyết tật tìm: {summary.get('total_defects')}")
    print(f" - Vết nứt (Crack):     {summary.get('crack_count', 0)}")
    print(f" - Ổ gà (Pothole):      {summary.get('pothole_count', 0)}")
    print(f" - Tỷ lệ phát hiện:     {summary.get('hit_rate_pct', 0)}%")
    print(f" - Tốc độ trung bình:   {summary.get('fps', 0)} FPS")
    print(f" - Số lượng ảnh crop:   {len(results_data.get('crops', []))}")
    print("=" * 60)
else:
    print(f"❌ Tác vụ thất bại: {status_data}")
