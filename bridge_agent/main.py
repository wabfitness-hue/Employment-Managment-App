"""
Employee Management System — Local Bridge Agent
Entry point. Run directly or as a PyInstaller one-file executable.

Usage:
  python main.py                    # normal run
  python main.py --mock             # use mock NFC + printer (no hardware needed)
  python main.py --printer-type os  # override printer type
"""
import asyncio
import logging
import signal
import sys
from argparse import ArgumentParser

from . import config
from .nfc_reader import NFCReader, MockNFCReader
from .card_printer import PrinterFactory
from .websocket_server import BridgeServer


def _setup_logging() -> None:
    level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _parse_args():
    p = ArgumentParser(description="Employee Management System Bridge Agent")
    p.add_argument("--mock", action="store_true", help="Use mock NFC and printer (no hardware)")
    p.add_argument("--printer-type", default=config.PRINTER_TYPE,
                   choices=["auto", "zebra", "os", "mock"], help="Printer type")
    p.add_argument("--printer-name", default=config.PRINTER_NAME, help="Printer name")
    p.add_argument("--host", default=config.WS_HOST, help="WebSocket bind host")
    p.add_argument("--port", type=int, default=config.WS_PORT, help="WebSocket port")
    return p.parse_args()


async def _run(args) -> None:
    logger = logging.getLogger("bridge")

    if args.mock:
        nfc = MockNFCReader(on_tap=lambda uid: None)
        printer = PrinterFactory.create("mock")
        logger.info("Running in mock mode (no hardware required).")
    else:
        nfc = NFCReader(on_tap=lambda uid: None)
        printer_type = args.printer_type if not args.mock else "mock"
        printer = PrinterFactory.create(printer_type, args.printer_name)

    # Override config with CLI args
    config.WS_HOST = args.host
    config.WS_PORT = args.port

    server = BridgeServer(nfc=nfc, printer=printer)

    loop = asyncio.get_running_loop()

    def _shutdown():
        logger.info("Shutdown signal received.")
        loop.create_task(server.stop())
        sys.exit(0)

    if sys.platform != "win32":
        loop.add_signal_handler(signal.SIGTERM, _shutdown)
        loop.add_signal_handler(signal.SIGINT, _shutdown)

    try:
        await server.run_forever()
    except (KeyboardInterrupt, SystemExit):
        await server.stop()


def main() -> None:
    _setup_logging()
    args = _parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
