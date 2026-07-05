"""
ID card PDF generator — produces a single CR80-sized card per call.
Uses ReportLab (pure Python, no system dependencies).

Card layout:
┌─────────────────────────────────────────┐
│  [HEADER — company name + type badge]   │
│──────────────────────────────────────── │
│ [PHOTO]  Full Name                      │
│          Employee ID                    │
│          Job Title                      │
│          Department | Floor             │
│──────────────────────────────────────── │
│  ACCESS: profile name     Valid: date   │
└─────────────────────────────────────────┘
"""
import io
from datetime import date
from typing import Optional

from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image

from .dimensions import (
    CARD_W, CARD_H, MARGIN, MM,
    PHOTO_X, PHOTO_Y, PHOTO_W, PHOTO_H,
    HEADER_H, TEXT_X, TEXT_W, FOOTER_H, FOOTER_Y,
    EMPLOYEE_BG, EMPLOYEE_HEADER, EMPLOYEE_TEXT,
    CONTRACTOR_BG, CONTRACTOR_HEADER, CONTRACTOR_TEXT,
    DARK_TEXT, WHITE, ACCENT_GOLD,
    hex_to_rgb,
)


# ReportLab built-in font families — no embedding needed
FONT_MAP = {
    "helvetica": ("Helvetica", "Helvetica-Bold"),
    "times": ("Times-Roman", "Times-Bold"),
    "courier": ("Courier", "Courier-Bold"),
}


# ── Data class ────────────────────────────────────────────────────────────────

class CardData:
    """Everything needed to draw one ID card."""
    def __init__(
        self,
        person_id: str,
        person_type: str,           # "employee" or "contractor"
        employee_id: str,
        full_name: str,
        job_title: str,
        department: str,
        floor: Optional[str],
        company_name: str,
        contract_end: date,
        photo_bytes: Optional[bytes] = None,
        access_profile_name: Optional[str] = None,
        access_days: Optional[str] = None,      # e.g. "Mon–Fri"
        access_start: Optional[str] = None,     # e.g. "08:00"
        access_end: Optional[str] = None,       # e.g. "17:30"
        bg_colour_hex: Optional[str] = None,    # override from card design settings
        nfc_uid: Optional[str] = None,
        text_colour_hex: Optional[str] = None,
        accent_colour_hex: Optional[str] = None,
        band_colour_hex: Optional[str] = None,  # top/bottom strips; None = auto-darken
        company_colour_hex: Optional[str] = None,  # company name text; None = text colour
        font: str = "helvetica",                # helvetica | times | courier
    ):
        self.person_id = person_id
        self.person_type = person_type
        self.employee_id = employee_id
        self.full_name = full_name
        self.job_title = job_title
        self.department = department
        self.floor = floor
        self.company_name = company_name
        self.contract_end = contract_end
        self.photo_bytes = photo_bytes
        self.access_profile_name = access_profile_name
        self.access_days = access_days
        self.access_start = access_start
        self.access_end = access_end
        self.bg_colour_hex = bg_colour_hex
        self.nfc_uid = nfc_uid
        self.text_colour_hex = text_colour_hex
        self.accent_colour_hex = accent_colour_hex
        self.band_colour_hex = band_colour_hex or None
        self.company_colour_hex = company_colour_hex or None
        self.font = font if font in FONT_MAP else "helvetica"

    @property
    def is_contractor(self) -> bool:
        return self.person_type == "contractor"

    @property
    def font_regular(self) -> str:
        return FONT_MAP[self.font][0]

    @property
    def font_bold(self) -> str:
        return FONT_MAP[self.font][1]

    @property
    def accent(self) -> tuple:
        if self.accent_colour_hex:
            return hex_to_rgb(self.accent_colour_hex)
        return ACCENT_GOLD

    @property
    def bg_colour(self) -> tuple:
        if self.bg_colour_hex:
            return hex_to_rgb(self.bg_colour_hex)
        return CONTRACTOR_BG if self.is_contractor else EMPLOYEE_BG

    @property
    def header_colour(self) -> tuple:
        # Top/bottom strips: use the explicit band colour if the designer set one,
        # otherwise a darker shade of the card colour.
        if self.band_colour_hex:
            return hex_to_rgb(self.band_colour_hex)
        if self.bg_colour_hex:
            r, g, b = hex_to_rgb(self.bg_colour_hex)
            return (r * 0.62, g * 0.62, b * 0.62)
        if self.is_contractor:
            return CONTRACTOR_HEADER
        return EMPLOYEE_HEADER

    @property
    def text_colour(self) -> tuple:
        if self.text_colour_hex:
            return hex_to_rgb(self.text_colour_hex)
        return WHITE

    @property
    def company_colour(self) -> tuple:
        # Company name sits on the band — its own colour, falling back to text colour.
        if self.company_colour_hex:
            return hex_to_rgb(self.company_colour_hex)
        return self.text_colour


# ── Core renderer ─────────────────────────────────────────────────────────────

def generate_card_pdf(card: CardData) -> bytes:
    """
    Renders a single ID card and returns the PDF bytes.
    The PDF page is exactly CR80 size (85.6 × 54 mm).
    """
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(CARD_W, CARD_H))
    c.setTitle(f"ID Card — {card.employee_id}")

    _draw_background(c, card)
    _draw_header(c, card)
    _draw_footer(c, card)
    _draw_photo(c, card)
    _draw_text_block(c, card)
    _draw_accent_stripe(c, card)

    c.save()
    buf.seek(0)
    return buf.read()


# ── Drawing helpers ───────────────────────────────────────────────────────────

def _draw_background(c: canvas.Canvas, card: CardData) -> None:
    c.setFillColorRGB(*card.bg_colour)
    c.rect(0, 0, CARD_W, CARD_H, fill=1, stroke=0)


