import os
from pathlib import Path
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY


def build_certificate_pdf(
    output_path: str,
    recipient_name: str,
    event_name: str,
    certificate_date: str,
    certificate_id: str,
):
    """
    Builds a professional landscape PDF certificate using ReportLab canvas drawing.
    """
    # Create parent directory if needed
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Page setup: Letter landscape (11 x 8.5 inches) -> 792 x 612 points
    c = canvas.Canvas(output_path, pagesize=landscape(letter))
    width, height = landscape(letter)

    # 1. Background color fill (subtle warm off-white)
    c.setFillColor(colors.HexColor("#FDFBF7"))
    c.rect(0, 0, width, height, fill=1, stroke=0)

    # 2. Outer decorative border (Navy & Gold accent)
    navy_color = colors.HexColor("#1A365D")
    gold_color = colors.HexColor("#D69E2E")
    gold_light = colors.HexColor("#ECC94B")

    # Outer border
    c.setStrokeColor(navy_color)
    c.setLineWidth(4)
    c.rect(20, 20, width - 40, height - 40)

    # Inner gold border
    c.setStrokeColor(gold_color)
    c.setLineWidth(1.5)
    c.rect(28, 28, width - 56, height - 56)

    # Corner decorative accents
    corner_size = 15
    for x, y in [
        (20, 20),
        (width - 20 - corner_size, 20),
        (20, height - 20 - corner_size),
        (width - 20 - corner_size, height - 20 - corner_size),
    ]:
        c.setFillColor(gold_color)
        c.rect(x, y, corner_size, corner_size, fill=1, stroke=0)

    # 3. Header Banner / Ribbon
    c.setFillColor(navy_color)
    c.rect(40, height - 110, width - 80, 50, fill=1, stroke=0)

    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(width / 2.0, height - 90, "CERTIFICATE OF COMPLETION")

    # Subtitle
    c.setFillColor(colors.HexColor("#4A5568"))
    c.setFont("Helvetica-Oblique", 14)
    c.drawCentredString(width / 2.0, height - 145, "PROUDLY PRESENTED TO")

    # Recipient Name (Bold, Large, Dark Blue)
    c.setFillColor(navy_color)
    c.setFont("Helvetica-Bold", 30)
    c.drawCentredString(width / 2.0, height - 200, recipient_name.upper())

    # Decorative Line under name
    c.setStrokeColor(gold_color)
    c.setLineWidth(2)
    c.line(width / 2.0 - 150, height - 215, width / 2.0 + 150, height - 215)

    # Fulfillment statement
    c.setFillColor(colors.HexColor("#2D3748"))
    c.setFont("Helvetica", 14)
    c.drawCentredString(
        width / 2.0, height - 255, "FOR SUCCESSFULLY COMPLETING THE REQUIREMENTS OF"
    )

    # Event Name
    c.setFillColor(colors.HexColor("#2B6CB0"))
    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(width / 2.0, height - 300, event_name)

    # Date
    c.setFillColor(colors.HexColor("#4A5568"))
    c.setFont("Helvetica", 13)
    c.drawCentredString(width / 2.0, height - 340, f"Issued on: {certificate_date}")

    # Divider line
    c.setStrokeColor(colors.HexColor("#E2E8F0"))
    c.setLineWidth(1)
    c.line(100, 150, width - 100, 150)

    # Signatures & Verification section
    # Left: Authorized Signature line
    c.setStrokeColor(colors.HexColor("#718096"))
    c.setLineWidth(1)
    c.line(120, 95, 300, 95)
    c.setFillColor(colors.HexColor("#4A5568"))
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(210, 80, "AUTHORIZED SIGNATURE")

    # Right: Certificate ID & Seal
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(navy_color)
    c.drawCentredString(width - 210, 95, f"CERTIFICATE ID")
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(colors.HexColor("#D69E2E"))
    c.drawCentredString(width - 210, 80, certificate_id)

    # Save PDF
    c.showPage()
    c.save()
    return output_path
