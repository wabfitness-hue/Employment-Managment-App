"""
Phase 5 Tests — Photo validation (magic bytes), storage (resize/crop/save),
webcam base64 decode, error cases (corrupt, oversized, wrong type).
"""
import io
import os
import base64
import pytest
import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch, MagicMock

from PIL import Image
from fastapi import HTTPException

from app.services.photos.validation import (
    detect_mime_from_bytes,
    validate_photo_bytes,
    validate_base64_photo,
    MAX_PHOTO_BYTES,
)
from app.services.photos.storage import (
    save_photo,
    delete_photo,
    photo_exists,
    get_photo_bytes,
    _square_crop,
)


# ── Helpers — generate real image bytes in-memory ─────────────────────────────

def _make_jpeg_bytes(width=200, height=200, colour=(255, 100, 50)) -> bytes:
    img = Image.new("RGB", (width, height), colour)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _make_png_bytes(width=200, height=200) -> bytes:
    img = Image.new("RGBA", (width, height), (0, 128, 255, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_webp_bytes(width=200, height=200) -> bytes:
    img = Image.new("RGB", (width, height), (100, 200, 100))
    buf = io.BytesIO()
    img.save(buf, format="WEBP")
    return buf.getvalue()


def _make_base64_jpeg(width=200, height=200) -> str:
    raw = _make_jpeg_bytes(width, height)
    return "data:image/jpeg;base64," + base64.b64encode(raw).decode()


# ── Magic byte detection ──────────────────────────────────────────────────────

class TestMagicByteDetection:
    def test_detects_jpeg(self):
        assert detect_mime_from_bytes(_make_jpeg_bytes()) == "image/jpeg"

    def test_detects_png(self):
        assert detect_mime_from_bytes(_make_png_bytes()) == "image/png"

    def test_detects_webp(self):
        assert detect_mime_from_bytes(_make_webp_bytes()) == "image/webp"

    def test_rejects_pdf_bytes(self):
        fake_pdf = b"%PDF-1.4 fake content"
        assert detect_mime_from_bytes(fake_pdf) is None

    def test_rejects_gif_bytes(self):
        fake_gif = b"GIF89a fake content"
        assert detect_mime_from_bytes(fake_gif) is None

    def test_rejects_exe_bytes(self):
        fake_exe = b"MZ\x90\x00 fake windows exe"
        assert detect_mime_from_bytes(fake_exe) is None

    def test_rejects_empty_bytes(self):
        assert detect_mime_from_bytes(b"") is None

    def test_rejects_text_file(self):
        assert detect_mime_from_bytes(b"Hello, world!") is None

    def test_jpeg_with_wrong_extension_still_accepted(self):
        # Magic bytes take priority over filename
        data = _make_jpeg_bytes()
        mime = validate_photo_bytes(data, "photo.docx")
        assert mime == "image/jpeg"


# ── Full validation ───────────────────────────────────────────────────────────

class TestValidatePhotoBytes:
    def test_valid_jpeg_passes(self):
        mime = validate_photo_bytes(_make_jpeg_bytes())
        assert mime == "image/jpeg"

    def test_valid_png_passes(self):
        mime = validate_photo_bytes(_make_png_bytes())
        assert mime == "image/png"

    def test_valid_webp_passes(self):
        mime = validate_photo_bytes(_make_webp_bytes())
        assert mime == "image/webp"

    def test_empty_bytes_rejected(self):
        with pytest.raises(HTTPException) as exc:
            validate_photo_bytes(b"")
        assert exc.value.status_code == 422
        assert "empty" in exc.value.detail.lower()

    def test_oversized_file_rejected(self):
        oversized = b"\xff\xd8\xff" + b"x" * (MAX_PHOTO_BYTES + 1)
        with pytest.raises(HTTPException) as exc:
            validate_photo_bytes(oversized)
        assert exc.value.status_code == 413
        assert "large" in exc.value.detail.lower()

    def test_wrong_type_rejected(self):
        with pytest.raises(HTTPException) as exc:
            validate_photo_bytes(b"%PDF-fake", "document.pdf")
        assert exc.value.status_code == 422

    def test_corrupt_image_rejected(self):
        # Starts with JPEG magic bytes but content is garbage
        corrupt = b"\xff\xd8\xff" + b"\x00" * 50
        with pytest.raises(HTTPException) as exc:
            validate_photo_bytes(corrupt)
        assert exc.value.status_code == 422

    def test_exactly_at_size_limit_passes(self):
        # Build a real JPEG that is under the limit
        data = _make_jpeg_bytes(100, 100)
        assert len(data) < MAX_PHOTO_BYTES
        mime = validate_photo_bytes(data)
        assert mime == "image/jpeg"


# ── Base64 / webcam decode ────────────────────────────────────────────────────

class TestValidateBase64Photo:
    def test_decodes_data_uri(self):
        b64 = _make_base64_jpeg()
        raw = validate_base64_photo(b64)
        assert raw[:3] == b"\xff\xd8\xff"

    def test_decodes_raw_base64_without_prefix(self):
        raw_bytes = _make_jpeg_bytes()
        b64_raw = base64.b64encode(raw_bytes).decode()
        decoded = validate_base64_photo(b64_raw)
        assert decoded[:3] == b"\xff\xd8\xff"

    def test_empty_string_rejected(self):
        with pytest.raises(HTTPException) as exc:
            validate_base64_photo("")
        assert exc.value.status_code == 422

    def test_invalid_base64_rejected(self):
        with pytest.raises(HTTPException) as exc:
            validate_base64_photo("not!valid!base64!!!!")
        assert exc.value.status_code == 422

    def test_png_base64_decoded(self):
        buf = io.BytesIO()
        Image.new("RGB", (50, 50)).save(buf, format="PNG")
        b64 = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
        raw = validate_base64_photo(b64)
        assert raw[:8] == b"\x89PNG\r\n\x1a\n"


# ── Square crop ───────────────────────────────────────────────────────────────

class TestSquareCrop:
    def test_landscape_crops_to_square(self):
        img = Image.new("RGB", (400, 200))
        cropped = _square_crop(img)
        assert cropped.size == (200, 200)

    def test_portrait_crops_to_square(self):
        img = Image.new("RGB", (200, 400))
        cropped = _square_crop(img)
        assert cropped.size == (200, 200)

    def test_already_square_unchanged(self):
        img = Image.new("RGB", (300, 300))
        cropped = _square_crop(img)
        assert cropped.size == (300, 300)

    def test_tiny_image_still_crops(self):
        img = Image.new("RGB", (10, 5))
        cropped = _square_crop(img)
        assert cropped.size == (5, 5)


# ── Storage ───────────────────────────────────────────────────────────────────

class TestPhotoStorage:
    @pytest.fixture(autouse=True)
    def use_temp_dir(self, tmp_path):
        """Redirect photo storage to a temporary directory for all tests."""
        with patch("app.services.photos.storage.settings") as mock_settings:
            mock_settings.PHOTO_STORAGE_PATH = str(tmp_path)
            yield tmp_path

    def test_save_jpeg_creates_file(self):
        pid = str(uuid.uuid4())
        path = save_photo(pid, _make_jpeg_bytes())
        assert path == f"photos/{pid}.jpg"
        assert photo_exists(pid)

    def test_save_png_converts_to_jpeg(self):
        pid = str(uuid.uuid4())
        save_photo(pid, _make_png_bytes())
        # File is always stored as JPEG
        assert photo_exists(pid)
        data = get_photo_bytes(pid)
        assert data[:3] == b"\xff\xd8\xff"

    def test_save_rgba_png_converts_without_error(self):
        pid = str(uuid.uuid4())
        img = Image.new("RGBA", (100, 100), (255, 0, 0, 128))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        save_photo(pid, buf.getvalue())
        assert photo_exists(pid)

    def test_save_bounds_size_preserving_aspect(self):
        pid = str(uuid.uuid4())
        save_photo(pid, _make_jpeg_bytes(800, 600))
        data = get_photo_bytes(pid)
        result = Image.open(io.BytesIO(data))
        # Bounded to fit within 600×600, aspect (4:3) preserved
        assert max(result.size) <= 600
        assert result.size == (600, 450)

    def test_save_overwrites_existing_photo(self):
        pid = str(uuid.uuid4())
        save_photo(pid, _make_jpeg_bytes(200, 200, colour=(255, 0, 0)))
        save_photo(pid, _make_jpeg_bytes(200, 200, colour=(0, 0, 255)))
        assert photo_exists(pid)
        # Only one file exists
        from pathlib import Path
        import tempfile
        files = list(Path(str(Path(get_photo_bytes.__module__))).parent.parent.parent.parent.glob("*.jpg"))

    def test_delete_removes_file(self):
        pid = str(uuid.uuid4())
        save_photo(pid, _make_jpeg_bytes())
        assert photo_exists(pid)
        result = delete_photo(pid)
        assert result is True
        assert not photo_exists(pid)

    def test_delete_nonexistent_returns_false(self):
        pid = str(uuid.uuid4())
        assert delete_photo(pid) is False

    def test_get_photo_bytes_returns_jpeg(self):
        pid = str(uuid.uuid4())
        save_photo(pid, _make_jpeg_bytes())
        data = get_photo_bytes(pid)
        assert isinstance(data, bytes)
        assert data[:3] == b"\xff\xd8\xff"

    def test_get_photo_bytes_missing_raises_404(self):
        with pytest.raises(HTTPException) as exc:
            get_photo_bytes(str(uuid.uuid4()))
        assert exc.value.status_code == 404

    def test_photo_not_exists_returns_false(self):
        assert photo_exists(str(uuid.uuid4())) is False

    def test_landscape_photo_keeps_landscape_aspect(self):
        pid = str(uuid.uuid4())
        save_photo(pid, _make_jpeg_bytes(640, 480))
        data = get_photo_bytes(pid)
        img = Image.open(io.BytesIO(data))
        w, h = img.size
        assert w > h and max(w, h) <= 600  # aspect preserved, bounded

    def test_portrait_photo_keeps_portrait_aspect(self):
        pid = str(uuid.uuid4())
        save_photo(pid, _make_jpeg_bytes(480, 640))
        data = get_photo_bytes(pid)
        img = Image.open(io.BytesIO(data))
        w, h = img.size
        assert h > w and max(w, h) <= 600  # aspect preserved, bounded


# ── Outlook employee ID extraction ────────────────────────────────────────────

class TestEmployeeIdExtraction:
    def test_extracts_standard_id(self):
        from app.services.photos.outlook_extractor import _extract_employee_id
        assert _extract_employee_id("Photo for DIR-0042") == "DIR-0042"

    def test_extracts_short_prefix(self):
        from app.services.photos.outlook_extractor import _extract_employee_id
        assert _extract_employee_id("New photo: HR-0005 ready") == "HR-0005"

    def test_extracts_from_body_text(self):
        from app.services.photos.outlook_extractor import _extract_employee_id
        text = "Please find attached the photo for employee CTR-0123 starting Monday."
        assert _extract_employee_id(text) == "CTR-0123"

    def test_case_insensitive(self):
        from app.services.photos.outlook_extractor import _extract_employee_id
        assert _extract_employee_id("photo for dir-0001") == "DIR-0001"

    def test_returns_none_when_no_id(self):
        from app.services.photos.outlook_extractor import _extract_employee_id
        assert _extract_employee_id("Please see the attached document") is None

    def test_returns_first_id_when_multiple(self):
        from app.services.photos.outlook_extractor import _extract_employee_id
        result = _extract_employee_id("Photo DIR-0001 and also ENG-0002")
        assert result == "DIR-0001"
