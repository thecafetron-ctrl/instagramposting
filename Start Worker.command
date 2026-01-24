#!/bin/bash
# Video Clipper - Local Worker
# Keeps running and processes ALL jobs automatically
# Just start it once and leave it running!

cd "$(dirname "$0")"

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║           🎬 VIDEO CLIPPER - LOCAL WORKER                    ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║  This worker runs continuously and handles ALL jobs:         ║"
echo "║  • Transcription (Whisper)                                   ║"
echo "║  • Viral moment analysis                                     ║"
echo "║  • Video rendering                                           ║"
echo "║                                                              ║"
echo "║  Just leave this running! Press Ctrl+C to stop.              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Check if another worker is already running
EXISTING_PID=$(pgrep -f "run_worker.py.*railway" 2>/dev/null | head -1)
if [ -n "$EXISTING_PID" ]; then
    echo "⚠️  Another worker is already running (PID: $EXISTING_PID)"
    echo ""
    read -p "Kill it and start fresh? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        pkill -f "run_worker.py.*railway" 2>/dev/null
        sleep 1
        echo "✓ Old worker stopped"
    else
        echo "Exiting. Use the existing worker."
        exit 0
    fi
fi

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found! Please install Python first."
    echo "   Download from: https://www.python.org/downloads/"
    read -p "Press Enter to exit..."
    exit 1
fi
echo "✅ Python: $(python3 --version)"

# Check for FFmpeg
if ! command -v ffmpeg &> /dev/null; then
    echo "❌ FFmpeg not found!"
    echo ""
    if command -v brew &> /dev/null; then
        echo "Installing FFmpeg via Homebrew..."
        brew install ffmpeg
    else
        echo "Please install FFmpeg:"
        echo "   brew install ffmpeg"
        read -p "Press Enter to exit..."
        exit 1
    fi
fi
echo "✅ FFmpeg found"

# Install Python dependencies
echo ""
echo "📦 Checking Python dependencies..."
pip3 install -q requests yt-dlp faster-whisper 2>/dev/null || pip install -q requests yt-dlp faster-whisper 2>/dev/null
echo "✅ Dependencies ready"

echo ""
echo "🚀 Starting worker..."
echo "   Server: https://instagramposting-production-4e91.up.railway.app"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "   Leave this window open! Worker will process jobs automatically."
echo "   Press Ctrl+C to stop."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Run the worker (it will keep running until Ctrl+C)
python3 run_worker.py https://instagramposting-production-4e91.up.railway.app

echo ""
echo "Worker stopped."
read -p "Press Enter to close..."
