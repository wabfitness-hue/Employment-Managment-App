"""
NFC/RFID card reader interface using PC/SC (pyscard).

Supports any PC/SC-compliant USB reader (ACS ACR122U, HID Omnikey,
Identiv uTrust, SpringCard, etc.).

The reader runs in a background thread and calls a callback whenever
a new card UID is detected. It de-duplicates within a hold-off window
so a single card tap does not fire dozens of callbacks.
"""
import threading
import time
import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# De-dup: same UID won't re-fire within this many seconds
_HOLDOFF_SECONDS = 2.0

# How long to wait between PC/SC poll loops (seconds)
_POLL_SLEEP = 0.25


class NFCReader:
    """
    Manages a PC/SC NFC reader.
    Call start() to begin polling; call stop() to shut down cleanly.
    """

    def __init__(self, on_tap: Callable[[str], None]):
        self._on_tap = on_tap
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_uid: Optional[str] = None
        self._last_seen_at: float = 0.0
        self._reader_name: Optional[str] = None
        self._available = False

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def reader_name(self) -> Optional[str]:
        return self._reader_name

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("NFC reader thread started.")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3)
        logger.info("NFC reader thread stopped.")

    def status(self) -> dict:
        return {
            "available": self._available,
            "reader": self._reader_name,
        }

    def _run(self) -> None:
        """Background polling loop. Restarts PC/SC connection on error."""
        while not self._stop_event.is_set():
            try:
                self._poll_loop()
            except Exception as exc:
                logger.warning("NFC reader error: %s — retrying in 3s", exc)
                self._available = False
                self._reader_name = None
                time.sleep(3)

    def _poll_loop(self) -> None:
        try:
            from smartcard.System import readers as get_readers
            from smartcard.CardConnection import CardConnection
            from smartcard.Exceptions import CardConnectionException, NoCardException
        except ImportError:
            logger.warning(
                "pyscard not installed — NFC reader unavailable. "
                "Install with: pip install pyscard"
            )
            self._available = False
            self._stop_event.wait()
            return

        reader_list = get_readers()
        if not reader_list:
            logger.debug("No PC/SC readers found. Waiting...")
            self._available = False
            time.sleep(3)
            return

        reader = reader_list[0]
        self._reader_name = str(reader)
        self._available = True
        logger.info("Using PC/SC reader: %s", self._reader_name)

        while not self._stop_event.is_set():
            try:
                conn = reader.createConnection()
                conn.connect()
                uid = self._get_uid(conn)
                conn.disconnect()

                if uid:
                    now = time.monotonic()
                    if uid != self._last_uid or (now - self._last_seen_at) > _HOLDOFF_SECONDS:
                        self._last_uid = uid
                        self._last_seen_at = now
                        logger.info("NFC tap: %s", uid)
                        try:
                            self._on_tap(uid)
                        except Exception as cb_exc:
                            logger.error("on_tap callback error: %s", cb_exc)
                else:
                    # Card removed
                    self._last_uid = None

            except Exception:
                # No card present — expected, not an error
                self._last_uid = None

            time.sleep(_POLL_SLEEP)

        self._available = False

    @staticmethod
    def _get_uid(connection) -> Optional[str]:
        """
        Send GET DATA (FF CA 00 00 00) APDU to retrieve the card UID.
        Returns hex UID string or None.
        """
        GET_UID = [0xFF, 0xCA, 0x00, 0x00, 0x00]
        try:
            data, sw1, sw2 = connection.transmit(GET_UID)
            if sw1 == 0x90 and sw2 == 0x00 and data:
                return "".join(f"{b:02X}" for b in data)
        except Exception:
            pass
        return None


class MockNFCReader(NFCReader):
    """
    Stub reader for testing — fires on_tap with a fake UID on demand.
    Does not require pyscard.
    """

    def __init__(self, on_tap: Callable[[str], None]):
        super().__init__(on_tap)
        self._available = True
        self._reader_name = "Mock NFC Reader (test)"

    def start(self) -> None:
        logger.info("MockNFCReader started (no hardware).")

    def stop(self) -> None:
        logger.info("MockNFCReader stopped.")

    def simulate_tap(self, uid: str = "A1B2C3D4") -> None:
        """Trigger a fake card tap — used in tests and development."""
        self._on_tap(uid)
