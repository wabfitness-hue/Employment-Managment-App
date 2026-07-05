@echo off
REM Build the Bridge Agent as a single Windows executable
REM Prerequisites: Python 3.11+, pip

echo ============================================================
echo  Employee Management System — Bridge Agent Builder (Windows)
echo ============================================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH.
    pause
    exit /b 1
)

echo [1/4] Creating virtual environment...
if exist .venv_build rmdir /s /q .venv_build
python -m venv .venv_build

echo [2/4] Installing dependencies...
.venv_build\Scripts\pip install --quiet --upgrade pip
.venv_build\Scripts\pip install --quiet websockets cryptography pyscard PyMuPDF pyinstaller

echo [3/4] Building executable...
.venv_build\Scripts\pyinstaller bridge_agent.spec --clean --noconfirm

echo [4/4] Copying config template...
if not exist dist\bridge_agent.env (
    copy bridge_agent.env.example dist\bridge_agent.env
    echo.
    echo  IMPORTANT: Edit dist\bridge_agent.env before running the agent.
    echo  Set BRIDGE_AGENT_SECRET to match the backend .env value.
)

echo.
echo ============================================================
echo  Build complete!
echo  Executable: dist\bridge_agent.exe
echo  Config:     dist\bridge_agent.env
echo ============================================================
pause
