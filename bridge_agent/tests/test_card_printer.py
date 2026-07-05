"""
Tests for the card printer module (using MockPrinter — no hardware needed).
"""
import io
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))

import pytest

from bridge_agent.card_printer import MockPrinter, PrinterFactory, _pack_1bpp


def _minimal_pdf() -> bytes:
    """Return a tiny but valid-looking PDF header."""
    return b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF"


class TestMockPrinter:
    def test_mock_printer_available(self):
        p = MockPrinter()
        assert p.status()["available"] is True

    def test_mock_printer_type(self):
        assert MockPrinter().status()["type"] == "mock"

    def test_mock_records_print_calls(self):
        p = MockPrinter()
        p.print_card(b"%PDF-mock", copies=1)
        assert len(p.printed) == 1
        assert p.printed[0] == b"%PDF-mock"

    def test_mock_multiple_prints(self):
        p = MockPrinter()
        p.print_card(b"%PDF-1", copies=1)
        p.print_card(b"%PDF-2", copies=2)
        assert len(p.printed) == 2

    def test_mock_name(self):
        p = MockPrinter()
        assert "Mock" in p.status()["name"]


class TestPrinterFactory:
    def test_factory_creates_mock(self):
        p = PrinterFactory.create("mock")
        assert isinstance(p, MockPrinter)

    def test_factory_auto_without_zebra_host_creates_os_printer(self):
        import os
        env_backup = os.environ.pop("ZEBRA_HOST", None)
        try:
            from bridge_agent.card_printer import OSPrintQueuePrinter
            p = PrinterFactory.create("auto")
            assert isinstance(p, OSPrintQueuePrinter)
        finally:
            if env_backup is not None:
                os.environ["ZEBRA_HOST"] = env_backup

    def test_factory_zebra_without_host_raises(self):
        import os
        env_backup = os.environ.pop("ZEBRA_HOST", None)
        try:
            with pytest.raises(ValueError, match="ZEBRA_HOST"):
                PrinterFactory.create("zebra")
        finally:
            if env_backup is not None:
                os.environ["ZEBRA_HOST"] = env_backup

    def test_factory_zebra_with_host_creates_zebra_printer(self):
        import os
        from bridge_agent.card_printer import ZebraPrinter
        os.environ["ZEBRA_HOST"] = "192.168.1.100"
        try:
            p = PrinterFactory.create("zebra")
            assert isinstance(p, ZebraPrinter)
            assert p.host == "192.168.1.100"
        finally:
            del os.environ["ZEBRA_HOST"]


class TestBitmapPacking:
    def test_all_white_row(self):
        # 8 white pixels → 1 byte = 0x00 (no ink)
        raw = bytes([255] * 8)
        packed, bpr = _pack_1bpp(raw, width=8, height=1)
        assert bpr == 1
        assert packed == bytes([0x00])

    def test_all_black_row(self):
        # 8 black pixels → 1 byte = 0xFF (all ink)
        raw = bytes([0] * 8)
        packed, bpr = _pack_1bpp(raw, width=8, height=1)
        assert packed == bytes([0xFF])

    def test_alternating_pixels(self):
        # B W B W B W B W → 0b10101010 = 0xAA
        raw = bytes([0, 255, 0, 255, 0, 255, 0, 255])
        packed, bpr = _pack_1bpp(raw, width=8, height=1)
        assert packed == bytes([0xAA])

    def test_bytes_per_row_9px(self):
        # 9 pixels → 2 bytes per row (ceil(9/8))
        raw = bytes([0] * 9)
        packed, bpr = _pack_1bpp(raw, width=9, height=1)
        assert bpr == 2

    def test_two_rows(self):
        raw = bytes([0] * 8 + [255] * 8)
        packed, bpr = _pack_1bpp(raw, width=8, height=2)
        assert len(packed) == 2
        assert packed[0] == 0xFF   # row 1: all black
        assert packed[1] == 0x00   # row 2: all white


class TestOSPrinterStatus:
    def test_os_printer_has_status(self):
        from bridge_agent.card_printer import OSPrintQueuePrinter
        p = OSPrintQueuePrinter()
        s = p.status()
        assert "available" in s
        assert "type" in s
        assert s["type"] == "os_queue"


