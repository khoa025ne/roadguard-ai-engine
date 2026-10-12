import sys
import json
import base64
from pathlib import Path
from openai import OpenAI

sys.stdout.reconfigure(encoding='utf-8')

img_path = Path("results/test_pothole_stock/crops/crop_job-acbcf8a23819_0001.jpg")
if not img_path.exists():
    print(f"File not found: {img_path}")
    sys.exit(1)

with open(img_path, "rb") as f:
    b64_data = base64.b64encode(f.read()).decode("utf-8")

import os

# Tự động nạp .env nếu chưa có biến môi trường
if not os.getenv("KDV_API_KEY") and Path(".env").exists():
    with open(".env", "r", encoding="utf-8") as f:
        for line in f:
            if line.strip() and not line.startswith("#") and "=" in line:
                k, v = line.strip().split("=", 1)
                os.environ[k.strip()] = v.strip().strip("'\"")

api_key = os.getenv("KDV_API_KEY")
if not api_key:
    print("LỖI: Chưa cấu hình KDV_API_KEY trong .env hoặc biến môi trường!")
    sys.exit(1)

base_url = os.getenv("KDV_BASE_URL", "https://api.xah.io/v1")
model_name = os.getenv("KDV_MODEL", "gpt-5.4")

client = OpenAI(
    api_key=api_key,
    base_url=base_url,
    timeout=30.0
)

prompt = """Bạn là KDV (Kiểm Duyệt Viên) - Chuyên gia AI thẩm định khuyết tật mặt đường giao thông (Crack & Pothole).
Nhiệm vụ:
1. SÀNG LỌC (Verify): Phán quyết [CHUẨN] (is_valid: true) hay [BÁO ĐỘNG GIẢ] (is_valid: false - do bóng râm, bóng cây, vạch kẻ đường, rác, vệt dầu...).
2. GẮN TAG (Tagging): Phân loại chi tiết khuyết tật (nứt dọc, nứt ngang, nứt lưới, ổ gà nông, ổ gà sâu...), cấp độ nguy hiểm (LOW, MEDIUM, CRITICAL) và nêu lý do ngắn gọn.

BẮT BUỘC trả về định dạng JSON thuần túy theo mẫu sau:
{
  "is_valid": true,
  "fine_tag": "crack_longitudinal",
  "severity": "MEDIUM",
  "reasoning": "Mô tả ngắn gọn bằng tiếng Việt"
}
Các giá trị fine_tag hợp lệ:
- crack_longitudinal: Vết nứt dọc tuyến
- crack_transverse: Vết nứt ngang tuyến
- crack_alligator: Vết nứt chân chim / nứt lưới
- pothole_shallow: Ổ gà nông
- pothole_deep_water: Ổ gà sâu hoặc đọng nước
- false_alarm_shadow: Báo động giả do bóng râm / bóng cây
- false_alarm_debris: Báo động giả do vệt sơn, rác, vệt dầu, mặt đường bẩn
"""

import time

max_retries = 3
raw_content = ""
for attempt in range(1, max_retries + 1):
    try:
        res = client.chat.completions.create(
            model="gpt-5.4",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_data}"}}
                    ]
                }
            ]
        )
        content = res.choices[0].message.content.strip()
        if "lỗi nội bộ" in content.lower():
            print(f"Attempt {attempt}: Gặp lỗi nội bộ proxy, đang retry sau 1.5s...")
            time.sleep(1.5)
            continue
        raw_content = content
        break
    except Exception as e:
        print(f"Attempt {attempt} failed: {e}")
        time.sleep(1.5)

print("=== RAW RESPONSE ===")
print(raw_content)
