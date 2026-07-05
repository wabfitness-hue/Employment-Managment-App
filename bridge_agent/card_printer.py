"""
Card printer interface.

Supports:
  - Zebra (ZXP3, ZXP7, ZC series) via ZPL over TCP/IP or USB
  - Fargo / HID FARGO (HDP5000, DTC series) via OS print queue
  - Evolis (Primacy, Zenius, Badgy) via OS print queue
  - Magicard via OS print queue
  - Generic: any printer accessible via the OS print queue (PDF → OS print)

The print method receives PDF bytes (the output of the card generator).
For Zebra printers, we convert PDF → ZPL using a raster approach.
For all others, we send the PDF to the OS print queue via subprocess.
"""
import io
import logging
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class CardPrinter:
    """
    Abstract card printer.  Use PrinterFactory.create() to get an instance.
    """

    def __init__(self, name: Optional[str] = None):
        self.name = name

    def print_card(self, pdf_bytes: bytes, copies: int = 1) -> None:
        raise NotImplementedError

    def status(self) -> dict:
        return {"available": False, "name": self.name, "type": "base"}


class OSPrintQueuePrinter(CardPrinter):
    """
    Sends a PDF to the OS print queue.
    Works on Windows (via SumatraPDF or mspaint fallback) and macOS/Linux (lp).
    """

    def __init__(self, name: Optional[str] = None):
        super().__init__(name)
        self._available = self._detect()

    def _detect(self) -> bool:
        if sys.platform == "win32":
            return True   # Windows always has a print queue
        try:
            subprocess.run(["lpstat", "-p"], capture_output=True, timeout=3)
            return True
        except Exception:
            return False

    def status(self) -> dict:
        return {
            "available": self._available,
            "name": self.name or "(default)",
            "type": "os_queue",
        }

    def print_card(self, pdf_bytes: bytes, copies: int = 1) -> None:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(pdf_bytes)
            tmp_path = f.name

        try:
            if sys.platform == "win32":
                _win_print(tmp_path, self.name, copies)
            else:
                _unix_print(tmp_path, self.name, copies)
        finally:
            Path(tmp_path).unlink(missing_ok=True)


class ZebraPrinter(CardPrinter):
    """
    Sends PDF (converted to ZPL) to a Zebra card printer over TCP/IP.
    ZPL conversion uses a raster approach: PDF → PNG → ZPL ^GF command.
    """

    def __init__(self, host: str, port: int = 9100, name: Optional[str] = None):
        super().__init__(name or f"Zebra @ {host}:{port}")
        self.host = host
        self.port = port

    def status(self) -> dict:
        available = self._ping()
        return {
            "available": available,
            "name": self.name,
            "type": "zebra_zpl",
            "host": self.host,
            "port": self.port,
        }

    def print_card(self, pdf_bytes: bytes, copies: int = 1) -> None:
        zpl = _pdf_to_zpl(pdf_bytes, copies=copies)
        self._send_zpl(zpl)

    def _ping(self) -> bool:
        import socket
        try:
            s = socket.create_connection((self.host, self.port), timeout=2)
            s.close()
            return True
        except OSError:
            return False

    def _send_zpl(self, zpl: bytes) -> None:
        import socket
        with socket.create_connection((self.host, self.port), timeout=10) as s:
            s.sendall(zpl)
        logger.info("ZPL sent to %s:%s (%d bytes)", self.host, self.port, len(zpl))


class MockPrinter(CardPrinter):
    """Stub printer for testing — records calls without real hardware."""

    def __init__(self):
        super().__init__("Mock Printer (test)")
        self.printed: list[bytes] = []

    def status(self) -> dict:
        return {"available": True, "name": self.name, "type": "mock"}

    def print_card(self, pdf_bytes: bytes, copies: int = 1) -> None:
        self.printed.append(pdf_bytes)
        logger.info("MockPrinter: received %d bytes (%d copies)", len(pdf_bytes), copies)


# ── Factory ───────────────────────────────────────────────────────────────────

