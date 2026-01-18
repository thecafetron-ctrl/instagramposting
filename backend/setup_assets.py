#!/usr/bin/env python3
"""
Setup script to download Montserrat fonts and prepare assets directory.
Run this before starting the server.
"""

import os
import urllib.request
import zipfile
from pathlib import Path


FONT_URL = "https://fonts.google.com/download?family=Montserrat"
ASSETS_DIR = Path("assets")
FONTS_DIR = ASSETS_DIR / "fonts" / "Montserrat"


def setup_directories():
    """Create required directories."""
    print("Creating directories...")
    ASSETS_DIR.mkdir(exist_ok=True)
    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    Path("generated_images").mkdir(exist_ok=True)
    print("✓ Directories created")


def download_fonts():
    """Download Montserrat fonts from Google Fonts."""
    zip_path = ASSETS_DIR / "montserrat.zip"
    
    if any(FONTS_DIR.glob("*.ttf")):
        print("✓ Fonts already exist, skipping download")
        return
    
    print("Downloading Montserrat fonts...")
    try:
        urllib.request.urlretrieve(FONT_URL, zip_path)
        print("✓ Downloaded font archive")
        
        print("Extracting fonts...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for file in zip_ref.namelist():
                if file.endswith('.ttf') and 'static' in file:
                    # Extract only the static TTF files we need
                    font_name = os.path.basename(file)
                    if any(weight in font_name for weight in ['Regular', 'Medium', 'SemiBold', 'Bold', 'ExtraBold']):
                        if 'Italic' not in font_name:
                            data = zip_ref.read(file)
                            dest_path = FONTS_DIR / font_name
                            with open(dest_path, 'wb') as f:
                                f.write(data)
                            print(f"  Extracted: {font_name}")
        
        # Clean up
        zip_path.unlink()
        print("✓ Fonts installed")
        
    except Exception as e:
        print(f"✗ Failed to download fonts: {e}")
        print("  Please download Montserrat manually from https://fonts.google.com/specimen/Montserrat")
        print(f"  and place the TTF files in: {FONTS_DIR}")


def check_assets():
    """Check required assets and provide instructions."""
    print("\nAsset Status:")
    
    # Check background
    bg_path = ASSETS_DIR / "background.png"
    if bg_path.exists():
        print("✓ background.png found")
    else:
        print("✗ background.png MISSING")
        print("  → Place your black marble texture image at: assets/background.png")
    
    # Check logo
    logo_path = ASSETS_DIR / "logo.png"
    if logo_path.exists():
        print("✓ logo.png found")
    else:
        print("✗ logo.png MISSING")
        print("  → Place your STRUCTURE logo at: assets/logo.png")
    
    # Check fonts
    required_fonts = [
        "Montserrat-Regular.ttf",
        "Montserrat-Medium.ttf",
        "Montserrat-SemiBold.ttf",
        "Montserrat-Bold.ttf",
        "Montserrat-ExtraBold.ttf",
    ]
    
    missing_fonts = []
    for font in required_fonts:
        if (FONTS_DIR / font).exists():
            print(f"✓ {font} found")
        else:
            missing_fonts.append(font)
            print(f"✗ {font} MISSING")
    
    if missing_fonts:
        print(f"\n  → Download fonts from: https://fonts.google.com/specimen/Montserrat")
        print(f"  → Place TTF files in: {FONTS_DIR}")
    
    return bg_path.exists() and logo_path.exists() and not missing_fonts


def main():
    print("=" * 50)
    print("Instagram Carousel Generator - Asset Setup")
    print("=" * 50)
    print()
    
    setup_directories()
    download_fonts()
    
    all_ready = check_assets()
    
    print()
    print("=" * 50)
    if all_ready:
        print("✓ All assets ready! You can start the server.")
    else:
        print("⚠ Some assets are missing. Please add them before generating images.")
        print("  The server will still work but image rendering may fail.")
    print("=" * 50)


if __name__ == "__main__":
    main()
