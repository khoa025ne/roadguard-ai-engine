# 08 — Google Drive 5 TB và manifest

## Layout đề xuất

```text
RoadGuard/
  00_raw/{survey_id}/{video,srt,metadata}/
  01_frames/{survey_id}/{sampled,best_evidence}/
  02_annotations/{dataset_version}/{train,val,test,manifest}/
  03_models/{model_version}/{weights,metrics,config}/
  04_runs/{run_id}/{candidates,metrics,logs,reports}/
  05_review/{survey_id}/{accepted,rejected,hard_negatives}/
  06_exports/{date}/
```

Raw immutable. Derived artifact phải tái tạo được từ raw + code + config. Local chỉ giữ cache theo run và có checksum.

## Manifest bắt buộc

`survey_id`, source file IDs, SHA256, duration/FPS/resolution, SRT status, camera metadata, dataset/model/config version, code commit, sampling parameters, output paths, counts, failure reasons và timestamps.

## Pairing và camera profile đã chốt

Mỗi survey phải có các cặp:

```text
DJI_0057.MP4 + DJI_0057.SRT
DJI_0059.MP4 + DJI_0059.SRT
DJI_0061.MP4 + DJI_0061.SRT
DJI_0064.MP4 + DJI_0064.SRT
```

Pairing chỉ PASS khi basename khớp 100%, duration/time coverage không lệch bất thường và SRT có GPS/barometer/gimbal pitch. Camera profile mặc định là DJI Mini 2 SE; mọi survey dùng profile khác phải tạo version mới.

## Vận hành

Đồng bộ raw trước, rồi derived; không dùng thư mục Drive đang sync dở làm input inference. Mỗi run có lock/status (`created/running/complete/failed`) và file `metrics.json`. Xóa intermediate chỉ sau khi artifact cuối và checksum đã kiểm tra.
