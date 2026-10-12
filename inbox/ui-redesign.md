# TASK: UI-REDESIGN — Redesign toàn bộ UI RoadGuard (design-first)
status: pending
branch: feature/target-band-api-worker

> Copy file này vào `F:\train AI đồ án\inbox\` — Inbox Runner sẽ tự pick up trong vòng 30 phút.

## Bối cảnh
Web UI hiện tại (`src/api/ui_server.py`) đã qua 1 vòng ui-polish theo spec CŨ. Giờ redesign lại toàn bộ
theo hướng design-first: viết design doc trước, code sau; tách/gắn được vào dự án tổng sau này.

## Spec (làm đúng từng bước)

### 1. KIỂM KÊ
Liệt kê TẤT CẢ màn hình/trang hiện có của Web UI (upload, task list, inspection detail, curation,
export, settings...) — ghi file:dòng từng template/route.

### 2. DESIGN-FIRST
Trước khi code, viết `docs/UI_DESIGN.md` mô tả: cấu trúc từng màn hình, luồng điều hướng, component
dùng chung, và design tokens Thủy Mệnh áp dụng:
- Nền #FFFFFF → #F4F7FA → #E9EFF5; chữ #0A2540 / #3D4F61 / #7A8FA3
- Accent #1E88C7; badge nền #D6E9F5; viền #D5DEE8; tối #061826; danger #E5484D
- Font: Be Vietnam Pro / Azeret Mono IN HOA / Inter; nút bo 4px, card bo 12px, zero-shadow

### 3. REDESIGN TẤT CẢ màn hình theo design doc
Không chỉ đổi màu: chuẩn hóa layout, spacing, typography, và các trạng thái empty/error/loading.

### 4. THIẾT KẾ ĐỂ TÁCH/GẮN ĐƯỢC (chuẩn bị cho dự án tổng sau này)
- UI giao tiếp với backend CHỈ qua API contracts đã định nghĩa (`/api/*`) — cấm gọi lén hàm nội bộ.
- Component dùng chung (layout, table, badge, modal...) tách riêng để tái sử dụng.
- Viết `docs/UI_INTEGRATION.md`: các điểm tích hợp (mount point, API cần dùng, config cần thiết)
  để sau này gắn module này vào dự án tổng mà không phải sửa code lõi.

### 5. GATE CHỐNG AI-SLOP ĐO ĐƯỢC (port từ Nutlope/hallmark, MIT)
Chạy cho TỪNG màn hình. Mọi câu trả lời phải là KHÔNG vi phạm — vi phạm thì sửa ngay:
1. Accent ≤5% diện tích màn hình — accent chỉ cho action chính + trạng thái
2. Không #000/#fff thuần (dùng tokens Thủy Mệnh); neutral có tint, cấm xám "chết"
3. 0 giá trị màu/font inline — mọi thứ qua token đặt tên trong `:root`
4. Heading luôn roman — cấm italic kể cả nhấn mạnh 1 từ
5. Tối đa 3 font family (Be Vietnam Pro / Azeret Mono / Inter)
6. Body ≥4.5:1 contrast; chữ nút không ≈ màu nền nút
7. Component tương tác đủ 8 states: default / hover / focus-visible / active / disabled /
   loading / error / success; border-width không đổi giữa states; focus ring hiện NGAY (không fade)
8. Cấm `transition-all`; mỗi element 1 hiệu ứng hover; mọi motion có `prefers-reduced-motion` fallback
9. Không scroll ngang 320→1920px (`overflow-x: clip` trên html+body); spacing theo thang 4pt
10. Số liệu #TẠM (GSD, severity, metrics demo) → hiển thị "—" + ô "chờ xác nhận", KHÔNG bịa số cho đẹp
11. Copy tiếng Việt: cấm "được...bởi", cấm chuỗi "của" liên hoàn, cấm giọng chatbot/sáo ngữ

### 6. PRE-EMIT SELF-CRITIQUE (bắt buộc trước mỗi push)
Tự chấm TỪNG màn hình theo 6 trục 1–5, trục nào <3 thì sửa lại rồi mới push:
**P**hilosophy (có lập trường hay layout cho có) · **H**ierarchy (2 giây thấy chính–phụ) ·
**E**xecution (đúng token/spec) · **S**pecificity (đúng màn hình này, không generic) ·
**R**estraint (cắt hết thứ thừa) · **V**ariety (không trùng cấu trúc màn hình trước).
Ghi vào báo cáo theo mẫu: `P? H? E? S? R? V? · gates fail: không / có (liệt kê)`.
Mở đầu mỗi file giao: `/* ck-design-kit · screen: <tên> · P? H? E? S? R? V? */`

## DONE khi
`docs/UI_DESIGN.md` + `docs/UI_INTEGRATION.md` hoàn chỉnh, tất cả màn hình đã redesign,
gates pass từng màn hình, self-critique ≥3 mọi trục, UI chạy không lỗi.

## Kỷ luật push (LUẬT SẮT — xem `.agents/rules/git_workflow.md`)
Kết thúc task: viết báo cáo vào `reports/agent_reports/ui-redesign.md` → git add/commit/push →
verify `git log origin/feature/target-band-api-worker --oneline -1`. Push fail → thử lại 1 lần →
vẫn fail thì ghi rõ lý do vào báo cáo rồi mới dừng.
