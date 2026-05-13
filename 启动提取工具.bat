@echo off
chcp 65001 >nul
title 音频提取工具

echo.
echo    ════════════════════════════════
echo       音频提取工具 - 启动中...
echo    ════════════════════════════════
echo.

:: 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo   [错误] 未找到 Python，请先安装 Python 3
    echo   下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: 检查并安装 imageio-ffmpeg（pip show 比 import 模块快得多）
pip show imageio-ffmpeg >nul 2>&1
if %errorlevel% neq 0 (
    echo   [安装] 正在自动安装 ffmpeg 组件...
    python -m pip install imageio-ffmpeg -q
    if %errorlevel% neq 0 (
        echo   [错误] 安装失败，请手动运行: pip install imageio-ffmpeg
        pause
        exit /b 1
    )
    echo   [完成] ffmpeg 组件安装成功
)

echo   [启动] 正在打开界面...
echo.

:: 优先用 pythonw（无后台终端窗口），失败则用 python
where /Q pythonw 2>nul && (
    start "" pythonw "%~dp0extract_audio_gui.py"
) || (
    start "" python "%~dp0extract_audio_gui.py"
)

