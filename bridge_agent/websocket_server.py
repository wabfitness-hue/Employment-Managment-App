"""
WebSocket server — the heart of the bridge agent.

Listens on ws://127.0.0.1:8765 (configurable).
The web app connects here, authenticates with the shared secret,
then receives NFC tap events and can send print/encode commands.

Connection lifecycle:
  1. Client connects
  2. Client sends {"type": "auth", "secret": "..."}
  3. Server replies {"type": "auth_ok"} or {"type": "auth_fail", ...}
  4. All subsequent messages require the connection to be authenticated
  5. NFC taps are pushed to all authenticated clients
"""
import asyncio
import base64
import logging
import time
from collections import defaultdict
from typing import Optional, Set

import websockets
try:
    from websockets.asyncio.server import ServerConnection as WebSocketServerProtocol
    _LEGACY = False
except ImportError:
    from websockets.server import WebSocketServerProtocol  # type: ignore[no-redef]
    _LEGACY = True

from . import protocol
from .config import WS_HOST, WS_PORT, BRIDGE_SECRET, ALLOW_INSECURE_BRIDGE
from .nfc_reader import NFCReader
from .card_printer import CardPrinter

logger = logging.getLogger(__name__)

_MAX_WS_MESSAGE_BYTES = 50 * 1024 * 1024   # 50 MB — websockets library limit
_MAX_PDF_B64_BYTES = 40 * 1024 * 1024      # 40 MB base64 PDF
_MAX_CONNECTIONS_PER_IP = 5
_RATE_LIMIT_WINDOW_SECS = 60