class TestWebSocketServerPrint:
    """Tests for print validation in the WebSocket server (no actual socket)."""

    @pytest.mark.asyncio
    async def test_print_invalid_base64_sends_error(self):
        from bridge_agent.nfc_reader import MockNFCReader
        from bridge_agent.card_printer import MockPrinter
        from bridge_agent.websocket_server import BridgeServer

        printer = MockPrinter()
        nfc = MockNFCReader(on_tap=lambda uid: None)
        server = BridgeServer(nfc=nfc, printer=printer)

        sent = []

        class FakeWS:
            async def send(self, msg): sent.append(msg)

        msg = {"type": "print_card", "request_id": "r1", "pdf_b64": "!!!not-b64!!!"}
        await server._dispatch(FakeWS(), msg)

        import json
        response = json.loads(sent[-1])
        assert response["type"] == "print_error"
        assert response["request_id"] == "r1"

    @pytest.mark.asyncio
    async def test_print_non_pdf_bytes_sends_error(self):
        import base64
        from bridge_agent.nfc_reader import MockNFCReader
        from bridge_agent.card_printer import MockPrinter
        from bridge_agent.websocket_server import BridgeServer

        server = BridgeServer(nfc=MockNFCReader(on_tap=lambda uid: None), printer=MockPrinter())
        sent = []

        class FakeWS:
            async def send(self, msg): sent.append(msg)

        bad_pdf = base64.b64encode(b"this is not a PDF").decode()
        await server._dispatch(FakeWS(), {"type": "print_card", "request_id": "r2", "pdf_b64": bad_pdf})

        import json
        response = json.loads(sent[-1])
        assert response["type"] == "print_error"
        assert response["request_id"] == "r2"

    @pytest.mark.asyncio
    async def test_print_valid_pdf_succeeds(self):
        import base64
        from bridge_agent.nfc_reader import MockNFCReader
        from bridge_agent.card_printer import MockPrinter
        from bridge_agent.websocket_server import BridgeServer

        printer = MockPrinter()
        server = BridgeServer(nfc=MockNFCReader(on_tap=lambda uid: None), printer=printer)
        sent = []

        class FakeWS:
            async def send(self, msg): sent.append(msg)

        pdf_b64 = base64.b64encode(b"%PDF-1.4 minimal").decode()
        await server._dispatch(FakeWS(), {"type": "print_card", "request_id": "r3", "pdf_b64": pdf_b64})

        import json
        response = json.loads(sent[-1])
        assert response["type"] == "print_ok"
        assert response["request_id"] == "r3"
        assert len(printer.printed) == 1

    @pytest.mark.asyncio
    async def test_status_message(self):
        from bridge_agent.nfc_reader import MockNFCReader
        from bridge_agent.card_printer import MockPrinter
        from bridge_agent.websocket_server import BridgeServer

        server = BridgeServer(nfc=MockNFCReader(on_tap=lambda uid: None), printer=MockPrinter())
        sent = []

        class FakeWS:
            async def send(self, msg): sent.append(msg)

        await server._dispatch(FakeWS(), {"type": "status"})

        import json
        response = json.loads(sent[-1])
        assert response["type"] == "status"
        assert "nfc" in response
        assert "printer" in response

    @pytest.mark.asyncio
    async def test_encode_nfc_returns_not_supported(self):
        from bridge_agent.nfc_reader import MockNFCReader
        from bridge_agent.card_printer import MockPrinter
        from bridge_agent.websocket_server import BridgeServer

        server = BridgeServer(nfc=MockNFCReader(on_tap=lambda uid: None), printer=MockPrinter())
        sent = []

        class FakeWS:
            async def send(self, msg): sent.append(msg)

        await server._dispatch(FakeWS(), {"type": "encode_nfc", "request_id": "r4", "uid": "A1B2C3D4"})

        import json
        response = json.loads(sent[-1])
        assert response["type"] == "encode_error"

    @pytest.mark.asyncio
    async def test_unknown_message_type(self):
        from bridge_agent.nfc_reader import MockNFCReader
        from bridge_agent.card_printer import MockPrinter
        from bridge_agent.websocket_server import BridgeServer

        server = BridgeServer(nfc=MockNFCReader(on_tap=lambda uid: None), printer=MockPrinter())
        sent = []

        class FakeWS:
            async def send(self, msg): sent.append(msg)

        await server._dispatch(FakeWS(), {"type": "totally_unknown"})

        import json
        response = json.loads(sent[-1])
        assert response["type"] == "error"


class TestNFCTapBroadcast:
    def test_on_tap_updates_callback(self):
        from bridge_agent.nfc_reader import MockNFCReader
        from bridge_agent.card_printer import MockPrinter
        from bridge_agent.websocket_server import BridgeServer

        taps_received = []

        def capture(uid):
            taps_received.append(uid)

        nfc = MockNFCReader(on_tap=capture)
        printer = MockPrinter()
        server = BridgeServer(nfc=nfc, printer=printer)

        # Simulate a tap — the server rewires on_tap to broadcast
        # Since no event loop / WS clients, just check the nfc._on_tap is set
        assert server._nfc._on_tap is not None
