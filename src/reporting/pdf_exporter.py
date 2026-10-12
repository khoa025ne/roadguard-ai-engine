"""
src/reporting/pdf_exporter.py — Module Xuất Báo Cáo PDF Chuyên Nghiệp Theo Design Tokens Thủy Mệnh
====================================================================================================
Triển khai bộ sinh báo cáo kỹ thuật mặt đường RoadGuard AI:
1. Design System Thủy Mệnh:
   - Nền: #FFFFFF / #F4F7FA / #E9EFF5
   - Chữ: #0A2540 (tiêu đề/chữ chính), #3D4F61 (chữ phụ), #7A8FA3 (nhãn phụ)
   - Accent: #1E88C7
   - Badge nền: #D6E9F5, chữ #0A2540
   - Viền: 1px solid #D5DEE8
   - Danger: #E5484D (chỉ áp dụng cho mức độ CRITICAL / HIGH)
   - Card bo góc: 12px, KHÔNG box-shadow
   - Nút bo góc: 4px
   - Typography: Be Vietnam Pro / Inter / ArialVN

2. Động cơ sinh PDF:
   - WeasyPrint (nếu có thư viện hệ thống Pango/GTK)
   - ReportLab Fallback (chuẩn Python thuần túy, hoạt động 100% độc lập không cần GTK trên Windows)
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

# ReportLab imports cho Native PDF Renderer
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


# Đăng ký font TrueType tiếng Việt trên Windows / Linux
def _register_vietnamese_fonts():
    font_registered = False
    candidates = [
        ("ArialVN", "C:/Windows/Fonts/arial.ttf"),
        ("ArialVNBold", "C:/Windows/Fonts/arialbd.ttf"),
        ("SegoeVN", "C:/Windows/Fonts/segoeui.ttf"),
        ("SegoeVNBold", "C:/Windows/Fonts/segoeuib.ttf")
    ]
    for name, path in candidates:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(name, path))
                font_registered = True
            except Exception:
                pass
    return font_registered


_FONTS_INITIALIZED = _register_vietnamese_fonts()


def generate_html_report(report_data: Dict[str, Any], output_html_path: Optional[Union[str, Path]] = None) -> str:
    """
    Sinh mã HTML báo cáo giám định định dạng chuẩn Design System Thủy Mệnh.
    """
    summary = report_data.get("summary", {})
    task_id = report_data.get("task_id") or report_data.get("processing_job_id", "N/A")
    video_path = report_data.get("video_path", "N/A")
    model_name = report_data.get("model_path") or report_data.get("model_version_id", "roadguard_best_15k.pt")
    if isinstance(model_name, str):
        model_name = Path(model_name).name

    total_defects = summary.get("total_defects") or report_data.get("total_detections", 0)
    pothole_count = summary.get("pothole_count", 0)
    crack_count = summary.get("crack_count", 0)
    critical_count = summary.get("critical_count", 0)
    exec_time = summary.get("total_time_seconds") or report_data.get("execution_time_seconds", 0.0)

    detections = report_data.get("detections", [])
    if not detections and "all_defects" in report_data:
        detections = report_data.get("all_defects", [])

    # Sinh danh sách hàng bảng
    table_rows = []
    for idx, det in enumerate(detections, 1):
        c_code = det.get("defect_type_code") or det.get("class_name", "defect")
        fine_tag = det.get("fine_tag") or det.get("fine_tag_code", c_code)
        sev = str(det.get("severity", "MEDIUM")).upper()
        width = det.get("estimated_width") or det.get("estimated_width_mm", 0.0)
        length = det.get("estimated_length") or det.get("estimated_length_m", 0.0)
        
        # Tọa độ GPS WGS84
        glat = det.get("ground_latitude")
        glon = det.get("ground_longitude")
        if glat and glon:
            gps_str = f"{glat:.6f}, {glon:.6f}"
        elif det.get("geometry"):
            gps_str = str(det.get("geometry"))
        else:
            gps_str = "Chưa có GPS"

        reason = det.get("reasoning") or det.get("structural_risk") or "KTV xác nhận hợp lệ"

        sev_badge_class = "badge-low"
        if sev in ["CRITICAL", "HIGH"]:
            sev_badge_class = "badge-danger"
        elif sev == "MEDIUM":
            sev_badge_class = "badge-medium"

        table_rows.append(f"""
        <tr>
            <td style="text-align: center; font-weight: bold;">#{idx}</td>
            <td><strong>{c_code.capitalize()}</strong><br><span style="color: #7A8FA3; font-size: 11px;">{fine_tag}</span></td>
            <td><span class="badge {sev_badge_class}">{sev}</span></td>
            <td>{width:.1f} mm<br><span style="color: #7A8FA3; font-size: 11px;">Dài: {length:.2f} m</span></td>
            <td><span style="font-family: monospace; font-size: 11px;">{gps_str}</span></td>
            <td style="font-size: 12px; color: #3D4F61;">{reason}</td>
        </tr>
        """)

    if not table_rows:
        table_rows.append("""
        <tr>
            <td colspan="6" style="text-align: center; padding: 24px; color: #7A8FA3;">
                Không phát hiện khuyết tật kết cấu nguy hiểm trên tuyến đường này (Toàn bộ báo động giả đã được KTV lọc bỏ).
            </td>
        </tr>
        """)

    html_content = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <title>Báo Cáo Giám Định Kỹ Thuật Mặt Đường — {task_id}</title>
    <style>
        @page {{
            size: A4;
            margin: 15mm;
        }}
        body {{
            font-family: 'Be Vietnam Pro', 'Inter', Arial, sans-serif;
            background-color: #FFFFFF;
            color: #0A2540;
            margin: 0;
            padding: 0;
            -webkit-print-color-adjust: exact;
        }}
        .header {{
            border-bottom: 2px solid #1E88C7;
            padding-bottom: 16px;
            margin-bottom: 24px;
            display: flex;
            justify-content: space-between;
            align-items: flex-end;
        }}
        .logo-title h1 {{
            margin: 0;
            font-size: 22px;
            color: #0A2540;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .logo-title p {{
            margin: 4px 0 0 0;
            color: #1E88C7;
            font-size: 13px;
            font-weight: 600;
        }}
        .meta-info {{
            text-align: right;
            font-size: 12px;
            color: #3D4F61;
            line-height: 1.5;
        }}
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 12px;
            margin-bottom: 24px;
        }}
        .card {{
            background-color: #F4F7FA;
            border: 1px solid #D5DEE8;
            border-radius: 12px;
            padding: 14px;
            box-shadow: none !important;
        }}
        .card-label {{
            font-size: 11px;
            text-transform: uppercase;
            color: #7A8FA3;
            font-weight: 700;
            margin-bottom: 4px;
        }}
        .card-value {{
            font-size: 24px;
            font-weight: 700;
            color: #0A2540;
        }}
        .card-value.accent {{
            color: #1E88C7;
        }}
        .card-value.danger {{
            color: #E5484D;
        }}
        .table-container {{
            margin-top: 16px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
        }}
        th {{
            background-color: #F4F7FA;
            color: #0A2540;
            text-align: left;
            padding: 10px 12px;
            font-weight: 700;
            border-top: 1px solid #D5DEE8;
            border-bottom: 2px solid #D5DEE8;
        }}
        td {{
            padding: 10px 12px;
            border-bottom: 1px solid #E9EFF5;
            vertical-align: top;
        }}
        .badge {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 10px;
            font-weight: 700;
            text-transform: uppercase;
        }}
        .badge-low {{
            background-color: #D6E9F5;
            color: #0A2540;
        }}
        .badge-medium {{
            background-color: #E9EFF5;
            color: #0A2540;
            border: 1px solid #D5DEE8;
        }}
        .badge-danger {{
            background-color: #E5484D;
            color: #FFFFFF;
        }}
        .footer {{
            margin-top: 32px;
            border-top: 1px solid #D5DEE8;
            padding-top: 12px;
            font-size: 11px;
            color: #7A8FA3;
            display: flex;
            justify-content: space-between;
        }}
    </style>
</head>
<body>
    <div class="header">
        <div class="logo-title">
            <h1>RoadGuard AI — Báo Cáo Giám Định Mặt Đường</h1>
            <p>Hệ Thống Phân Tích Khuyết Tật Giao Thông & Kiểm Định Hạ Tầng Bê Tông</p>
        </div>
        <div class="meta-info">
            <strong>Mã nhiệm vụ:</strong> {task_id}<br>
            <strong>Video khảo sát:</strong> {video_path}<br>
            <strong>Mô hình AI:</strong> {model_name}<br>
            <strong>Thời gian tạo:</strong> {time.strftime('%Y-%m-%d %H:%M:%S')}
        </div>
    </div>

    <div class="summary-grid">
        <div class="card">
            <div class="card-label">Tổng khuyết tật</div>
            <div class="card-value accent">{total_defects}</div>
        </div>
        <div class="card">
            <div class="card-label">Ổ gà (Potholes)</div>
            <div class="card-value">{pothole_count}</div>
        </div>
        <div class="card">
            <div class="card-label">Vết nứt (Cracks)</div>
            <div class="card-value">{crack_count}</div>
        </div>
        <div class="card">
            <div class="card-label">Nguy cơ khẩn cấp</div>
            <div class="card-value danger">{critical_count}</div>
        </div>
    </div>

    <div class="table-container">
        <table>
            <thead>
                <tr>
                    <th style="width: 40px; text-align: center;">STT</th>
                    <th style="width: 140px;">Phân loại</th>
                    <th style="width: 90px;">Mức độ</th>
                    <th style="width: 90px;">Kích thước 2D</th>
                    <th style="width: 130px;">Tọa độ GPS WGS84</th>
                    <th>Nhận định KTV / Khuyến nghị</th>
                </tr>
            </thead>
            <tbody>
                {''.join(table_rows)}
            </tbody>
        </table>
    </div>

    <div class="footer">
        <div>Hệ Thống RoadGuard AI • Báo cáo tự hành chuẩn hóa Kiến trúc A</div>
        <div>Thời gian xử lý: {exec_time:.2f}s</div>
    </div>
</body>
</html>
"""

    if output_html_path:
        out_p = Path(output_html_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "w", encoding="utf-8") as f:
            f.write(html_content)

    return html_content


