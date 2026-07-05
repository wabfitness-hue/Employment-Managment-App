#!/usr/bin/env bash
# Build the Bridge Agent as a single executable on macOS or Linux.
# Prerequisites: Python 3.11+, pcscd running (Linux: sudo apt install pcscd)

set -euo pipefail

echo "============================================================"
echo " Employee Management System — Bridge Agent Builder (Unix)"
echo "============================================================"
echo

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 is not installed." >&2
    exit 1
fi

echo "[1/4] Creating virtual environment..."
rm -rf .venv_build
python3 -m venv .venv_build

echo "[2/4] Installing dependencies..."
.venv_build/bin/pip install --quiet --upgrade pip
.venv_build/bin/pip install --quiet websockets cryptography pyscard PyMuPDF pyinstaller

echo "[3/4] Building executable..."
.venv_build/bin/pyinstaller bridge_agent.spec --clean --noconfirm

echo "[4/4] Copying config template..."
if [ ! -f dist/bridge_agent.env ]; then
    cp bridge_agent.env.example dist/bridge_agent.env
    echo
    echo "  IMPORTANT: Edit dist/bridge_agent.env before running."
    echo "  Set BRIDGE_AGENT_SECRET to match the backend .env value."
fi

echo
echo "============================================================"
echo " Build complete!"
echo " Executable: dist/bridge_agent"
echo " Config:     dist/bridge_agent.env"
echo
echo " To run: ./dist/bridge_agent"
echo " Linux NFC: ensure pcscd is running (sudo systemctl start pcscd)"
echo "============================================================"
