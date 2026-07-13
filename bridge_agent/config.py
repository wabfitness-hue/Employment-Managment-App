"""
Bridge Agent configuration.
Values read from environment variables or bridge_agent.env (same directory as the executable).
"""
import os
import json
from pathlib import Path


def _load_env_file() -> None:
    """Load key=value pairs from bridge_agent.env if it exists."""
    env_path = Path(__file__).parent / "bridge_agent.env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())


_load_env_file()

# WebSocket server settings
WS_HOST: str = os.getenv("BRIDGE_WS_HOST", "127.0.0.1")
WS_PORT: int = int(os.getenv("BRIDGE_WS_PORT", "8765"))

# Shared secret — must match BRIDGE_AGENT_SECRET in the backend .env
BRIDGE_SECRET: str = os.getenv("BRIDGE_AGENT_SECRET", "")

# Dev-only escape hatch: allow the bridge to run WITHOUT a shared secret.
# Off by default so an unset secret fails closed rather than open.
ALLOW_INSECURE_BRIDGE: bool = os.getenv("ALLOW_INSECURE_BRIDGE", "").lower() in ("1", "true", "yes")

# NFC reader settings
NFC_POLL_INTERVAL_MS: int = int(os.getenv("NFC_POLL_INTERVAL_MS", "250"))

# Which side of a barrier/door this reader sits on ("in" or "out"). One bridge
# agent = one physical reader, so buildings with separate entry/exit readers
# (e.g. a barrier) run one bridge instance per reader, each configured with its
# own direction. Defaults to "in" for the common single-reader setup.
_READER_DIRECTION_RAW = os.getenv("READER_DIRECTION", "in").strip().lower()
READER_DIRECTION: str = _READER_DIRECTION_RAW if _READER_DIRECTION_RAW in ("in", "out") else "in"

# Printer settings
PRINTER_NAME: str = os.getenv("PRINTER_NAME", "")          # blank = auto-detect
PRINTER_TYPE: str = os.getenv("PRINTER_TYPE", "auto")      # auto | zebra | fargo | evolis | magicard | os

# Log level
LOG_LEVEL: str = os.getenv("BRIDGE_LOG_LEVEL", "INFO")
