"""
Tests for BridgeServer._resolve_printer — picking which printer to use for a
given print_card message (per-print picker vs. the bridge's configured default).
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))

from bridge_agent.websocket_server import BridgeServer
from bridge_agent.card_printer import MockPrinter, OSPrintQueuePrinter, ZebraPrinter


class _StubNFC:
    """Minimal stand-in — BridgeServer only wires up `_on_tap` at construction."""
    _on_tap = None


def _server():
    default = MockPrinter()
    return BridgeServer(nfc=_StubNFC(), printer=default), default


class TestResolvePrinter:
    def test_no_printer_field_uses_default(self):
        server, default = _server()
        assert server._resolve_printer({}) is default

    def test_os_target_builds_os_printer(self):
        server, _ = _server()
        p = server._resolve_printer({"printer": {"target_type": "os", "target": "3rd Floor Printer"}})
        assert isinstance(p, OSPrintQueuePrinter)
        assert p.name == "3rd Floor Printer"

    def test_zebra_target_builds_zebra_printer(self):
        server, _ = _server()
        p = server._resolve_printer({"printer": {"target_type": "zebra", "target": "192.168.1.50"}})
        assert isinstance(p, ZebraPrinter)
        assert p.host == "192.168.1.50"

    def test_missing_target_falls_back_to_default(self):
        server, default = _server()
        p = server._resolve_printer({"printer": {"target_type": "os", "target": ""}})
        assert p is default

    def test_unknown_target_type_falls_back_to_default(self):
        server, default = _server()
        p = server._resolve_printer({"printer": {"target_type": "unknown", "target": "x"}})
        assert p is default

    def test_non_dict_printer_field_falls_back_to_default(self):
        server, default = _server()
        p = server._resolve_printer({"printer": "not-a-dict"})
        assert p is default

    # ── Server-side re-validation (bridge must not trust the target blindly) ──

    def test_zebra_target_invalid_ip_falls_back_to_default(self):
        server, default = _server()
        p = server._resolve_printer({"printer": {"target_type": "zebra", "target": "not-an-ip; rm -rf /"}})
        assert p is default

    def test_zebra_target_hostname_rejected(self):
        server, default = _server()
        p = server._resolve_printer({"printer": {"target_type": "zebra", "target": "evil.example.com"}})
        assert p is default

    def test_zebra_target_out_of_range_octet_rejected(self):
        server, default = _server()
        p = server._resolve_printer({"printer": {"target_type": "zebra", "target": "999.1.1.1"}})
        assert p is default

    def test_os_target_leading_dash_rejected(self):
        server, default = _server()
        p = server._resolve_printer({"printer": {"target_type": "os", "target": "-print-settings"}})
        assert p is default

    def test_os_target_control_char_rejected(self):
        server, default = _server()
        p = server._resolve_printer({"printer": {"target_type": "os", "target": "Printer\nInjected"}})
        assert p is default

    def test_os_target_non_string_rejected(self):
        server, default = _server()
        p = server._resolve_printer({"printer": {"target_type": "os", "target": 12345}})
        assert p is default

    def test_valid_os_name_with_spaces_accepted(self):
        server, _ = _server()
        p = server._resolve_printer({"printer": {"target_type": "os", "target": "3rd Floor Printer (HP)"}})
        assert isinstance(p, OSPrintQueuePrinter)
