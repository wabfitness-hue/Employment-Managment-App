"""
Tests for the NFC reader module (using MockNFCReader — no hardware needed).
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))

from bridge_agent.nfc_reader import MockNFCReader, NFCReader


class TestMockNFCReader:
    def test_mock_reports_available(self):
        reader = MockNFCReader(on_tap=lambda uid: None)
        assert reader.is_available is True

    def test_mock_reader_name(self):
        reader = MockNFCReader(on_tap=lambda uid: None)
        assert "Mock" in reader.reader_name

    def test_simulate_tap_calls_callback(self):
        taps = []
        reader = MockNFCReader(on_tap=taps.append)
        reader.simulate_tap("A1B2C3D4")
        assert taps == ["A1B2C3D4"]

    def test_simulate_multiple_taps(self):
        taps = []
        reader = MockNFCReader(on_tap=taps.append)
        reader.simulate_tap("AA000001")
        reader.simulate_tap("BB000002")
        assert taps == ["AA000001", "BB000002"]

    def test_default_uid(self):
        taps = []
        reader = MockNFCReader(on_tap=taps.append)
        reader.simulate_tap()   # default uid
        assert len(taps) == 1
        assert taps[0] == "A1B2C3D4"

    def test_start_stop_no_error(self):
        reader = MockNFCReader(on_tap=lambda uid: None)
        reader.start()
        reader.stop()   # should not raise

    def test_status_returns_dict(self):
        reader = MockNFCReader(on_tap=lambda uid: None)
        status = reader.status()
        assert "available" in status
        assert "reader" in status

    def test_status_available(self):
        reader = MockNFCReader(on_tap=lambda uid: None)
        assert reader.status()["available"] is True

    def test_callback_receives_uppercase_uid(self):
        """UIDs should be delivered as-is; uppercasing happens in the backend."""
        taps = []
        reader = MockNFCReader(on_tap=taps.append)
        reader.simulate_tap("a1b2c3d4")
        assert taps[0] == "a1b2c3d4"   # mock passes through unchanged


class TestNFCReaderInit:
    def test_real_reader_starts_unavailable(self):
        """Real reader without pyscard should be unavailable (not crash)."""
        reader = NFCReader(on_tap=lambda uid: None)
        # Not started yet — default state
        assert reader.is_available is False
        assert reader.reader_name is None

    def test_status_not_started(self):
        reader = NFCReader(on_tap=lambda uid: None)
        status = reader.status()
        assert status["available"] is False
        assert status["reader"] is None

    def test_get_uid_helper_graceful(self):
        """_get_uid with a mock connection that always raises."""
        class FailConn:
            def transmit(self, _):
                raise RuntimeError("no card")
        result = NFCReader._get_uid(FailConn())
        assert result is None
