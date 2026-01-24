@echo off
REM Double-click this file to start the local video clipper worker
REM It will process jobs from Railway using your computer's power

cd /d "%~dp0"

echo ================================================================
echo           VIDEO CLIPPER - LOCAL WORKER
echo ================================================================
echo.

REM Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found! Please install Python first.
    echo Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [OK] Python found

REM Check for FFmpeg
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo ERROR: FFmpeg not found!
    echo.
    echo Please install FFmpeg:
    echo   winget install ffmpeg
    echo   OR download from: https://ffmpeg.org/download.html
    pause
    exit /b 1
)
echo [OK] FFmpeg found

echo.
echo Installing Python dependencies...
pip install -q requests yt-dlp 2>nul

echo.
echo Starting worker...
echo Server: https://instagramposting-production-4e91.up.railway.app
echo.
echo Press Ctrl+C to stop the worker
echo.

python run_worker.py https://instagramposting-production-4e91.up.railway.app

echo.
pause
