"""
Tests for the bridge agent protocol module.
"""
import json
import pytest
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))

from bridge_agent.protocol import (
    encode, decode, make_status, make_nfc_tap,
    make_print_ok, make_print_error, make_encode_ok, make_encode_error,
    make_nfc_read_result, make_error, verify_secret,
)


class TestEncodeDecode:
    def test_encode_produces_valid_json(self):
        msg = {"type": "auth_ok"}
        raw = encode(msg)
        assert json.loads(raw) == msg

    def test_decode_parses_json(self):
        raw = '{"type": "auth", "secret": "abc"}'
        msg = decode(raw)
        assert msg["type"] == "auth"
        assert msg["secret"] == "abc"

    def test_decode_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            decode("{not valid json")

    def test_roundtrip(self):
        msg = {"type": "nfc_tap", "uid": "A1B2C3D4", "extra": [1, 2, 3]}
        assert decode(encode(msg)) == msg


class TestMessageBuilders:
    def test_make_status(self):
        msg = make_status({"available": True}, {"available": False})
        assert msg["type"] == "status"
        assert msg["nfc"]["available"] is True
        assert msg["printer"]["available"] is False

    def test_make_nfc_tap(self):
        msg = make_nfc_tap("A1B2C3D4")
        assert msg == {"type": "nfc_tap", "uid": "A1B2C3D4"}

    def test_make_print_ok(self):
        msg = make_print_ok("req-001")
        assert msg == {"type": "print_ok", "request_id": "req-001"}

    def test_make_print_error(self):
        msg = make_print_error("req-002", "Printer offline")
        assert msg["type"] == "print_error"
        assert msg["request_id"] == "req-002"
        assert msg["error"] == "Printer offline"

    def test_make_encode_ok(self):
        assert make_encode_ok("req-003")["type"] == "encode_ok"

    def test_make_encode_error(self):
        msg = make_encode_error("req-004", "No writer")
        assert msg["type"] == "encode_error"
        assert "No writer" in msg["error"]

    def test_make_nfc_read_result(self):
        msg = make_nfc_read_result("req-005", "DEADBEEF")
        assert msg == {"type": "nfc_read_result", "request_id": "req-005", "uid": "DEADBEEF"}

    def test_make_error(self):
        msg = make_error("Something went wrong")
        assert msg == {"type": "error", "error": "Something went wrong"}


class TestSecretVerification:
    def test_correct_secret_accepted(self):
        assert verify_secret("my-secret", "my-secret") is True

    def test_wrong_secret_rejected(self):
        assert verify_secret("wrong", "my-secret") is False

    def test_empty_expected_secret_fails_closed(self):
        # No secret configured → deny by default (fail closed)
        assert verify_secret("anything", "") is False
        assert verify_secret("", "") is False

    def test_empty_expected_secret_open_only_with_dev_flag(self):
        # Explicit dev opt-in re-enables the old open behaviour
        assert verify_secret("anything", "", allow_insecure=True) is True
        assert verify_secret("", "", allow_insecure=True) is True

    def test_empty_provided_secret_fails_when_expected(self):
        assert verify_secret("", "my-secret") is False

    def test_case_sensitive(self):
        assert verify_secret("Secret", "secret") is False

    def test_whitespace_matters(self):
        assert verify_secret(" secret", "secret") is False
