#!/bin/bash
# One-time setup: Installs the Clipper Worker URL handler
# After this, clicking "Start Worker" in the web app will automatically launch the worker

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║      🎬 CLIPPER WORKER - ONE-TIME INSTALLATION               ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

cd "$(dirname "$0")"

# Check if app exists
if [ ! -d "ClipperWorker.app" ]; then
    echo "❌ ClipperWorker.app not found!"
    echo "   Make sure you're running this from the project folder."
    read -p "Press Enter to exit..."
    exit 1
fi

echo "📦 Installing ClipperWorker..."

# Copy to Applications folder for proper URL scheme registration
cp -R "ClipperWorker.app" "/Applications/ClipperWorker.app"

# Register the URL scheme by opening and immediately closing the app
echo "🔗 Registering URL scheme (clipperworker://)..."
open -a "/Applications/ClipperWorker.app"
sleep 1

# Also reset launch services to pick up the new URL scheme
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "/Applications/ClipperWorker.app" 2>/dev/null

echo ""
echo "✅ Installation complete!"
echo ""
echo "Now you can click 'Start Worker' in the web app and it will"
echo "automatically launch the worker on your computer!"
echo ""
echo "🌐 Go to: https://instagramposting-production-4e91.up.railway.app"
echo "   Enable 'Use Local Worker' and click 'Start Worker'"
echo ""
read -p "Press Enter to close..."
