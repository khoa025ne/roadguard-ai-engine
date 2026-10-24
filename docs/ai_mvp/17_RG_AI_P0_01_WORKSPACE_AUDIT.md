# RG-AI-P0-01 — Kiểm kê AI workspace và baseline

> Cập nhật khảo sát nguồn sau audit: đã xác minh 5 cặp MP4/SRT `DJI_0059`–`DJI_0063` tại `F:\video-flycam ngày 04-10`. Phần nhận định về SRT trong tài liệu này là ảnh chụp thời điểm kiểm kê cũ; xem [audit DJI mới](18_DJI_SURVEY_20261004_AUDIT.md) để dùng dữ liệu hiện hành.

Ngày kiểm tra: 2026-10-22; revision `82ae0dc` + các file chưa được Git theo dõi. Sáu tài liệu `01/02/03/09/10/12` là yêu cầu đối chiếu, không phải bằng chứng phần mềm đã đạt MVP. Phạm vi là `F:\train AI đồ án`; không sửa Backend/Frontend, không train, không đổi source/config/model/dataset. `GIỮ` nghĩa là cần giữ ở thời điểm audit, không khẳng định đã đạt chất lượng; `CẦN XÁC MINH` nghĩa là chưa đủ bằng chứng để xóa hoặc dùng làm nguồn sự thật.

## 1. Hiện có gì?

### Source và luồng chạy

| Thành phần | Công dụng / nơi dùng | Quyết định |
|---|---|---|
| `pipeline.py`, `src/pipeline/pipeline.py`, `src/pipeline/stages/__init__.py` | CLI, điều phối 7 stage; stage được nạp **động** bằng `importlib`, không được xóa vì thiếu import tĩnh | GIỮ |
| `src/pipeline/stages/01_segment.py` | Road mask bằng YOLO-seg, fallback Otsu/HSV; dùng `weights/pretrained/yolo11m-road-seg.pt` | GIỮ; fallback phủ vùng giữa khi mask yếu là rủi ro |
| `02_detect.py` | Detector + tiling, dùng checkpoint trong config | GIỮ |
| `03_filter.py` | Lọc confidence, bbox, road-mask overlap 35%, target band | GIỮ; mask thiếu thì cho qua |
| `04_dedup.py` | Gọi `DefectDeduplicator` gom detection gần thời gian/frame/ảnh | GIỮ; chưa chứng minh tracking/persistence trên video thật |
| `05_measure.py` | Ước lượng kích thước/GPS từ SRT hoặc default | GIỮ; GSD hardcode 2720 px và độ cao fallback 10 m trái nguyên tắc không bịa số đo |
| `06_inspect.py` | Heuristic KDV/VLM tùy cấu hình; mặc định heuristic | GIỮ; crop thiếu có nhánh tự đánh dấu `VERIFIED` |
| `07_report.py` | JSON/GeoJSON/PDF/crop/annotated frame | GIỮ; schema báo cáo còn thiên về 2 lớp |
| `src/ingestion/{video_extractor,srt_parser,survey_manifest,dataset_scanner}.py` | Đọc video/SRT, manifest kiểm kê và quét dữ liệu; `survey_manifest` được tool P0 dùng | GIỮ; parser runtime có default alt/pitch, khác validator chặt của manifest |
| `src/inference/{predictor,tiling_engine}.py` | Nạp YOLO, cắt tile, hiển thị; được stage/UI/tool gọi | GIỮ |
| `src/curation/{auto_tagger,crack_analyzer,dataset_exporter,deduplicator,kdv_inspector}.py` | Curation, phân tích nứt, xuất nhãn, dedup, review; được stage/UI/tool gọi | GIỮ; không coi heuristic/VLM là nghiệm thu |
| `src/measurement/{metric_estimator,spatial_tracker}.py`, `src/utils/{geo,io}.py`, `src/reporting/pdf_exporter.py` | Ước lượng, hỗ trợ tọa độ, I/O, PDF; có consumer trực tiếp hoặc công cụ field | GIỮ |
| `src/contracts/{aidetection_schema,idempotency,mock_ai_adapter}.py` | Format callback, idempotency, mock; worker/test dùng | GIỮ cho tích hợp; mock không phải real AI |
| `src/api/ui_server.py`, `src/api/web/`, `run_ui.py` | Test bench dùng pipeline thật, ảnh và kết quả ở `results/` | GIỮ; không chỉnh UI trong phiếu này |
| `src/api/worker_service.py` | Endpoint job/callback cho Backend; **cả nhánh `is_mock=false` vẫn gọi `MockAIAdapter`** | GIỮ; blocker E2E real worker |
| `src/training/{train_crack,train_pothole}.py` | Entry point huấn luyện lịch sử một lớp; không trong inference MVP | CẦN XÁC MINH trước xóa vì giữ khả năng tái hiện |

