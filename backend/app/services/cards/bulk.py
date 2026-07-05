"""
Bulk card PDF — lays out multiple CR80 cards on A4 pages for sheet printing.
Layout: 2 columns × 5 rows = 10 cards per A4 page with 10mm margins and gaps.

Each card is printed at exactly CR80 dimensions.
HR prints the sheet and cuts along the card borders.
"""
import io
from typing import List

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

from .dimensions import CARD_W, CARD_H, MM
from .generator import CardData, generate_card_pdf


# A4: 210mm × 297mm = 595.3pt × 841.9pt
A4_W, A4_H = A4

PAGE_MARGIN = 10 * MM   # 10mm border around sheet
CARD_GAP = 5 * MM       # 5mm gap between cards

COLS = 2
ROWS = 5
CARDS_PER_PAGE = COLS * ROWS


def generate_bulk_pdf(cards: List[CardData]) -> bytes:
    """
    Render all cards onto A4 pages, 10 per page.
    Returns a single PDF containing all pages.
    """
    if not cards:
        raise ValueError("No cards to generate.")

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle(f"ID Cards — Bulk Print ({len(cards)} cards)")

    for page_start in range(0, len(cards), CARDS_PER_PAGE):
        page_cards = cards[page_start : page_start + CARDS_PER_PAGE]
        _draw_page(c, page_cards)
        c.showPage()

    c.save()
    buf.seek(0)
    return buf.read()


def _draw_page(c: canvas.Canvas, cards: List[CardData]) -> None:
    """Draws up to 10 cards on one A4 page with cut guide lines."""
    _draw_cut_guides(c, len(cards))

    for idx, card in enumerate(cards):
        col = idx % COLS
        row = idx // COLS

        x = PAGE_MARGIN + col * (CARD_W + CARD_GAP)
        # ReportLab y=0 is bottom — place top row near top of page
        y = A4_H - PAGE_MARGIN - (row + 1) * CARD_H - row * CARD_GAP

        # Render this card into its own mini-PDF, then embed as a form XObject
        card_pdf_bytes = generate_card_pdf(card)
        _embed_card(c, card_pdf_bytes, x, y)


def _embed_card(c: canvas.Canvas, card_pdf_bytes: bytes, x: float, y: float) -> None:
    """
    Embeds a single card PDF at position (x, y) on the current canvas.
    Uses ReportLab's drawImage via a rendered raster of the card.
    """
    # Re-render card as a high-res image and embed it
    from PIL import Image
    import io as _io

    try:
        from reportlab.lib.utils import ImageReader
        import fitz  # PyMuPDF — renders PDF page to image

        doc = fitz.open(stream=card_pdf_bytes, filetype="pdf")
        page = doc[0]
        # 300 DPI scale factor: 300/72 ≈ 4.17
        mat = fitz.Matrix(4.17, 4.17)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img_bytes = pix.tobytes("jpeg")
        doc.close()

        reader = ImageReader(_io.BytesIO(img_bytes))
        c.drawImage(reader, x, y, width=CARD_W, height=CARD_H)

    except ImportError:
        # PyMuPDF not available — draw a placeholder rectangle with label
        c.setFillColorRGB(0.9, 0.9, 0.9)
        c.rect(x, y, CARD_W, CARD_H, fill=1, stroke=1)
        c.setFillColorRGB(0, 0, 0)
        c.setFont("Helvetica", 6)
        c.drawCentredString(x + CARD_W / 2, y + CARD_H / 2, "Card preview requires PyMuPDF")


def _draw_cut_guides(c: canvas.Canvas, card_count: int) -> None:
    """Draws dashed cut lines around each card position."""
    c.setStrokeColorRGB(0.7, 0.7, 0.7)
    c.setLineWidth(0.3)
    c.setDash(2, 3)

    filled = min(card_count, CARDS_PER_PAGE)
    for idx in range(filled):
        col = idx % COLS
        row = idx // COLS
        x = PAGE_MARGIN + col * (CARD_W + CARD_GAP)
        y = A4_H - PAGE_MARGIN - (row + 1) * CARD_H - row * CARD_GAP
        c.rect(x, y, CARD_W, CARD_H, fill=0, stroke=1)

    c.setDash()
