@echo off
title Build Audio Extractor EXE

echo.
echo    ========================================
echo       Build Audio Extractor Standalone EXE
echo    ========================================
echo.

echo   [1/3] Checking PyInstaller...
python -c "import PyInstaller" >nul 2>&1
if %errorlevel% neq 0 (
    echo   [INSTALL] Installing PyInstaller...
    python -m pip install pyinstaller -q
    if %errorlevel% neq 0 (
        echo   [ERROR] Failed to install PyInstaller
        pause
        exit /b 1
    )
    echo   [OK] PyInstaller installed
)

echo   [2/3] Cleaning old builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo   [3/3] Building standalone EXE...
echo.
echo   This may take 1-2 minutes...

python -m PyInstaller --onefile --windowed ^
    --name "AudioExtractor" ^
    --collect-binaries imageio_ffmpeg ^
    --collect-binaries tkinterdnd2 ^
    --hidden-import imageio_ffmpeg ^
    --hidden-import tkinterdnd2 ^
    --hidden-import tkinter ^
    --add-data "audio_utils.py;." ^
    extract_audio_gui.py

if %errorlevel% neq 0 (
    echo   [ERROR] Build failed!
    pause
    exit /b 1
)

echo.
echo    ========================================
echo       Build Complete!
echo       Output: dist\AudioExtractor.exe
echo    ========================================
echo.

:: Copy to project root for convenience
copy /y "dist\AudioExtractor.exe" "AudioExtractor.exe" >nul
echo   Copied to: AudioExtractor.exe
echo.

pause
