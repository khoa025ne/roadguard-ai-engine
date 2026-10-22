# 07 — Chính sách VLM

## Khi nào gọi

Chỉ gọi VLM cho confidence vùng xám, mâu thuẫn detector/rule/track, candidate hard-negative khó, hoặc cần mô tả kỹ thuật cho kỹ sư. Không gửi mọi frame/crop.

## Input

Một request gồm overview frame có đánh số candidate, tối đa vài crop có context, metadata không nhạy cảm và instruction yêu cầu JSON schema cố định.

## Output bắt buộc

`is_road_surface`, `is_defect`, `class`, `severity_hint`, `reason_code`, `needs_field_check`, `confidence`.

VLM trả `review_suggestion`; không được tự chuyển sang `accepted`, không được tự ghi kích thước nghiệm thu, không được thay thế detector provenance.

## Chi phí và an toàn

Batch candidate, cache theo hash ảnh, giới hạn kích thước ảnh, retry có backoff, fallback rule-based khi API lỗi. Ghi model/provider/version và chi phí ước tính trong run manifest. Không gửi raw video; chỉ gửi crop đã được phép.