def _draw_header(c: canvas.Canvas, card: CardData) -> None:
    """Top strip: company name left, card type badge right."""
    strip_y = CARD_H - HEADER_H
    c.setFillColorRGB(*card.header_colour)
    c.rect(0, strip_y, CARD_W, HEADER_H, fill=1, stroke=0)

    # Company name
    c.setFillColorRGB(*card.company_colour)
    c.setFont(card.font_bold, 11.0)
    company = card.company_name.upper()
    c.drawString(MARGIN, strip_y + 3.0 * MM, company)

    # Type badge
    badge_label = "CONTRACTOR" if card.is_contractor else "EMPLOYEE"
    badge_w = 26 * MM
    badge_x = CARD_W - badge_w - MARGIN
    c.setFillColorRGB(*card.accent)
    c.roundRect(badge_x, strip_y + 1.2 * MM, badge_w, 6.5 * MM, radius=1 * MM, fill=1, stroke=0)
    c.setFillColorRGB(*DARK_TEXT)
    c.setFont(card.font_bold, 8.0)
    c.drawCentredString(badge_x + badge_w / 2, strip_y + 3.4 * MM, badge_label)


def _draw_footer(c: canvas.Canvas, card: CardData) -> None:
    """Bottom strip — plain colour band. Access and expiry deliberately not
    printed; both live in the person's profile and can change without a reprint."""
    footer_y = FOOTER_Y
    c.setFillColorRGB(*card.header_colour)
    c.rect(0, footer_y, CARD_W, FOOTER_H, fill=1, stroke=0)


def _draw_photo(c: canvas.Canvas, card: CardData) -> None:
    """Photo box — shows placeholder if no photo available."""
    px, py, pw, ph = PHOTO_X, PHOTO_Y, PHOTO_W, PHOTO_H

    if card.photo_bytes:
        try:
            img_buf = io.BytesIO(card.photo_bytes)
            pil_img = Image.open(img_buf)
            pil_img = pil_img.convert("RGB")
            img_out = io.BytesIO()
            pil_img.save(img_out, format="JPEG")
            img_out.seek(0)
            reader = ImageReader(img_out)
            c.drawImage(reader, px, py, width=pw, height=ph, preserveAspectRatio=False)
        except Exception:
            _draw_photo_placeholder(c, px, py, pw, ph)
    else:
        _draw_photo_placeholder(c, px, py, pw, ph)

    # Thin border around photo (matches text colour)
    c.setStrokeColorRGB(*card.text_colour)
    c.setLineWidth(0.5)
    c.rect(px, py, pw, ph, fill=0, stroke=1)


def _draw_photo_placeholder(c: canvas.Canvas, x, y, w, h) -> None:
    c.setFillColorRGB(0.85, 0.85, 0.85)
    c.rect(x, y, w, h, fill=1, stroke=0)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.setFont("Helvetica", 6.0)
    c.drawCentredString(x + w / 2, y + h / 2 - 2.0 * MM, "NO")
    c.drawCentredString(x + w / 2, y + h / 2 + 1.0 * MM, "PHOTO")


def _draw_text_block(c: canvas.Canvas, card: CardData) -> None:
    """Employee details to the right of the photo."""
    c.setFillColorRGB(*card.text_colour)

    y_top = CARD_H - HEADER_H - 4.0 * MM

    # Full name — largest text
    c.setFont(card.font_bold, 11.5)
    name = _truncate(card.full_name, TEXT_W, c, card.font_bold, 11.5)
    c.drawString(TEXT_X, y_top, name)

    # Employee ID
    c.setFont(card.font_bold, 11.0)
    c.setFillColorRGB(*card.accent)
    c.drawString(TEXT_X, y_top - 6.0 * MM, card.employee_id)

    c.setFillColorRGB(*card.text_colour)

    # Job title
    c.setFont(card.font_regular, 9.5)
    title = _truncate(card.job_title, TEXT_W, c, card.font_regular, 9.5)
    c.drawString(TEXT_X, y_top - 11.5 * MM, title)

    # Department + floor
    dept = card.department
    if card.floor:
        dept = f"{dept}  |  Floor {card.floor}"
    dept = _truncate(dept, TEXT_W, c, card.font_regular, 8.5)
    c.setFont(card.font_regular, 8.5)
    c.drawString(TEXT_X, y_top - 16.0 * MM, dept)

    # Contractor company name (shown below department for contractors)
    if card.is_contractor:
        c.setFont(card.font_bold, 8.0)
        c.setFillColorRGB(*card.accent)
        cname = _truncate(card.company_name, TEXT_W, c, card.font_bold, 8.0)
        c.drawString(TEXT_X, y_top - 20.0 * MM, cname)


def _draw_accent_stripe(c: canvas.Canvas, card: CardData) -> None:
    """Thin accent vertical stripe between photo and text — purely decorative."""
    stripe_x = TEXT_X - 1.5 * MM
    stripe_top = CARD_H - HEADER_H - 1 * MM
    stripe_bot = FOOTER_Y + FOOTER_H + 1 * MM
    c.setFillColorRGB(*card.accent)
    c.rect(stripe_x, stripe_bot, 0.4 * MM, stripe_top - stripe_bot, fill=1, stroke=0)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _truncate(text: str, max_width: float, c: canvas.Canvas, font: str, size: float) -> str:
    """Truncate text with ellipsis if it exceeds max_width points."""
    c.setFont(font, size)
    if c.stringWidth(text, font, size) <= max_width:
        return text
    while text and c.stringWidth(text + "…", font, size) > max_width:
        text = text[:-1]
    return text + "…"
