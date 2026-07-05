@echo off
REM Run the bridge agent in mock mode (no physical NFC reader or printer required)
REM Useful for testing the frontend without hardware.
python main.py --mock
