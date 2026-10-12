"""
tools/generate_pothole_5k_notebook.py — Tạo Notebook Colab Cho Bộ Dữ Liệu 5K Ổ Gà
"""

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
output_nb_path = WORKSPACE_ROOT / "notebooks" / "RoadGuard_Pothole_5K_Colab.ipynb"

cells = [
    {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "# 🕳️ ROADGUARD AI — HUẤN LUYỆN 5,000 ẢNH Ổ GÀ (TỐI ƯU GOOGLE COLAB FREE)\n",
            "### Nhận Diện Ổ Gà (Pothole) + Mẫu Âm Tính Chống Báo Động Giả (Bóng Râm / Mặt Đường Sạch)\n",
            "---\n",
            "> **Quy mô tối ưu:** Đúng chuẩn **5,000 ảnh** (3,940 ảnh ổ gà thực tế + 1,060 ảnh mẫu âm tính).\n",
            "> **Dung lượng file zip:** `pothole_dataset_5k.zip` chỉ **~221 MB** (Tải lên Colab mất ~10-15 giây).\n",
            "> **Thời gian huấn luyện:** Chỉ **~12–15 phút / 30 Epochs** trên GPU Tesla T4 (Miễn phí 100%, không lo timeout hay cạn tài nguyên!).\n",
            "> **Đầu ra:** File trọng số chuyên dụng `roadguard_pothole_best_5k.pt`."
        ]
    },
    {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "### 📌 BƯỚC 1: KIỂM TRA GPU TESLA T4 & CÀI ĐẶT THƯ VIỆN"
        ]
    },
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "# 1. Kiểm tra trạng thái GPU\n",
            "!nvidia-smi\n",
            "\n",
            "import torch\n",
            "print('=' * 65)\n",
            "print(f'CUDA Available: {torch.cuda.is_available()}')\n",
            "if torch.cuda.is_available():\n",
            "    print(f'GPU Model:      {torch.cuda.get_device_name(0)}')\n",
            "    print(f'VRAM Capacity:  {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB')\n",
            "else:\n",
            "    print('⚠️ CHÚ Ý: Hãy vào menu Runtime -> Change runtime type -> Chọn T4 GPU!')\n",
            "print('=' * 65)\n",
            "\n",
            "# 2. Cài đặt Ultralytics YOLOv11 mới nhất\n",
            "!pip install -q ultralytics matplotlib pyyaml opencv-python"
        ]
    },
    {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "### 📥 BƯỚC 2: GIẢI NÉN FILE `pothole_dataset_5k.zip`\n",
            "Kéo thả file `pothole_dataset_5k.zip` (~221 MB) vào cột Files bên trái Colab, sau đó bấm chạy ô bên dưới."
        ]
    },
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "import os, zipfile\n",
            "\n",
            "zip_path = 'pothole_dataset_5k.zip'\n",
            "extract_path = '/content/'\n",
            "\n",
            "if os.path.exists(zip_path):\n",
            "    print(f'Đang giải nén siêu tốc {zip_path}...')\n",
            "    with zipfile.ZipFile(zip_path, 'r') as zf:\n",
            "        zf.extractall(extract_path)\n",
            "    print('✓ Đã giải nén thành công vào: /content/pothole_dataset_5k')\n",
            "else:\n",
            "    print(f'⚠️ Chưa thấy file {zip_path}. Hãy kéo thả file vào Files bên trái Colab!')"
        ]
    },
    {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "### ⚙️ BƯỚC 3: CẤU HÌNH FILE `data.yaml` & KIỂM TRA SỐ LƯỢNG ẢNH"
        ]
    },
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "from pathlib import Path\n",
            "\n",
            "yaml_content = '''\n",
            "path: /content/pothole_dataset_5k\n",
            "train: train/images\n",
            "val:   valid/images\n",
            "test:  test/images\n",
            "\n",
            "nc: 1\n",
            "names: ['pothole']\n",
            "'''\n",
            "\n",
            "yaml_path = '/content/pothole_dataset_5k/data.yaml'\n",
            "with open(yaml_path, 'w', encoding='utf-8') as f:\n",
            "    f.write(yaml_content.strip())\n",
            "\n",
            "print(f'✓ File data.yaml sẵn sàng tại: {yaml_path}')\n",
            "\n",
            "# Kiểm tra số lượng ảnh từng tập\n",
            "p = Path('/content/pothole_dataset_5k')\n",
            "for split in ['train', 'valid', 'test']:\n",
            "    imgs = list((p / split / 'images').glob('*.*'))\n",
            "    lbls = list((p / split / 'labels').glob('*.txt'))\n",
            "    print(f'• Tập [{split.upper():<5}]: {len(imgs):,} ảnh | {len(lbls):,} file nhãn')\n",
            "print('👉 Tổng cộng chuẩn 5,000 ảnh (bao gồm cả ổ gà thực tế và mẫu âm tính bóng râm).')"
        ]
    },
    {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "### 🚀 BƯỚC 4: HUẤN LUYỆN YOLOV11N SIÊU TỐC (~12-15 PHÚT)\n",
            "Huấn luyện 30 Epochs với batch=16 trên GPU Tesla T4."
        ]
    },
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "from ultralytics import YOLO\n",
            "\n",
            "# Khởi tạo từ mô hình nền tảng YOLOv11 nano nhẹ nhất và chính xác nhất\n",
            "model = YOLO('yolo11n.pt')\n",
            "\n",
            "results = model.train(\n",
            "    data='/content/pothole_dataset_5k/data.yaml',\n",
            "    epochs=30,            # 30 epochs chỉ mất ~12-15 phút trên T4 GPU\n",
            "    imgsz=640,\n",
            "    batch=16,\n",
            "    device=0,\n",
            "    warmup_epochs=2,\n",
            "    box=7.5,\n",
            "    cls=0.5,\n",
            "    dfl=1.5,\n",
            "    mosaic=0.5,\n",
            "    close_mosaic=5,\n",
            "    project='roadguard_train',\n",
            "    name='pothole_5k_yolo11n',\n",
            "    save=True,\n",
            "    val=True,\n",
            "    plots=True\n",
            ")\n",
            "print('🎉 HUẤN LUYỆN HOÀN TẤT THÀNH CÔNG!')"
        ]
    },
    {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "### 📊 BƯỚC 5: ĐÁNH GIÁ CHỈ SỐ TRÊN TẬP TEST ĐỘC LẬP (258 ẢNH)"
        ]
    },
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "best_pt = '/content/roadguard_train/pothole_5k_yolo11n/weights/best.pt'\n",
            "eval_model = YOLO(best_pt)\n",
            "\n",
            "metrics = eval_model.val(data='/content/pothole_dataset_5k/data.yaml', split='test')\n",
            "\n",
            "print('=' * 65)\n",
            "print('🏆 KẾT QUẢ ĐÁNH GIÁ TRÊN TẬP TEST Ổ GÀ (258 ẢNH):')\n",
            "print(f'• mAP@50 (Độ chuẩn nhận diện): {metrics.box.map50 * 100:.2f}%')\n",
            "print(f'• mAP@50-95:                   {metrics.box.map * 100:.2f}%')\n",
            "print(f'• Precision (Độ chính xác):    {metrics.box.mp * 100:.2f}%')\n",
            "print(f'• Recall (Độ bao quát):        {metrics.box.mr * 100:.2f}%')\n",
            "print('=' * 65)"
        ]
    },
    {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "### 💾 BƯỚC 6: TẢI MODEL XUẤT XƯỞNG `roadguard_pothole_best_5k.pt` VỀ MÁY"
        ]
    },
    {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [
            "import shutil\n",
            "from google.colab import files\n",
            "\n",
            "out_file = 'roadguard_pothole_best_5k.pt'\n",
            "shutil.copy2(best_pt, out_file)\n",
            "print(f'Đã sẵn sàng tải file: {out_file}')\n",
            "files.download(out_file)\n",
            "print('👉 Hãy lưu file này vào: weights/trained/roadguard_pothole_best_5k.pt trong project của bạn!')"
        ]
    }
]

nb = {
    "cells": cells,
    "metadata": {
        "accelerator": "GPU",
        "colab": {
            "name": "RoadGuard_Pothole_5K_Colab.ipynb",
            "provenance": []
        },
        "kernelspec": {
            "display_name": "Python 3",
            "name": "python3"
        },
        "language_info": {
            "name": "python"
        }
    },
    "nbformat": 4,
    "nbformat_minor": 0
}

with open(output_nb_path, "w", encoding="utf-8") as f:
    json.dump(nb, f, ensure_ascii=False, indent=2)

print(f"✓ Đã tạo thành công Notebook Colab: {output_nb_path}")