### Tools, script, notebook

| Thành phần | Công dụng / quan hệ | Quyết định |
|---|---|---|
| `tools/{audit_survey_assets,audit_dataset_readiness,check_training_readiness}.py` | Manifest MP4/SRT, đếm YOLO label, gate số lượng | GIỮ; `check_training_readiness` nhận số survey/negative **do người gọi tự khai**, không kiểm chứng provenance |
| `tools/{benchmark_road_seg_model,validate_mask_filter_effect,eval_multiclass_model,run_field_test,test_roadguard_15k,benchmark_crack_v1,benchmark_curation_flow,eval_dataset_zip}.py` | Benchmark/eval/smoke độc lập; có output và trọng số liên quan | GIỮ; giữ để tái hiện, chưa thay thế evaluation gate trên holdout thật |
| `tools/{extract_50_drone_frames,extract_testcases_and_export_dataset,verify_and_pack_phase2_dataset,remap_merge,merge_datasets}.py` | Tạo frame/test case, remap/đóng gói nhãn | GIỮ vì liên quan nguồn dữ liệu và khả năng tái hiện |
| `tools/{build_20k_dataset,build_5k_pothole_dataset,build_full_44k_dataset,package_kaggle_dataset}.py` | Builder/đóng gói tập dữ liệu các đời; có chức năng chồng lấn nhưng mapping khác nhau | CẦN XÁC MINH input/output và checksum trước khi hợp nhất/xóa |
| `tools/{generate_crack_notebook,generate_kaggle_notebook,generate_multiclass_notebook,generate_phase2_colab_notebook,generate_pothole_5k_notebook}.py` và `notebooks/` (10 file) | Sinh notebook train Kaggle/Colab lịch sử; không dùng ở đường inference | CẦN XÁC MINH phiên bản nào sinh checkpoint/metrics đang giữ |
| `tools/{train_phase2_local,train_upgrade_model}.py`, `tools/{test_kdv,test_kdv_context,test_model_web_e2e}.py` | Train/thử thủ công, không thuộc regression mặc định | CẦN XÁC MINH vì có thể là lệnh tái hiện kết quả |
| `tools/create_video_from_dataset.py` | Tạo video tổng hợp để test, không thay thế video bay thật | CẦN XÁC MINH trước xóa fixture |
| `tools/cleanup_tasks.py`, `docs/RETENTION.md` | Retention `results/web_runs`; bảo vệ junction và task được tài liệu dẫn | GIỮ; **không chạy chế độ xóa/di dời** trong audit này |
| `tools/inbox_runner/` | Runner tự động cho task AI, không phải model runtime | CẦN XÁC MINH workflow đang dùng; không tự vô hiệu hóa |
| `scratch/` (6 file), `inbox/`, `reports/agent_reports/` | Script UI ad-hoc, yêu cầu/biên bản cũ; có tham chiếu chéo | CẦN XÁC MINH; không thuộc lõi MVP nhưng chưa chứng minh có thể bỏ |
| `tests/` (9 module) | 36 unit/integration tests, gồm pipeline/API/mock/curation/manifest/readiness | GIỮ; test qua không chứng minh model đạt field gate |

### Config, weights, dữ liệu, output, tài liệu

