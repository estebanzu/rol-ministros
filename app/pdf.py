from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

CONTACT_NAME = "Gabriela Mora Aguilar"
CONTACT_PHONE = "+506 8817 2417"
CONTACT_LINE = f"Contacto: {CONTACT_NAME}  ·  Tel: {CONTACT_PHONE}"

MARGIN = 7 * mm
PAGE_WIDTH, PAGE_HEIGHT = A4


def _styles() -> dict:
    return {
        "title": ParagraphStyle(
            "title", fontName="Helvetica-Bold", fontSize=13, leading=16, spaceAfter=2
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#444444"),
            spaceAfter=2,
        ),
        "day": ParagraphStyle(
            "day",
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            spaceBefore=8,
            spaceAfter=3,
        ),
        "cell": ParagraphStyle("cell", fontName="Helvetica", fontSize=8.5, leading=10.5),
        "cell-bold": ParagraphStyle(
            "cell-bold", fontName="Helvetica-Bold", fontSize=8.5, leading=10.5
        ),
        "warn": ParagraphStyle(
            "warn",
            fontName="Helvetica",
            fontSize=8.5,
            leading=10.5,
            textColor=colors.HexColor("#b3261e"),
        ),
    }


def _on_page(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#111111"))
    canvas.setLineWidth(0.5)
    y = 4 * mm
    canvas.line(MARGIN, y + 3.2 * mm, PAGE_WIDTH - MARGIN, y + 3.2 * mm)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.HexColor("#111111"))
    canvas.drawString(MARGIN, y, CONTACT_LINE)
    canvas.drawRightString(PAGE_WIDTH - MARGIN, y, f"Página {doc.page}")
    canvas.restoreState()


def build_roster_pdf(data: dict) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=8 * mm,
        bottomMargin=13 * mm,
        title="Rol de Ministros de la Comunión",
        author=CONTACT_NAME,
    )
    st = _styles()
    from reportlab.platypus import Flowable
    story: list[Flowable] = []

    story.append(Paragraph("Ministros de la Comunión", st["title"]))
    story.append(Paragraph(f"Rol semanal: {data['week_start_display']}", st["subtitle"]))
    if data.get("generated_at"):
        story.append(Paragraph(f"Generado: {data['generated_at']}", st["subtitle"]))
    story.append(Spacer(1, 4 * mm))

    if data["status"] == "con_faltantes" and data.get("warnings"):
        story.append(Paragraph("Rol con faltantes", st["cell-bold"]))
        story.append(
            ListFlowable(
                [ListItem(Paragraph(w, st["warn"]), leftIndent=6) for w in data["warnings"]],
                bulletType="bullet",
                start="•",
                leftIndent=8,
            )
        )
        story.append(Spacer(1, 3 * mm))

    content_width = PAGE_WIDTH - 2 * MARGIN
    col_time = 22 * mm
    col_place = 55 * mm
    col_min = content_width - col_time - col_place
    header = [Paragraph(h, st["cell-bold"]) for h in ("Hora", "Lugar", "Ministros")]

    for day in data["days"]:
        if not day["masses"]:
            continue
        story.append(Paragraph(f"{day['label']} {day['date']}", st["day"]))
        rows = [header]
        for m in day["masses"]:
            names = ", ".join(x["name"] for x in m["ministers"]) if m["ministers"] else "—"
            if not m["complete"]:
                faltan = m["min_ministers"] - m["assigned"]
                names += f"  (faltan {faltan})"
                ministers_cell = Paragraph(names, st["warn"])
            else:
                ministers_cell = Paragraph(names, st["cell"])
            rows.append(
                [
                    Paragraph(m["time"], st["cell"]),
                    Paragraph(m["location"], st["cell"]),
                    ministers_cell,
                ]
            )
        table = Table(rows, colWidths=[col_time, col_place, col_min], repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#bbbbbb")),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 2.5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
                ]
            )
        )
        story.append(table)

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return buf.getvalue()