def _export_pdf_via_reportlab(report_data: Dict[str, Any], output_pdf_path: Union[str, Path]) -> str:
    """
    Sinh file PDF chuẩn mực bằng ReportLab Platypus Engine, áp dụng toàn bộ Design Tokens Thủy Mệnh.
    """
    out_pdf = Path(output_pdf_path)
    out_pdf.parent.mkdir(parents=True, exist_ok=True)

    font_base = "ArialVN" if _FONTS_INITIALIZED else "Helvetica"
    font_bold = "ArialVNBold" if _FONTS_INITIALIZED else "Helvetica-Bold"

    doc = SimpleDocTemplate(
        str(out_pdf),
        pagesize=A4,
        rightMargin=28,
        leftMargin=28,
        topMargin=28,
        bottomMargin=28
    )

    styles = getSampleStyleSheet()

    # Style Tokens
    c_navy = colors.HexColor("#0A2540")
    c_slate = colors.HexColor("#3D4F61")
    c_gray = colors.HexColor("#7A8FA3")
    c_accent = colors.HexColor("#1E88C7")
    c_bg_light = colors.HexColor("#F4F7FA")
    c_border = colors.HexColor("#D5DEE8")
    c_danger = colors.HexColor("#E5484D")

    style_title = ParagraphStyle(
        'DocTitle',
        fontName=font_bold,
        fontSize=15,
        leading=18,
        textColor=c_navy
    )
    style_subtitle = ParagraphStyle(
        'DocSubTitle',
        fontName=font_bold,
        fontSize=9,
        leading=12,
        textColor=c_accent
    )
    style_meta = ParagraphStyle(
        'DocMeta',
        fontName=font_base,
        fontSize=8,
        leading=11,
        textColor=c_slate,
        alignment=2 # Right
    )
    style_th = ParagraphStyle(
        'TableHead',
        fontName=font_bold,
        fontSize=8.5,
        leading=11,
        textColor=c_navy
    )
    style_td = ParagraphStyle(
        'TableText',
        fontName=font_base,
        fontSize=8,
        leading=10.5,
        textColor=c_slate
    )
    style_td_bold = ParagraphStyle(
        'TableTextBold',
        fontName=font_bold,
        fontSize=8,
        leading=10.5,
        textColor=c_navy
    )

    elements = []

    # 1. Header
    summary = report_data.get("summary", {})
    task_id = report_data.get("task_id") or report_data.get("processing_job_id", "N/A")
    video_path = report_data.get("video_path", "N/A")
    model_name = report_data.get("model_path") or report_data.get("model_version_id", "roadguard_best_15k.pt")
    if isinstance(model_name, str):
        model_name = Path(model_name).name

    header_table_data = [
        [
            Paragraph("<b>ROADGUARD AI — BÁO CÁO GIÁM ĐỊNH MẶT ĐƯỜNG</b>", style_title),
            Paragraph(f"<b>Mã nhiệm vụ:</b> {task_id}<br/><b>Thời gian:</b> {time.strftime('%Y-%m-%d %H:%M:%S')}", style_meta)
        ],
        [
            Paragraph("HỆ THỐNG PHÂN TÍCH KHUYẾT TẬT GIAO THÔNG & KIỂM ĐỊNH HẠ TẦNG", style_subtitle),
            Paragraph(f"<b>Mô hình:</b> {model_name}<br/><b>Video:</b> {Path(video_path).name}", style_meta)
        ]
    ]
    t_header = Table(header_table_data, colWidths=[330, 210])
    t_header.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('LINEBELOW', (0,1), (-1,1), 1.5, c_accent)
    ]))
    elements.append(t_header)
    elements.append(Spacer(1, 14))

    # 2. Metric Summary Cards
    total_defects = summary.get("total_defects") or report_data.get("total_detections", 0)
    pothole_count = summary.get("pothole_count", 0)
    crack_count = summary.get("crack_count", 0)
    critical_count = summary.get("critical_count", 0)

    card_data = [
        [
            Paragraph("TỔNG KHUYẾT TẬT", ParagraphStyle('C1', fontName=font_bold, fontSize=7.5, textColor=c_gray)),
            Paragraph("Ổ GÀ (POTHOLES)", ParagraphStyle('C2', fontName=font_bold, fontSize=7.5, textColor=c_gray)),
            Paragraph("VẾT NỨT (CRACKS)", ParagraphStyle('C3', fontName=font_bold, fontSize=7.5, textColor=c_gray)),
            Paragraph("KHẨN CẤP (CRITICAL)", ParagraphStyle('C4', fontName=font_bold, fontSize=7.5, textColor=c_gray))
        ],
        [
            Paragraph(f"<b>{total_defects}</b>", ParagraphStyle('V1', fontName=font_bold, fontSize=16, textColor=c_accent)),
            Paragraph(f"<b>{pothole_count}</b>", ParagraphStyle('V2', fontName=font_bold, fontSize=16, textColor=c_navy)),
            Paragraph(f"<b>{crack_count}</b>", ParagraphStyle('V3', fontName=font_bold, fontSize=16, textColor=c_navy)),
            Paragraph(f"<b>{critical_count}</b>", ParagraphStyle('V4', fontName=font_bold, fontSize=16, textColor=c_danger))
        ]
    ]
    t_cards = Table(card_data, colWidths=[135, 135, 135, 135])
    t_cards.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), c_bg_light),
        ('BOX', (0,0), (-1,-1), 1.0, c_border),
        ('INNERGRID', (0,0), (-1,-1), 0.5, c_border),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
    ]))
    elements.append(t_cards)
    elements.append(Spacer(1, 14))

    # 3. Detections Table
    detections = report_data.get("detections", [])
    if not detections and "all_defects" in report_data:
        detections = report_data.get("all_defects", [])

    table_data = [
        [
            Paragraph("STT", style_th),
            Paragraph("Phân loại", style_th),
            Paragraph("Mức độ", style_th),
            Paragraph("Kích thước 2D", style_th),
            Paragraph("GPS WGS84", style_th),
            Paragraph("Nhận định KTV / Khuyến nghị", style_th)
        ]
    ]

    for idx, det in enumerate(detections, 1):
        c_code = det.get("defect_type_code") or det.get("class_name", "defect")
        fine_tag = det.get("fine_tag") or det.get("fine_tag_code", c_code)
        sev = str(det.get("severity", "MEDIUM")).upper()
        width = det.get("estimated_width") or det.get("estimated_width_mm", 0.0)
        length = det.get("estimated_length") or det.get("estimated_length_m", 0.0)

        glat = det.get("ground_latitude")
        glon = det.get("ground_longitude")
        if glat and glon:
            gps_txt = f"{glat:.6f},<br/>{glon:.6f}"
        elif det.get("geometry"):
            gps_txt = str(det.get("geometry"))[:22]
        else:
            gps_txt = "Chưa có GPS"

        reason = det.get("reasoning") or det.get("structural_risk") or "KTV xác nhận hợp lệ"

        sev_color = c_navy
        if sev in ["CRITICAL", "HIGH"]:
            sev_color = c_danger

        table_data.append([
            Paragraph(f"<b>#{idx}</b>", style_td_bold),
            Paragraph(f"<b>{c_code.capitalize()}</b><br/><font color='#7A8FA3' size='7'>{fine_tag}</font>", style_td),
            Paragraph(f"<b><font color='{sev_color.hexval()}'>{sev}</font></b>", style_td_bold),
            Paragraph(f"Rộng: {width:.1f}mm<br/><font color='#7A8FA3' size='7'>Dài: {length:.2f}m</font>", style_td),
            Paragraph(f"<font size='7'>{gps_txt}</font>", style_td),
            Paragraph(reason[:140] + ("..." if len(reason) > 140 else ""), style_td)
        ])

    if len(table_data) == 1:
        table_data.append([
            Paragraph("-", style_td),
            Paragraph("Không có khuyết tật nguy hiểm", style_td),
            Paragraph("NONE", style_td),
            Paragraph("-", style_td),
            Paragraph("-", style_td),
            Paragraph("Tuyến đường kiểm tra đạt tiêu chuẩn an toàn (0 khuyết tật kết cấu tồn đọng).", style_td)
        ])

    t_dets = Table(table_data, colWidths=[30, 95, 60, 75, 95, 185], repeatRows=1)
    t_dets.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), c_bg_light),
        ('GRID', (0,0), (-1,-1), 0.5, c_border),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('VALIGN', (0,0), (-1,-1), 'TOP')
    ]))
    elements.append(t_dets)

    # 4. Build Document
    doc.build(elements)
    return str(out_pdf)