| Thành phần | Hiện trạng / phụ thuộc | Quyết định |
|---|---|---|
| `configs/pipeline.yaml`, `class_map.json`, `requirements.txt`, `.env.example` | Cấu hình chạy và taxonomy hiện 3 lớp; pipeline chọn model 2 lớp; `.env` thật không mở/in, không xóa | GIỮ |
| `configs/{crack_8classes,pothole_dataset,road_crack_dataset}.yaml` | Config train từng bộ dữ liệu | CẦN XÁC MINH trước xóa vì notebook/script có thể dùng qua path |
| `weights/pretrained/yolo11m-road-seg.pt` | Đã nạp: segmentation 1 lớp `road` | GIỮ |
| `weights/trained/roadguard_best_15k.pt` | Đã nạp: detect 2 lớp `pothole, crack`; **mặc định** | GIỮ |
| `weights/trained/roadguard_multiclass_v1_best.pt` | Đã nạp: detect 3 lớp `pothole, crack, bong_troc`, chưa mặc định | GIỮ; chưa chứng minh chất lượng bong_troc trên domain |
| `weights/trained/{roadguard_crack_yolo11n_v1,roadguard_pothole_best_5k}.pt`, `.zip` cùng tên multiclass | Checkpoint riêng lớp / gói phân phối; không chứng minh bản thay thế tương đương | CẦN XÁC MINH; không xóa |
| `data/raw_videos/` | 4 MP4 gốc trong workspace, 4,499,043,644 byte; không có SRT cùng thư mục | GIỮ tuyệt đối |
| `data/{merged,unified_road_dataset_15k,pothole_dataset_5k,unified_dataset,unified_road_dataset_20k,unified_road_dataset_full,pothole,road_crack_test_eval,curated_export,mvp_test_cases}/` và ZIP dataset | Dataset, nhãn, holdout/fixture hoặc bản dẫn xuất; nguồn dữ liệu và split chưa đủ metadata để chọn bản thừa | GIỮ; chưa xóa dữ liệu/nhãn |
| `data/road_crack` | NTFS junction tới `results/web_runs/task_ds_1790603381_f0cab9/unzipped` | GIỮ target; không dọn `web_runs` theo tuổi |
| `outputs/{drone_benchmark_50_frames,road_seg_eval_overlays,eval_multiclass,mask_filter_validation,reports}/`, JSON report/manifest | Evidence kiểm thử hoặc cần đối chiếu; 50 frame/overlay và các report không được tự xóa | GIỮ |
| `outputs/predicts/` (42,851 file, ~845 MB), `results/web_runs/` (20,559 file, ~2.10 GB), `_trash_20261011/` (~16.1 GB) | Artifact lịch sử rất lớn; `web_runs` có junction và tài liệu tham chiếu, `_trash_` có upload từng dùng | CẦN XÁC MINH manifest/đường dẫn/backup trước xóa; **không dọn hàng loạt** |
| `outputs/roadguard_multiclass_dataset.zip` (~845 MB) | Gói Kaggle được `package_kaggle_dataset.py` và devlog tham chiếu | CẦN XÁC MINH đã lưu nơi khác, checksum và nhu cầu tái hiện trước xóa |
| `outputs/test*.pdf`, `results/test_videos/`, `assets/` | Output/fixture demo; chưa thấy tham chiếu trực tiếp cho PDF thử | CẦN XÁC MINH với chủ sở hữu/UI test trước xóa |
| `docs/ai_mvp/` | Đặc tả mới (01/03/09/10/12), báo cáo audit và kế hoạch; một phần **PROPOSED** | GIỮ |
| `docs/project_export/`, `docs/specs/`, `docs/PIPELINE.md`, `docs/RETENTION.md`, các docs drone/Backend/UI, `docs/superpowers/` | Lịch sử, hợp đồng và nguồn nghiệm thu; có điểm mâu thuẫn với runtime | GIỮ/cần rà soát từng tài liệu trước khi coi là trùng |
| `docs/MVP_AUDIT_AND_SCOPE_DISCOVERY.md`, `docs/README.md`, `reports/agent_reports/PROJECT_COMPLETE.md` | Handoff/kết luận cũ; không được dùng làm bằng chứng MVP đạt | CẦN XÁC MINH nội dung trước hợp nhất/xóa |

Không thấy `AGENTS.md` thực trên repo khi tìm bằng `rg --files`; áp dụng hướng dẫn người dùng cung cấp trong cuộc trò chuyện. Các file chưa được Git theo dõi từ phiên trước được giữ nguyên như tài sản người dùng.

## 2. Đã xóa gì?

**Không xóa file nào.** Kiểm tra xác nhận 13 thư mục `__pycache__` trong `src/`, `tools/`, `tests/` chứa 51 file bytecode (~385,045 byte), có thể tái tạo và không được Git theo dõi; đã thử `Remove-Item -LiteralPath ... -Recurse -Force` trên đúng `tests/__pycache__` và lệnh bị môi trường từ chối trước khi chạy (`blocked by policy`). Không dùng đường vòng để né chính sách. Không có “before/after cleanup” thực tế để tuyên bố; baseline trước cleanup: `python -m unittest discover -s tests -q` = **36 tests OK, 25.278 s**. Kiểm tra lại sau khi chỉ thêm tài liệu: `python -B -m unittest discover -s tests -q` = **36 tests OK, 20.260 s**. Chưa có cleanup nào làm thay đổi code/data.

## 3. Baseline kỹ thuật và phần chưa đủ bằng chứng

