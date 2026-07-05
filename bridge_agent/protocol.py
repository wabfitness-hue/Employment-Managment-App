"""
WebSocket message protocol between the bridge agent and the web app.

All messages are JSON objects with a required "type" field.

Web app → Bridge agent:
  {"type": "auth",    "secret": "..."}
  {"type": "status"}
  {"type": "print_card", "request_id": "...", "pdf_b64": "...", "printer": "optional-name"}
  {"type": "encode_nfc", "request_id": "...", "uid": "A1B2C3D4", "employee_id": "DIR-0001"}
  {"type": "read_nfc_once"}          — one-shot read, used for NFC enrollment

Bridge agent → Web app:
  {"type": "auth_ok"}
  {"type": "auth_fail", "reason": "..."}
  {"type": "status", "nfc": {...}, "printer": {...}}
  {"type": "nfc_tap", "uid": "A1B2C3D4"}           — unsolicited on card tap
  {"type": "nfc_read_result", "request_id": "...", "uid": "A1B2C3D4"}
  {"type": "print_ok",    "request_id": "..."}
  {"type": "print_error", "request_id": "...", "error": "..."}
  {"type": "encode_ok",   "request_id": "..."}
  {"type": "encode_error","request_id": "...", "error": "..."}
  {"type": "error", "error": "..."}
"""
import json
import hmac
import hashlib
from typing import Any


def encode(msg: dict) -> str:
    return json.dumps(msg)


def decode(raw: str) -> dict:
    return json.loads(raw)


def make_status(nfc_info: dict, printer_info: dict) -> dict:
    return {"type": "status", "nfc": nfc_info, "printer": printer_info}


def make_nfc_tap(uid: str) -> dict:
    return {"type": "nfc_tap", "uid": uid}


def make_print_ok(request_id: str) -> dict:
    return {"type": "print_ok", "request_id": request_id}


def make_print_error(request_id: str, error: str) -> dict:
    return {"type": "print_error", "request_id": request_id, "error": error}


def make_encode_ok(request_id: str) -> dict:
    return {"type": "encode_ok", "request_id": request_id}


def make_encode_error(request_id: str, error: str) -> dict:
    return {"type": "encode_error", "request_id": request_id, "error": error}


def make_nfc_read_result(request_id: str, uid: str) -> dict:
    return {"type": "nfc_read_result", "request_id": request_id, "uid": uid}


def make_error(error: str) -> dict:
    return {"type": "error", "error": error}


def verify_secret(provided: str, expected: str) -> bool:
    """Constant-time comparison to prevent timing attacks."""
    if not expected:
        return True   # no secret configured = open (dev mode only)
    return hmac.compare_digest(provided.encode(), expected.encode())