class BridgeServer:
    def __init__(self, nfc: NFCReader, printer: CardPrinter):
        self._nfc = nfc
        self._printer = printer
        self._authenticated_clients: Set[WebSocketServerProtocol] = set()
        self._server = None
        self._connections_by_ip: dict[str, list[float]] = defaultdict(list)

        # Wire up the NFC tap callback to broadcast to all clients
        nfc._on_tap = self._on_nfc_tap

    # ── Server lifecycle ──────────────────────────────────────────────────────

    async def start(self) -> None:
        if not BRIDGE_SECRET:
            if ALLOW_INSECURE_BRIDGE:
                logger.warning("BRIDGE_AGENT_SECRET is not set — running INSECURE (ALLOW_INSECURE_BRIDGE). Dev only.")
            else:
                logger.error(
                    "BRIDGE_AGENT_SECRET is not set — all client connections will be REFUSED. "
                    "Set BRIDGE_AGENT_SECRET (recommended), or ALLOW_INSECURE_BRIDGE=1 for local dev."
                )
        self._nfc.start()
        self._server = await websockets.serve(
            self._handle_client, WS_HOST, WS_PORT,
            ping_interval=20,
            ping_timeout=10,
            max_size=_MAX_WS_MESSAGE_BYTES,
        )
        logger.info("Bridge agent WebSocket server listening on ws://%s:%s", WS_HOST, WS_PORT)

    async def stop(self) -> None:
        self._nfc.stop()
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        logger.info("Bridge agent stopped.")

    async def run_forever(self) -> None:
        await self.start()
        try:
            await asyncio.Future()   # run until cancelled
        finally:
            await self.stop()

    # ── Per-connection handler ────────────────────────────────────────────────

    async def _handle_client(self, ws: WebSocketServerProtocol, path: str = "/") -> None:
        client_ip = ws.remote_address[0] if ws.remote_address else "unknown"
        now = time.monotonic()

        # Per-IP connection rate limiting
        self._connections_by_ip[client_ip] = [
            t for t in self._connections_by_ip[client_ip]
            if now - t < _RATE_LIMIT_WINDOW_SECS
        ]
        if len(self._connections_by_ip[client_ip]) >= _MAX_CONNECTIONS_PER_IP:
            logger.warning("Rate limit: too many connections from %s", client_ip)
            await ws.close(1008, "Too many connections")
            return
        self._connections_by_ip[client_ip].append(now)

        logger.info("Client connected from %s", ws.remote_address)
        authenticated = False

        try:
            async for raw in ws:
                try:
                    msg = protocol.decode(raw)
                except Exception:
                    await ws.send(protocol.encode(protocol.make_error("Invalid JSON.")))
                    continue

                msg_type = msg.get("type", "")

                # Auth must be first
                if not authenticated:
                    if msg_type == "auth":
                        if protocol.verify_secret(msg.get("secret", ""), BRIDGE_SECRET, ALLOW_INSECURE_BRIDGE):
                            authenticated = True
                            self._authenticated_clients.add(ws)
                            await ws.send(protocol.encode({"type": "auth_ok"}))
                            logger.info("Client authenticated from %s", ws.remote_address)
                        else:
                            logger.warning("Failed auth attempt from %s", ws.remote_address)
                            await ws.send(protocol.encode({"type": "auth_fail", "reason": "Invalid secret."}))
                            await ws.close(1008, "Unauthorized")
                            return
                    else:
                        await ws.send(protocol.encode(protocol.make_error("Authenticate first.")))
                    continue

                # Authenticated — dispatch message
                await self._dispatch(ws, msg)

        except websockets.exceptions.ConnectionClosed:
            logger.info("Client disconnected: %s", ws.remote_address)
        finally:
            self._authenticated_clients.discard(ws)

    async def _dispatch(self, ws: WebSocketServerProtocol, msg: dict) -> None:
        msg_type = msg.get("type", "")

        if msg_type == "status":
            await ws.send(protocol.encode(
                protocol.make_status(self._nfc.status(), self._printer.status())
            ))

        elif msg_type == "print_card":
            await self._handle_print(ws, msg)

        elif msg_type == "read_nfc_once":
            await self._handle_read_once(ws, msg)

        elif msg_type == "encode_nfc":
            await ws.send(protocol.encode(
                protocol.make_encode_error(
                    msg.get("request_id", ""),
                    "NFC encode (write) is not yet supported. Cards are read-only in this version.",
                )
            ))

        else:
            await ws.send(protocol.encode(protocol.make_error(f"Unknown message type: {msg_type!r}")))

    async def _handle_print(self, ws: WebSocketServerProtocol, msg: dict) -> None:
        request_id = msg.get("request_id", "")
        pdf_b64 = msg.get("pdf_b64", "")
        copies = max(1, min(int(msg.get("copies", 1)), 10))

        if not pdf_b64:
            await ws.send(protocol.encode(protocol.make_print_error(request_id, "No PDF data provided.")))
            return

        if len(pdf_b64) > _MAX_PDF_B64_BYTES:
            await ws.send(protocol.encode(protocol.make_print_error(request_id, "PDF data too large.")))
            return

        try:
            pdf_bytes = base64.b64decode(pdf_b64)
        except Exception:
            await ws.send(protocol.encode(protocol.make_print_error(request_id, "Invalid base64 PDF data.")))
            return

        if not pdf_bytes.startswith(b"%PDF"):
            await ws.send(protocol.encode(protocol.make_print_error(request_id, "Data is not a valid PDF.")))
            return

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: self._printer.print_card(pdf_bytes, copies))
            await ws.send(protocol.encode(protocol.make_print_ok(request_id)))
            logger.info("Card printed (request_id=%s, copies=%d)", request_id, copies)
        except Exception as exc:
            logger.error("Print failed: %s", exc)
            await ws.send(protocol.encode(protocol.make_print_error(request_id, str(exc))))

    async def _handle_read_once(self, ws: WebSocketServerProtocol, msg: dict) -> None:
        """
        Wait up to 15 seconds for a single NFC tap and return the UID.
        Used for enrollment: HR taps the card while the browser waits.
        """
        request_id = msg.get("request_id", "")
        future: asyncio.Future = asyncio.get_event_loop().create_future()

        def _capture_tap(uid: str) -> None:
            if not future.done():
                asyncio.get_event_loop().call_soon_threadsafe(future.set_result, uid)

        original_callback = self._nfc._on_tap
        self._nfc._on_tap = _capture_tap

        try:
            uid = await asyncio.wait_for(future, timeout=15.0)
            await ws.send(protocol.encode(protocol.make_nfc_read_result(request_id, uid)))
        except asyncio.TimeoutError:
            await ws.send(protocol.encode(protocol.make_encode_error(request_id, "Timeout waiting for NFC tap.")))
        finally:
            self._nfc._on_tap = original_callback

    # ── NFC tap broadcast ─────────────────────────────────────────────────────

    def _on_nfc_tap(self, uid: str) -> None:
        """Called from the NFC reader thread — schedule broadcast on the event loop."""
        msg = protocol.encode(protocol.make_nfc_tap(uid))
        for client in list(self._authenticated_clients):
            asyncio.get_event_loop().call_soon_threadsafe(
                asyncio.ensure_future, self._safe_send(client, msg)
            )

    async def _safe_send(self, ws: WebSocketServerProtocol, msg: str) -> None:
        try:
            await ws.send(msg)
        except Exception:
            self._authenticated_clients.discard(ws)