- MP4 đọc được: `DJI_0057` 1920×1080/59.94006 fps; `0059`, `0061`, `0064` 1920×1080/29.97003 fps. Không khớp profile 2720×1530/30 fps trong tài liệu. `F:\video-flycam ngày 04-10` đang có 0059/0061/0064 cùng video khác nhưng không thấy 0057 hoặc SRT nào. Chưa có bằng chứng độ cao/gimbal/GPS nên chưa thể nghiệm thu telemetry.
- `outputs/survey_manifest_dji_mini2se.json` ghi SHA256 cho 4 MP4, `missing_srt` cả 4. Manifest tính GSD **5.3248 mm/px theo profile cấu hình 2720 px**, không phải phép đo thực cho video 1920 px. Nếu file 1080p vẫn dùng cùng cảm biến/tiêu cự và H=10 m thì GSD lý thuyết ~**7.54 mm/px**; độ cao thực và nguồn gốc re-encode chưa rõ.
- Pipeline 7 stage có code và được import; unit tests xác minh scaffold. Không có fresh end-to-end trên 4 MP4/SRT với ground truth. `worker_service.py` có endpoint nhưng nhánh “real” vẫn trả kết quả mock; `ui_server.py` mới gọi pipeline real.
- Road gate có mask và overlap, nhưng thiếu mask cho qua; model thất bại/road ratio thấp lại tô vùng trung tâm. Không có exclusion model riêng cho xe/người/bóng. Dedup có heuristic nhưng không bắt buộc persistence nhiều frame; `gps_distance_m` có trong YAML nhưng không thấy được truyền vào deduplicator. Chưa đạt gate A/B/C/D/E.
- `outputs/road_seg_benchmark_report.json` và `mask_filter_validation_report.json` là kết quả lịch sử (50 frame, 98% có mask; báo cáo 6 FP vegetation thành 0); **không phải mIoU/Dice, FP/km hoặc recall có nhãn độc lập**. `outputs/eval_multiclass/metrics.json` là 200 ảnh, 541 detection đều class `crack`; không có đối chiếu ground truth per-class, vì vậy không gọi là AP/mAP.
- `data/merged` báo cáo cấu trúc 21,424 ảnh, 10,111 instance pothole, 21,587 crack, 6,334 nhãn rỗng; không có `bong_troc` và ba lớp MVP còn lại. Nhãn rỗng **không đồng nghĩa** hard negative được xác nhận. `outputs/baseline_training_readiness.json` ghi PASS vì tool nhận `--surveys 4` và `--hard-negatives 6334` do người gọi cung cấp; không dùng PASS đó làm bằng chứng có 4 survey độc lập hay negative đã được review.
- Tài liệu 01 vừa yêu cầu `joint_gap` trong taxonomy sáu lớp vừa nói khe nối bình thường là hard negative: cần BA xác định rõ “joint damage” khác “normal joint gap” để tránh gán nhãn mâu thuẫn.

### Cấu trúc sau audit (không thay đổi)

```text
MP4 + SRT (hiện chỉ có MP4) -> ingestion/manifest -> pipeline 7 stage
  -> road mask -> tiled detector -> mask/bbox filter -> heuristic dedup
  -> ước lượng GSD/GPS -> heuristic/VLM inspect -> JSON/GeoJSON/PDF
                         |                         |
                      UI test bench           worker API: vẫn MOCK
data + notebooks/tools -> train/eval ngoại tuyến -> weights (2 lớp mặc định)
```

## 4. Gói tiếp theo đề xuất

**RG-AI-P0-02 — Khóa dữ liệu khảo sát và baseline có nhãn (chưa train):** (1) lấy đúng bản gốc 4 MP4/SRT, đối chiếu SHA256, resolution/FPS và metadata camera; nếu không có SRT thì ghi rõ `telemetry_missing`; (2) sửa quyết định GSD theo **kích thước file thực** và không phát hành GPS/kích thước như số đo tin cậy khi thiếu telemetry; (3) đóng băng survey-level split + bộ frame có nhãn road/defect/hard-negative do kỹ sư review; (4) replay model hiện tại và báo per-class/FP/km, road leakage, crack recall, duplicate count trên holdout; (5) chỉ sau đó quyết định đổi model, bổ sung 6 lớp và tích hợp real worker. Cần BA chốt định nghĩa `joint_gap`/khe bình thường và ngưỡng FP/km, recall crack, sai số đếm trước khi đánh giá PASS.

Handoff BA: AI hiện có scaffold và weights nhưng chưa đạt MVP; thiếu SRT, video không khớp profile, worker vẫn mock, gate road/temporal/provenance chưa được chứng minh. Không có tài sản gốc bị xóa. Cleanup chỉ có danh sách ứng viên, chưa thực thi do môi trường từ chối xóa.
