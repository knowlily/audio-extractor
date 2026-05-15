@echo off
title Audio Extractor

echo.
echo    ================================
echo       Audio Extractor - Starting...
echo    ================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo   [ERROR] Python 3 not found
    echo   Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Check / install imageio-ffmpeg
python -m pip show imageio-ffmpeg >nul 2>&1
if %errorlevel% neq 0 (
    echo   [INSTALL] Installing ffmpeg component...
    python -m pip install imageio-ffmpeg -q
    if %errorlevel% neq 0 (
        echo   [ERROR] Install failed. Run: pip install imageio-ffmpeg
        pause
        exit /b 1
    )
    echo   [OK] ffmpeg component installed
)

echo   [LAUNCH] Starting GUI...
echo.

:: Prefer pythonw (no console window), fall back to python
pythonw --version >nul 2>&1 && (
    start "" pythonw "%~dp0extract_audio_gui.py"
) || (
    start "" python "%~dp0extract_audio_gui.py"
)
