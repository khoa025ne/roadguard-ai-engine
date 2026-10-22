# RG-AI-DATA-05 — handoff 2026-10-22

- Scope: hoàn thiện batch 20 hiện có, tách 7 ảnh xiên, local bbox/review UI; không mở batch/train/upload ảnh.
- Sources: DATA-04 report/manifest/triage/contact sheet; SOP `15_FIELD_DATA_COLLECTION_PACK.md`; Gate 09. Local image hashes verified before changes.
- Delivered: `tools/annotate_dji_crack_pilot.py` + HTML/JS UI; revisioned JSON annotations; `docs/ai_mvp/21_RG_AI_DATA_05_ANNOTATION_HANDOFF.md`; sanitized 20-row handoff CSV (không ảnh/GPS/đường dẫn cá nhân).
- Invariants: 7 provisional oblique cannot be approved for nadir branch; no auto-GT/negative; approval requires named reviewer and explicit confirmation; all revision files stay local ignored `data/`.
- Pending: assign annotator/reviewer, actual 20-image timing and review, choose mask tool and any future oblique branch. No mask tool configured or GT approved.
- Verification: focused UI/extraction tests 5/5 PASS; toàn bộ `python -m unittest discover -s tests -q` 52/52 PASS; `node --check` PASS; GET UI/JS/20 items/JPEG/annotation trên server local PASS. Chưa có người thao tác nhãn/duyệt thực tế.
- Git: chỉ stage code/test/docs và manifest handoff đã lược GPS; bỏ qua `data/`, MP4/SRT và manifest DJI nguồn có GPS. Ghi commit/push SHA khi hoàn tất.