def export_pdf_report(
    report_input: Union[Dict[str, Any], str, Path],
    output_pdf_path: Union[str, Path]
) -> str:
    """
    API chính xuất báo cáo PDF:
    - Nhận vào dict kết quả inspection hoặc đường dẫn file JSON.
    - Sinh đồng thời file HTML chuẩn token Thủy Mệnh.
    - Thử xuất qua WeasyPrint trước (nếu môi trường có hỗ trợ Pango).
    - Tự động fallback sang ReportLab Platypus Engine bảo đảm luôn xuất thành công 100%.
    """
    if isinstance(report_input, (str, Path)):
        p = Path(report_input)
        if not p.exists():
            raise FileNotFoundError(f"Không tìm thấy file báo cáo: {p}")
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = report_input

    out_pdf = Path(output_pdf_path)
    out_html = out_pdf.with_suffix(".html")

    # 1. Sinh file HTML báo cáo
    generate_html_report(data, out_html)

    # 2. Thử sinh qua WeasyPrint nếu có
    weasyprint_success = False
    try:
        import weasyprint
        doc = weasyprint.HTML(filename=str(out_html))
        doc.write_pdf(str(out_pdf))
        weasyprint_success = True
    except Exception:
        weasyprint_success = False

    # 3. Fallback sang ReportLab Native Generator
    if not weasyprint_success:
        _export_pdf_via_reportlab(data, out_pdf)

    return str(out_pdf)


def main():
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    import argparse
    parser = argparse.ArgumentParser(description="RoadGuard AI — Xuất Báo Cáo PDF Chuyên Nghiệp")
    parser.add_argument("--report", type=str, required=True, help="Đường dẫn file inspection_report.json")
    parser.add_argument("--output", type=str, default="outputs/reports/inspection_report.pdf", help="Đường dẫn file PDF xuất ra")
    args = parser.parse_args()

    pdf_path = export_pdf_report(args.report, args.output)
    print(f"[SUCCESS] Da xuat bao cao PDF thanh cong: {pdf_path} ({os.path.getsize(pdf_path)} bytes)")


if __name__ == "__main__":
    main()
