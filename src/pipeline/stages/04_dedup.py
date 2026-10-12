"""
src/pipeline/stages/04_dedup.py — Giai đoạn 4: Khử Trùng Lặp Đối Tượng (Defect Deduplication)
=============================================================================================
Nhiệm vụ:
  - Khử trùng lặp đa khung hình theo chuỗi thời gian (Flycam bay liên tục 2-4 giây qua cùng 1 vị trí).
  - Khử trùng lặp do cắt mảnh lưới 640x640 có gối đầu 20%.
  - Tích hợp DefectDeduplicator để gom cụm đối tượng, gán cluster_id / track_id.

Interface:
  def run(ctx: dict) -> dict
"""

from typing import Dict, Any, List
from src.curation.deduplicator import DefectDeduplicator


def run(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Thực thi Stage 04: Dedup.
    """
    cfg = ctx.get("config", {}).get("stages", {}).get("04_dedup", {})
    if not cfg.get("enabled", True):
        ctx["deduped_detections"] = ctx.get("filtered_detections", [])
        return ctx

    time_th = float(cfg.get("time_threshold_s", 2.0))
    frame_th = int(cfg.get("frame_threshold", 4))
    dist_norm_th = float(cfg.get("spatial_dist_norm_threshold", 0.20))
    sim_th = float(cfg.get("visual_similarity_threshold", 0.76))

    deduplicator = DefectDeduplicator(
        time_threshold_s=time_th,
        frame_threshold=frame_th,
        spatial_dist_norm_threshold=dist_norm_th,
        visual_similarity_threshold=sim_th
    )

    items = ctx.get("filtered_detections", [])
    if not items:
        ctx["deduped_detections"] = []
        ctx["dedup_stats"] = {"total": 0, "unique": 0, "duplicates_removed": 0}
        return ctx

    # Chuẩn bị định danh duy nhất cho từng detection
    for idx, it in enumerate(items, 1):
        if "id" not in it:
            it["id"] = f"det_{idx:04d}"
        if "crop_id" not in it:
            it["crop_id"] = f"crop_{idx:04d}"
        if "index" not in it:
            it["index"] = idx

    dedup_res = deduplicator.deduplicate(items)
    unique_items = dedup_res.get("unique_items", items)

    ctx["deduped_detections"] = unique_items
    ctx["all_clustered_detections"] = dedup_res.get("deduplicated_items", items)
    ctx["dedup_stats"] = {
        "total_filtered": dedup_res.get("total_items", len(items)),
        "unique_defects": dedup_res.get("unique_count", len(unique_items)),
        "duplicates_merged": dedup_res.get("duplicate_count", len(items) - len(unique_items))
    }
    ctx["stage_04_completed"] = True
    return ctx
