"""
Modular Design System for Instagram Carousel Posts.

Three independent customization options:
1. COLOR THEME - the color palette (black, purple, blue, emerald, etc.)
2. BACKGROUND TEXTURE - stars, marble, logistics, mesh, minimal
3. LAYOUT STYLE - centered, left-aligned, etc.
"""

from dataclasses import dataclass
from typing import Literal

# Image dimensions
WIDTH = 1080
HEIGHT = 1350


# ============================================
# COLOR THEMES
# ============================================
COLOR_THEMES = {
    "black": {
        "id": "black",
        "name": "Classic Black",
        "primary": (8, 8, 12),
        "secondary": (15, 15, 20),
        "accent": (100, 100, 120),
        "accent_band": (60, 60, 80, 160),
        "underline": (150, 150, 170),
        "orb_colors": [(40, 40, 55), (50, 50, 65), (35, 35, 50)],
    },
    "purple": {
        "id": "purple",
        "name": "Deep Purple",
        "primary": (12, 8, 20),
        "secondary": (25, 15, 40),
        "accent": (140, 100, 200),
        "accent_band": (100, 70, 160, 160),
        "underline": (160, 120, 255),
        "orb_colors": [(80, 50, 130), (100, 60, 150), (70, 45, 120)],
    },
    "blue": {
        "id": "blue",
        "name": "Ocean Blue",
        "primary": (8, 12, 25),
        "secondary": (15, 25, 50),
        "accent": (80, 150, 220),
        "accent_band": (50, 100, 160, 160),
        "underline": (100, 180, 255),
        "orb_colors": [(40, 80, 140), (50, 100, 160), (35, 70, 130)],
    },
    "emerald": {
        "id": "emerald",
        "name": "Emerald Green",
        "primary": (8, 18, 15),
        "secondary": (15, 35, 28),
        "accent": (80, 200, 140),
        "accent_band": (50, 130, 100, 160),
        "underline": (100, 220, 160),
        "orb_colors": [(40, 100, 70), (50, 120, 85), (35, 90, 60)],
    },
    "copper": {
        "id": "copper",
        "name": "Warm Copper",
        "primary": (18, 12, 8),
        "secondary": (35, 25, 18),
        "accent": (220, 160, 100),
        "accent_band": (160, 110, 70, 160),
        "underline": (255, 180, 120),
        "orb_colors": [(120, 80, 50), (140, 95, 60), (100, 70, 45)],
    },
    "burgundy": {
        "id": "burgundy",
        "name": "Rich Burgundy",
        "primary": (20, 8, 12),
        "secondary": (40, 15, 25),
        "accent": (200, 100, 130),
        "accent_band": (150, 70, 100, 160),
        "underline": (255, 140, 170),
        "orb_colors": [(100, 45, 65), (120, 55, 80), (85, 40, 55)],
    },
    "gold": {
        "id": "gold",
        "name": "Luxury Gold",
        "primary": (15, 12, 8),
        "secondary": (30, 25, 15),
        "accent": (220, 180, 100),
        "accent_band": (180, 140, 60, 160),
        "underline": (255, 210, 120),
        "orb_colors": [(140, 110, 50), (160, 125, 60), (120, 95, 45)],
    },
}


# ============================================
# BACKGROUND TEXTURES
# ============================================
BACKGROUND_TEXTURES = {
    "stars": {
        "id": "stars",
        "name": "Starfield",
        "description": "Dark sky with scattered stars and glowing orbs",
        "star_count": 400,
        "has_orbs": True,
        "has_mesh": False,
        "has_logistics": False,
    },
    "marble": {
        "id": "marble",
        "name": "Marble Texture",
        "description": "Elegant marble-like texture with veins",
        "star_count": 100,
        "has_orbs": True,
        "has_mesh": False,
        "has_logistics": False,
    },
    "logistics": {
        "id": "logistics",
        "name": "Logistics Network",
        "description": "Abstract boxes, lines, and connection nodes",
        "star_count": 150,
        "has_orbs": True,
        "has_mesh": False,
        "has_logistics": True,
    },
    "mesh": {
        "id": "mesh",
        "name": "Geometric Mesh",
        "description": "Modern geometric grid pattern",
        "star_count": 100,
        "has_orbs": True,
        "has_mesh": True,
        "has_logistics": False,
    },
    "minimal": {
        "id": "minimal",
        "name": "Minimal Clean",
        "description": "Ultra-clean with subtle particles only",
        "star_count": 80,
        "has_orbs": False,
        "has_mesh": False,
        "has_logistics": False,
    },
    "gradient": {
        "id": "gradient",
        "name": "Smooth Gradient",
        "description": "Clean diagonal gradient with particles",
        "star_count": 150,
        "has_orbs": True,
        "has_mesh": False,
        "has_logistics": False,
    },
}


# ============================================
# LAYOUT STYLES
# ============================================
LAYOUT_STYLES = {
    "centered": {
        "id": "centered",
        "name": "Centered Hero",
        "description": "Logo top center, text centered on page",
        "logo_position": "top_center",
        "text_align": "center",
    },
    "left": {
        "id": "left",
        "name": "Left Editorial",
        "description": "Logo top left, text left-aligned in centered block",
        "logo_position": "top_left",
        "text_align": "left",
    },
    "centered_left_text": {
        "id": "centered_left_text",
        "name": "Block Centered",
        "description": "Logo top center, left-aligned text in centered block",
        "logo_position": "top_center",
        "text_align": "left",
    },
}


def get_color_theme(theme_id: str) -> dict:
    """Get a color theme by ID."""
    return COLOR_THEMES.get(theme_id, COLOR_THEMES["black"])


def get_texture(texture_id: str) -> dict:
    """Get a background texture by ID."""
    return BACKGROUND_TEXTURES.get(texture_id, BACKGROUND_TEXTURES["stars"])


def get_layout(layout_id: str) -> dict:
    """Get a layout style by ID."""
    return LAYOUT_STYLES.get(layout_id, LAYOUT_STYLES["centered_left_text"])


def list_color_themes():
    """List all color themes."""
    return [{"id": t["id"], "name": t["name"]} for t in COLOR_THEMES.values()]


def list_textures():
    """List all background textures."""
    return [{"id": t["id"], "name": t["name"], "description": t["description"]} for t in BACKGROUND_TEXTURES.values()]


def list_layouts():
    """List all layout styles."""
    return [{"id": t["id"], "name": t["name"], "description": t["description"]} for t in LAYOUT_STYLES.values()]


# Legacy support - keep for backwards compatibility
def list_design_templates():
    """List design templates (legacy - returns color themes for backwards compat)."""
    return [
        {"id": t["id"], "name": t["name"], "description": f"Color theme: {t['name']}"}
        for t in COLOR_THEMES.values()
    ]


def get_design_template(template_id: str):
    """Get design template (legacy support)."""
    return get_color_theme(template_id)
