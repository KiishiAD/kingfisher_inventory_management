"""Small PDF export helpers for list and detail downloads."""

from __future__ import annotations

import json
from decimal import Decimal
from io import BytesIO
from typing import Iterable

from django.http import HttpResponse
from django.utils import timezone
from django.utils.text import slugify
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _table_col_widths(headers: list[str], available_width: float) -> list[float]:
    """Allocate stable column widths so export data is visible instead of squeezed/clipped."""
    count = max(len(headers), 1)
    if count == 1:
        return [available_width]

    lowered = [str(h).lower() for h in headers]
    weights = []
    for h in lowered:
        if any(key in h for key in ("product", "notes", "details", "event", "description")):
            weights.append(2.4)
        elif any(key in h for key in ("when", "created", "updated", "processed", "received")):
            weights.append(1.7)
        elif any(key in h for key in ("sku", "supplier", "requester", "approver", "created by")):
            weights.append(1.5)
        else:
            weights.append(1.0)
    total = sum(weights) or count
    return [available_width * (w / total) for w in weights]


_EMPTY = "—"


def clean_text(value) -> str:
    if value is None:
        return _EMPTY
    if isinstance(value, Decimal):
        return f"{value:,.2f}"
    text = str(value).strip()
    return text or _EMPTY


def _paragraph(value, style):
    text = clean_text(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(text, style)


def _response(buffer: BytesIO, filename: str) -> HttpResponse:
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _safe_filename(title: str) -> str:
    return f"{slugify(title) or 'export'}.pdf"


def render_table_pdf(
    *,
    title: str,
    headers: Iterable,
    rows: Iterable[Iterable],
    subtitle: str | None = None,
    filename: str | None = None,
    landscape_page: bool = True,
) -> HttpResponse:
    """Render a compact table PDF and return it as a download response."""
    buffer = BytesIO()
    page_size = landscape(A4) if landscape_page else A4
    doc = SimpleDocTemplate(
        buffer,
        pagesize=page_size,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
    )
    styles = getSampleStyleSheet()
    normal = ParagraphStyle(
        "ListExportBody",
        parent=styles["BodyText"],
        fontSize=7,
        leading=8,
        textColor=colors.HexColor("#111827"),
    )
    header_style = ParagraphStyle(
        "ListExportHeader",
        parent=styles["BodyText"],
        fontSize=7,
        leading=8,
        fontName="Helvetica-Bold",
        textColor=colors.white,
    )

    story = [Paragraph(clean_text(title), styles["Title"])]
    generated = timezone.localtime(timezone.now()).strftime("Generated %Y-%m-%d %H:%M")
    story.append(Paragraph(generated, styles["Normal"]))
    if subtitle:
        story.append(Paragraph(clean_text(subtitle), styles["Normal"]))
    story.append(Spacer(1, 6))

    header_values = [clean_text(h) for h in headers]
    row_values = [[clean_text(cell) for cell in row] for row in rows]
    if not header_values:
        header_values = ["Result"]
    if not row_values:
        row_values = [["No matching records"] + [""] * (len(header_values) - 1)]

    data = [[_paragraph(h, header_style) for h in header_values]]
    data.extend([[_paragraph(cell, normal) for cell in row] for row in row_values])

    available_width = page_size[0] - doc.leftMargin - doc.rightMargin
    table = Table(data, repeatRows=1, colWidths=_table_col_widths(header_values, available_width))
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f4e79")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cccccc")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f9fb")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(table)
    doc.build(story)
    buffer.seek(0)
    return _response(buffer, filename or _safe_filename(title))


def render_key_value_pdf(
    *,
    title: str,
    sections: list[tuple[str, list[tuple[str, object]]]],
    tables: list[tuple[str, list[str], list[list[object]]]] | None = None,
    filename: str | None = None,
) -> HttpResponse:
    buffer = BytesIO()
    page_size = landscape(A4)
    doc = SimpleDocTemplate(
        buffer,
        pagesize=page_size,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
    )
    available_width = page_size[0] - doc.leftMargin - doc.rightMargin
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ExportTitle",
        parent=styles["Title"],
        fontSize=20,
        leading=24,
        textColor=colors.white,
        alignment=0,
        spaceAfter=4,
    )
    generated_style = ParagraphStyle(
        "Generated",
        parent=styles["Normal"],
        fontSize=9,
        leading=11,
        textColor=colors.HexColor("#e5e7eb"),
    )
    normal = ParagraphStyle("ExportBody", parent=styles["BodyText"], fontSize=9, leading=12)
    label_style = ParagraphStyle(
        "ExportLabel",
        parent=normal,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#111827"),
    )
    section_style = ParagraphStyle(
        "ExportSection",
        parent=styles["Heading2"],
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#111827"),
        spaceBefore=6,
        spaceAfter=6,
    )
    header_style = ParagraphStyle(
        "ExportTableHeader",
        parent=normal,
        fontName="Helvetica-Bold",
        textColor=colors.white,
    )

    generated = timezone.localtime(timezone.now()).strftime("Generated %Y-%m-%d %H:%M")
    title_block = Table(
        [[Paragraph(clean_text(title), title_style)], [Paragraph(generated, generated_style)]],
        colWidths=[available_width],
    )
    title_block.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#111827")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#111827")),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story = [title_block, Spacer(1, 10)]

    for heading, values in sections:
        story.append(Paragraph(clean_text(heading), section_style))
        data = [[_paragraph(label, label_style), _paragraph(value, normal)] for label, value in values]
        table = Table(data, colWidths=[48 * mm, available_width - (48 * mm)])
        table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d1d5db")),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eef2f7")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.extend([table, Spacer(1, 8)])

    for heading, headers, rows in tables or []:
        story.append(Paragraph(clean_text(heading), section_style))
        if rows:
            data = [[_paragraph(h, header_style) for h in headers]]
            data.extend([[_paragraph(cell, normal) for cell in row] for row in rows])
            table = Table(data, repeatRows=1, colWidths=_table_col_widths(headers, available_width))
        else:
            data = [[_paragraph("No records for this section.", normal)]]
            table = Table(data, colWidths=[available_width])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f4e79")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d1d5db")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f9fb")]),
        ]))
        story.extend([table, Spacer(1, 8)])

    doc.build(story)
    buffer.seek(0)
    return _response(buffer, filename or _safe_filename(title))


def decode_table_payload(post_data):
    """Decode JSON table-export payload submitted by list pages."""
    return {
        "title": post_data.get("title") or "List export",
        "subtitle": post_data.get("subtitle") or "Current visible rows",
        "headers": json.loads(post_data.get("headers") or "[]"),
        "rows": json.loads(post_data.get("rows") or "[]"),
    }
