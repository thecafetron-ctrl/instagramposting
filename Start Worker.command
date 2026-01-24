#!/bin/bash
# Double-click this file to start the local video clipper worker
# It will process jobs from Railway using your computer's power

cd "$(dirname "$0")"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║           🎬 VIDEO CLIPPER - LOCAL WORKER                    ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found! Please install Python first."
    echo "   Download from: https://www.python.org/downloads/"
    read -p "Press Enter to exit..."
    exit 1
fi
echo "✅ Python found: $(python3 --version)"

# Check for FFmpeg
if ! command -v ffmpeg &> /dev/null; then
    echo "❌ FFmpeg not found!"
    echo ""
    echo "Installing FFmpeg via Homebrew..."
    if command -v brew &> /dev/null; then
        brew install ffmpeg
    else
        echo "Please install FFmpeg manually:"
        echo "   brew install ffmpeg"
        echo "   OR download from: https://ffmpeg.org/download.html"
        read -p "Press Enter to exit..."
        exit 1
    fi
fi
echo "✅ FFmpeg found"

# Install Python dependencies
echo ""
echo "📦 Checking Python dependencies..."
pip3 install -q requests yt-dlp 2>/dev/null || pip install -q requests yt-dlp 2>/dev/null

echo ""
echo "🚀 Starting worker..."
echo "   Server: https://instagramposting-production-4e91.up.railway.app"
echo ""
echo "   Press Ctrl+C to stop the worker"
echo ""

# Run the worker
python3 run_worker.py https://instagramposting-production-4e91.up.railway.app

echo ""
read -p "Press Enter to close..."