class PrinterFactory:
    @staticmethod
    def create(printer_type: str = "auto", printer_name: str = "") -> CardPrinter:
        """
        Returns the best available printer.

        printer_type values:
          auto     — detect: prefer Zebra if env has ZEBRA_HOST, else OS queue
          zebra    — Zebra ZPL via TCP (needs ZEBRA_HOST env var)
          os       — OS print queue
          mock     — test stub
        """
        import os
        if printer_type == "mock":
            return MockPrinter()

        if printer_type in ("zebra", "auto"):
            host = os.getenv("ZEBRA_HOST", "")
            if host:
                port = int(os.getenv("ZEBRA_PORT", "9100"))
                return ZebraPrinter(host=host, port=port, name=printer_name or None)
            if printer_type == "zebra":
                raise ValueError("ZEBRA_HOST environment variable not set.")

        return OSPrintQueuePrinter(name=printer_name or None)


# ── PDF → ZPL conversion ──────────────────────────────────────────────────────

def _pdf_to_zpl(pdf_bytes: bytes, dpi: int = 300, copies: int = 1) -> bytes:
    """
    Convert a single-page PDF to a ZPL label.
    Uses PyMuPDF (fitz) for rasterisation, then encodes as ZPL ^GF (graphic field).
    Falls back to a minimal ZPL placeholder if PyMuPDF is not available.
    """
    try:
        import fitz
    except ImportError:
        logger.warning("PyMuPDF not installed — sending minimal ZPL placeholder.")
        return _minimal_zpl(copies)

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[0]
    scale = dpi / 72
    mat = fitz.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=mat, alpha=False, colorspace=fitz.csGRAY)
    doc.close()

    width, height = pix.width, pix.height
    raw = pix.samples   # bytes: one byte per pixel, 0=black 255=white

    # Convert to 1bpp packed bytes for ZPL ^GF
    packed, bytes_per_row = _pack_1bpp(raw, width, height)

    total_bytes = len(packed)
    zpl_parts = [f"^XA^FO0,0^GFA,{total_bytes},{total_bytes},{bytes_per_row},"]
    # ZPL wants hex-encoded bytes
    zpl_parts.append(packed.hex().upper())
    zpl_parts.append("^FS")
    zpl_parts.append(f"^PQ{copies}")
    zpl_parts.append("^XZ")
    return "".join(zpl_parts).encode("ascii")


def _pack_1bpp(raw: bytes, width: int, height: int) -> tuple[bytes, int]:
    """Pack 8-bit grayscale pixels into 1bpp (threshold at 128)."""
    import struct
    bytes_per_row = (width + 7) // 8
    result = bytearray()
    for y in range(height):
        row_byte = 0
        bit = 7
        col_out = 0
        for x in range(width):
            pixel = raw[y * width + x]
            if pixel < 128:   # dark → ink
                row_byte |= (1 << bit)
            bit -= 1
            if bit < 0:
                result.append(row_byte)
                row_byte = 0
                bit = 7
                col_out += 1
        if bit < 7:
            result.append(row_byte)
    return bytes(result), bytes_per_row


def _minimal_zpl(copies: int) -> bytes:
    return f"^XA^FO50,50^A0N,40,40^FDID CARD^FS^PQ{copies}^XZ".encode()


# ── OS print helpers ──────────────────────────────────────────────────────────

def _win_print(pdf_path: str, printer_name: Optional[str], copies: int) -> None:
    """
    Print a PDF on Windows.
    Tries SumatraPDF (common, free) then falls back to ShellExecute print verb.
    """
    import shutil
    sumatra = shutil.which("SumatraPDF") or shutil.which("sumatrapdf")
    if sumatra:
        args = [sumatra, "-print-to", printer_name or "-", "-print-settings",
                f"{copies}x", pdf_path]
        subprocess.run(args, check=True, timeout=30)
    else:
        # ShellExecute "print" verb — opens default association
        import os
        os.startfile(pdf_path, "print")


def _unix_print(pdf_path: str, printer_name: Optional[str], copies: int) -> None:
    args = ["lp", "-n", str(copies)]
    if printer_name:
        args += ["-d", printer_name]
    args.append(pdf_path)
    subprocess.run(args, check=True, timeout=30)
