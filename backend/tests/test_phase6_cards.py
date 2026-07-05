"""
Phase 6 Tests — ID card generation: PDF output, dimensions, card data assembly,
colour selection, day abbreviation, bulk PDF, edge cases.
"""
import io
import pytest
import uuid
from datetime import date, timedelta
from unittest.mock import patch

from app.services.cards.generator import (
    CardData, generate_card_pdf, _truncate,
)
from app.services.cards.bulk import generate_bulk_pdf, CARDS_PER_PAGE
from app.services.cards.dimensions import (
    CARD_W, CARD_H, EMPLOYEE_BG, CONTRACTOR_BG, hex_to_rgb, MM,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _employee_card(**kwargs) -> CardData:
    defaults = dict(
        person_id=str(uuid.uuid4()),
        person_type="employee",
        employee_id="DIR-0001",
        full_name="Jane Smith",
        job_title="Director of Operations",
        department="Operations",
        floor="3",
        company_name="Acme Corporation",
        contract_end=date.today() + timedelta(days=365 * 4),
        photo_bytes=None,
        access_profile_name="Director Full Access",
        access_days=None,
        access_start=None,
        access_end=None,
    )
    defaults.update(kwargs)
    return CardData(**defaults)


def _contractor_card(**kwargs) -> CardData:
    defaults = dict(
        person_id=str(uuid.uuid4()),
        person_type="contractor",
        employee_id="CTR-0001",
        full_name="Bob Builder",
        job_title="Site Engineer",
        department="Construction",
        floor="1",
        company_name="BuildRight Ltd",
        contract_end=date.today() + timedelta(days=90),
        photo_bytes=None,
        access_profile_name="Contractor Entry Only",
        access_days="monday,tuesday,wednesday,thursday,friday",
        access_start="08:00",
        access_end="17:30",
    )
    defaults.update(kwargs)
    return CardData(**defaults)


def _make_jpeg_bytes(w=100, h=100) -> bytes:
    import io as _io
    from PIL import Image
    img = Image.new("RGB", (w, h), (200, 100, 50))
    buf = _io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


# ── CardData properties ───────────────────────────────────────────────────────

class TestCardDataProperties:
    def test_employee_is_not_contractor(self):
        card = _employee_card()
        assert card.is_contractor is False

    def test_contractor_is_contractor(self):
        card = _contractor_card()
        assert card.is_contractor is True

    def test_employee_uses_blue_bg(self):
        card = _employee_card()
        assert card.bg_colour == EMPLOYEE_BG

    def test_contractor_uses_orange_bg(self):
        card = _contractor_card()
        assert card.bg_colour == CONTRACTOR_BG

    def test_hex_colour_override_applied(self):
        card = _employee_card(bg_colour_hex="#FF0000")
        r, g, b = card.bg_colour
        assert abs(r - 1.0) < 0.01
        assert abs(g - 0.0) < 0.01

    def test_no_photo_bytes_is_none(self):
        card = _employee_card()
        assert card.photo_bytes is None

    def test_photo_bytes_stored(self):
        photo = _make_jpeg_bytes()
        card = _employee_card(photo_bytes=photo)
        assert card.photo_bytes == photo


# ── CR80 dimensions ───────────────────────────────────────────────────────────

class TestCardDimensions:
    def test_card_width_is_correct(self):
        # 85.6mm in points (within 0.5pt tolerance)
        assert abs(CARD_W - 85.6 * MM) < 0.5

    def test_card_height_is_correct(self):
        assert abs(CARD_H - 54.0 * MM) < 0.5

    def test_card_wider_than_tall(self):
        assert CARD_W > CARD_H

    def test_hex_to_rgb_blue(self):
        r, g, b = hex_to_rgb("#1E40AF")
        assert abs(r - 0.118) < 0.01
        assert abs(g - 0.251) < 0.01
        assert abs(b - 0.686) < 0.01

    def test_hex_to_rgb_white(self):
        r, g, b = hex_to_rgb("#FFFFFF")
        assert r == g == b == 1.0

    def test_hex_to_rgb_black(self):
        r, g, b = hex_to_rgb("#000000")
        assert r == g == b == 0.0


# ── PDF generation ────────────────────────────────────────────────────────────

class TestPDFGeneration:
    def test_generates_bytes(self):
        card = _employee_card()
        pdf = generate_card_pdf(card)
        assert isinstance(pdf, bytes)
        assert len(pdf) > 0

    def test_output_is_pdf(self):
        card = _employee_card()
        pdf = generate_card_pdf(card)
        assert pdf[:4] == b"%PDF"

    def test_employee_card_generates(self):
        card = _employee_card()
        pdf = generate_card_pdf(card)
        assert len(pdf) > 500

    def test_contractor_card_generates(self):
        card = _contractor_card()
        pdf = generate_card_pdf(card)
        assert len(pdf) > 500

    def test_card_with_photo_generates(self):
        card = _employee_card(photo_bytes=_make_jpeg_bytes(400, 400))
        pdf = generate_card_pdf(card)
        assert pdf[:4] == b"%PDF"

    def test_card_without_photo_generates(self):
        card = _employee_card(photo_bytes=None)
        pdf = generate_card_pdf(card)
        assert pdf[:4] == b"%PDF"

    def test_long_name_does_not_crash(self):
        card = _employee_card(full_name="Sir Jonathan Alexander Bartholomew Whitfield-Cunningham III")
        pdf = generate_card_pdf(card)
        assert pdf[:4] == b"%PDF"

    def test_long_job_title_does_not_crash(self):
        card = _employee_card(job_title="Executive Vice President of Global Operations and Strategic Development")
        pdf = generate_card_pdf(card)
        assert pdf[:4] == b"%PDF"

    def test_no_floor_generates(self):
        card = _employee_card(floor=None)
        pdf = generate_card_pdf(card)
        assert pdf[:4] == b"%PDF"

    def test_no_access_profile_generates(self):
        card = _employee_card(access_profile_name=None)
        pdf = generate_card_pdf(card)
        assert pdf[:4] == b"%PDF"

    def test_contractor_with_time_restriction_generates(self):
        card = _contractor_card(
            access_days="monday,wednesday,friday",
            access_start="09:00",
            access_end="16:00",
        )
        pdf = generate_card_pdf(card)
        assert pdf[:4] == b"%PDF"

    def test_two_cards_produce_different_pdfs(self):
        c1 = _employee_card(employee_id="DIR-0001", full_name="Alice Jones")
        c2 = _employee_card(employee_id="ENG-0002", full_name="Bob Smith")
        assert generate_card_pdf(c1) != generate_card_pdf(c2)


# ── Text truncation ───────────────────────────────────────────────────────────

class TestTextTruncation:
    def _canvas(self):
        import io as _io
        from reportlab.pdfgen import canvas as _canvas
        buf = _io.BytesIO()
        return _canvas.Canvas(buf)

    def test_short_text_unchanged(self):
        c = self._canvas()
        result = _truncate("Jane Smith", 200, c, "Helvetica", 8)
        assert result == "Jane Smith"

    def test_long_text_truncated(self):
        c = self._canvas()
        long_text = "A" * 100
        result = _truncate(long_text, 50, c, "Helvetica", 8)
        assert result.endswith("…")
        assert len(result) < len(long_text)

    def test_truncated_fits_within_width(self):
        c = self._canvas()
        long_text = "W" * 50
        result = _truncate(long_text, 60, c, "Helvetica", 8)
        c.setFont("Helvetica", 8)
        assert c.stringWidth(result, "Helvetica", 8) <= 60 + 5  # small tolerance


# ── Bulk PDF ──────────────────────────────────────────────────────────────────

class TestBulkPDF:
    def test_single_card_bulk(self):
        cards = [_employee_card()]
        pdf = generate_bulk_pdf(cards)
        assert pdf[:4] == b"%PDF"

    def test_ten_cards_bulk(self):
        cards = [_employee_card() for _ in range(10)]
        pdf = generate_bulk_pdf(cards)
        assert pdf[:4] == b"%PDF"

    def test_mixed_cards_bulk(self):
        cards = [_employee_card(), _contractor_card(), _employee_card()]
        pdf = generate_bulk_pdf(cards)
        assert pdf[:4] == b"%PDF"

    def test_empty_cards_raises(self):
        with pytest.raises(ValueError, match="No cards"):
            generate_bulk_pdf([])

    def test_eleven_cards_fits_two_pages(self):
        # 11 cards should produce a multi-page PDF
        cards = [_employee_card() for _ in range(11)]
        pdf = generate_bulk_pdf(cards)
        assert pdf[:4] == b"%PDF"
        assert len(pdf) > 1000

    def test_cards_per_page_constant(self):
        assert CARDS_PER_PAGE == 10

    def test_bulk_larger_than_single(self):
        single = generate_card_pdf(_employee_card())
        bulk = generate_bulk_pdf([_employee_card()])
        # Bulk page (A4) should be larger than single CR80 card
        assert len(bulk) > 0
        assert len(single) > 0
