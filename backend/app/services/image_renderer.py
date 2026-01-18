"""
Professional Image Rendering Engine for Instagram Carousel Posts.

Modular system with:
- Color theme selection
- Background texture selection  
- Layout style selection
- MASSIVE headlines for impact
"""

import os
import uuid
import random
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from app.config import get_settings
from app.design_templates import get_color_theme, get_texture, get_layout

settings = get_settings()

# Image dimensions
WIDTH = 1080
HEIGHT = 1350

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

# Typography - MASSIVE headlines, SAME SIZE for all body text
HEADLINE_SIZE = 96  # MASSIVE headlines for slide 1
BODY_SIZE = 34  # ALL body text same size
CTA_SIZE = 48  # BIGGER for last slide only
CTA_BIG_SIZE = 56  # "STRUCTURE" on last slide
LINE_HEIGHT_HEADLINE = 110
LINE_HEIGHT_BODY = 50
LINE_HEIGHT_CTA = 65
PARAGRAPH_SPACING = 45  # Space between paragraphs/sections
BULLET_LINE_HEIGHT = 46  # Tighter line height for bullets
MAX_TEXT_WIDTH = 900


class TextRenderer:
    """Handles text rendering with shadows and effects."""
    
    def __init__(self, assets_path: str):
        self.assets_path = Path(assets_path)
        self.fonts = self._load_fonts()
        
    def _load_fonts(self) -> dict:
        """Load Montserrat font family."""
        font_path = self.assets_path / "fonts" / "Montserrat"
        fonts = {}
        
        font_files = {
            "regular": "Montserrat-Regular.ttf",
            "medium": "Montserrat-Medium.ttf", 
            "semibold": "Montserrat-SemiBold.ttf",
            "bold": "Montserrat-Bold.ttf",
            "extrabold": "Montserrat-ExtraBold.ttf",
            "black": "Montserrat-Black.ttf",
        }
        
        for weight, filename in font_files.items():
            path = font_path / filename
            if path.exists():
                fonts[weight] = str(path)
            else:
                fonts[weight] = str(font_path / "Montserrat-Bold.ttf")
                
        return fonts
    
    def get_font(self, weight: str, size: int) -> ImageFont.FreeTypeFont:
        """Get font with specified weight and size."""
        font_path = self.fonts.get(weight, self.fonts["bold"])
        return ImageFont.truetype(font_path, size)
    
    def draw_text_with_shadow(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        position: tuple,
        font: ImageFont.FreeTypeFont,
        fill: tuple = WHITE,
        shadow_strength: int = 4,
    ):
        """Draw text with drop shadow."""
        x, y = position
        
        # Draw shadow layers
        for i in range(3):
            offset = shadow_strength + i
            draw.text((x + offset, y + offset), text, font=font, fill=(0, 0, 0))
        
        # Draw main text
        draw.text(position, text, font=font, fill=fill)


class BackgroundGenerator:
    """Generates backgrounds based on texture and color settings."""
    
    @staticmethod
    def create_base(width: int, height: int, color_theme: dict) -> Image.Image:
        """Create base image with primary color."""
        return Image.new("RGBA", (width, height), (*color_theme["primary"], 255))
    
    @staticmethod
    def add_gradient(img: Image.Image, color_theme: dict):
        """Add diagonal gradient."""
        width, height = img.size
        primary = color_theme["primary"]
        secondary = color_theme["secondary"]
        
        for y in range(height):
            for x in range(width):
                factor = (x + y) / (width + height)
                r = int(primary[0] + (secondary[0] - primary[0]) * factor)
                g = int(primary[1] + (secondary[1] - primary[1]) * factor)
                b = int(primary[2] + (secondary[2] - primary[2]) * factor)
                img.putpixel((x, y), (r, g, b, 255))
    
    @staticmethod
    def add_stars(img: Image.Image, count: int, seed: int = 42):
        """Add visible star particles with varying sizes and brightness."""
        width, height = img.size
        draw = ImageDraw.Draw(img)
        random.seed(seed)
        
        # More visible stars
        for _ in range(count):
            x = random.randint(0, width - 1)
            y = random.randint(0, height - 1)
            brightness = random.randint(80, 200)  # More visible
            size = random.choice([1, 1, 1, 2, 2, 3])  # Varying sizes
            
            color = (brightness, brightness, brightness, 255)
            if size == 1:
                img.putpixel((x, y), color)
            else:
                draw.ellipse([(x-size, y-size), (x+size, y+size)], fill=color)
            
            # Some stars have a glow
            if random.random() > 0.85:
                glow_size = size + 4
                for r in range(glow_size, 0, -1):
                    alpha = int(30 * (glow_size - r) / glow_size)
                    draw.ellipse([(x-r, y-r), (x+r, y+r)], fill=(brightness, brightness, brightness, alpha))
    
    @staticmethod
    def add_orbs(img: Image.Image, color_theme: dict, seed: int = 42):
        """Add subtle ambient glowing orbs - very understated."""
        width, height = img.size
        orb_colors = color_theme.get("orb_colors", [(60, 50, 100)])
        
        # Only 2 subtle orbs max
        for i, orb_color in enumerate(orb_colors[:2]):
            random.seed(seed + i * 100)
            ox = random.randint(200, width - 200)
            oy = random.randint(200, height - 200)
            orb_size = random.randint(180, 280)  # Larger but more subtle
            
            for dx in range(-orb_size, orb_size + 1, 2):  # Skip pixels for performance
                for dy in range(-orb_size, orb_size + 1, 2):
                    dist = math.sqrt(dx**2 + dy**2)
                    if dist < orb_size and 0 <= ox + dx < width and 0 <= oy + dy < height:
                        # Very subtle glow
                        alpha = int(12 * (1 - dist / orb_size) ** 3)  # Cubic falloff for softer edge
                        px = img.getpixel((ox + dx, oy + dy))
                        new_r = min(255, px[0] + int(orb_color[0] * alpha / 150))
                        new_g = min(255, px[1] + int(orb_color[1] * alpha / 150))
                        new_b = min(255, px[2] + int(orb_color[2] * alpha / 150))
                        img.putpixel((ox + dx, oy + dy), (new_r, new_g, new_b, 255))
                        # Fill skipped pixel too
                        if ox + dx + 1 < width:
                            img.putpixel((ox + dx + 1, oy + dy), (new_r, new_g, new_b, 255))
    
    @staticmethod
    def add_mesh(img: Image.Image, color_theme: dict, seed: int = 42):
        """Add visible hexagonal mesh pattern."""
        draw = ImageDraw.Draw(img)
        accent = color_theme["accent"]
        width, height = img.size
        
        random.seed(seed)
        
        # Hexagonal grid - MORE VISIBLE
        hex_size = 55
        for row in range(-2, height // hex_size + 3):
            for col in range(-2, width // hex_size + 3):
                offset = (hex_size // 2) if row % 2 else 0
                cx = col * hex_size + offset
                cy = row * int(hex_size * 0.866)
                
                points = []
                for i in range(6):
                    angle = math.pi / 6 + i * math.pi / 3
                    px = cx + hex_size // 2 * math.cos(angle)
                    py = cy + hex_size // 2 * math.sin(angle)
                    points.append((px, py))
                
                # Draw more hexagons with varying visibility
                if random.random() > 0.5:
                    alpha = random.randint(25, 45)  # MORE VISIBLE
                    for i in range(6):
                        draw.line([points[i], points[(i+1) % 6]], fill=(*accent, alpha), width=1)
        
        # Add glowing connection nodes - MORE OF THEM
        for _ in range(25):
            x = random.randint(80, width - 80)
            y = random.randint(80, height - 80)
            # Glowing dot
            for r in range(12, 3, -1):
                alpha = int(15 * (12 - r) / 9)
                draw.ellipse([(x-r, y-r), (x+r, y+r)], fill=(*accent, alpha))
            draw.ellipse([(x-3, y-3), (x+3, y+3)], fill=(*accent, 50))
    
    @staticmethod
    def add_logistics(img: Image.Image, color_theme: dict, seed: int = 42):
        """Add visible logistics network overlay - world map style with route connections."""
        draw = ImageDraw.Draw(img)
        accent = color_theme["accent"]
        width, height = img.size
        
        random.seed(seed)
        
        # Create a world map / globe outline effect - MORE VISIBLE
        cx, cy = width // 2, height // 2
        
        # Draw longitude lines (curved vertical lines) - MORE VISIBLE
        for i in range(-5, 6):
            curve_offset = i * 70
            points = []
            for y in range(0, height, 15):
                curve = int(40 * math.sin(y / height * math.pi))
                x = cx + curve_offset + curve
                points.append((x, y))
            if len(points) >= 2:
                for j in range(len(points) - 1):
                    draw.line([points[j], points[j+1]], fill=(*accent, 25), width=1)
        
        # Draw latitude lines (horizontal arcs) - MORE VISIBLE
        for i in range(-4, 5):
            y_pos = cy + i * 100
            points = []
            for x in range(50, width - 50, 12):
                arc = int(25 * math.sin((x - 50) / (width - 100) * math.pi))
                points.append((x, y_pos + arc))
            if len(points) >= 2:
                for j in range(len(points) - 1):
                    draw.line([points[j], points[j+1]], fill=(*accent, 18), width=1)
        
        # Add hub/node points (major logistics hubs)
        hubs = [
            (width * 0.15, height * 0.25),   # North America
            (width * 0.5, height * 0.28),    # Europe
            (width * 0.78, height * 0.32),   # Asia
            (width * 0.25, height * 0.62),   # South America
            (width * 0.52, height * 0.68),   # Africa
            (width * 0.82, height * 0.62),   # Australia
            (width * 0.35, height * 0.45),   # Mid Atlantic
            (width * 0.68, height * 0.5),    # Indian Ocean
        ]
        
        # Draw connections between hubs (curved flight paths) - MORE VISIBLE
        for i, (x1, y1) in enumerate(hubs):
            for j, (x2, y2) in enumerate(hubs):
                if i < j and random.random() > 0.3:
                    mid_x = (x1 + x2) / 2
                    mid_y = (y1 + y2) / 2 - random.randint(40, 80)
                    
                    steps = 40
                    prev_point = None
                    for t in range(steps + 1):
                        tt = t / steps
                        px = (1-tt)**2 * x1 + 2*(1-tt)*tt * mid_x + tt**2 * x2
                        py = (1-tt)**2 * y1 + 2*(1-tt)*tt * mid_y + tt**2 * y2
                        if prev_point:
                            # Solid lines, more visible
                            draw.line([prev_point, (px, py)], fill=(*accent, 35), width=1)
                        prev_point = (px, py)
        
        # Draw hub nodes - BIGGER and BRIGHTER
        for x, y in hubs:
            # Outer glow
            for r in range(18, 4, -2):
                alpha = int(20 * (18 - r) / 14)
                draw.ellipse([(x-r, y-r), (x+r, y+r)], fill=(*accent, alpha))
            # Center dot - brighter
            draw.ellipse([(x-5, y-5), (x+5, y+5)], fill=(*accent, 80))
            # Small inner bright dot
            draw.ellipse([(x-2, y-2), (x+2, y+2)], fill=(255, 255, 255, 100))
    
    @staticmethod
    def add_marble(img: Image.Image, color_theme: dict, seed: int = 42):
        """Add visible marble texture with flowing veins and cracks."""
        draw = ImageDraw.Draw(img)
        accent = color_theme["accent"]
        width, height = img.size
        
        random.seed(seed)
        
        # Draw main marble veins - more visible
        for vein_num in range(10):
            # Start from different edges
            if vein_num % 4 == 0:
                x = random.randint(0, width // 3)
                y = random.randint(0, height // 4)
            elif vein_num % 4 == 1:
                x = random.randint(width * 2 // 3, width)
                y = random.randint(0, height // 4)
            elif vein_num % 4 == 2:
                x = 0
                y = random.randint(height // 4, height * 3 // 4)
            else:
                x = width
                y = random.randint(height // 4, height * 3 // 4)
            
            # Flow with curves
            points = [(x, y)]
            direction = random.uniform(-0.4, 0.4)
            
            steps = random.randint(15, 25)
            for _ in range(steps):
                direction += random.uniform(-0.2, 0.2)
                direction = max(-0.6, min(0.6, direction))
                
                x += int(50 * direction) + random.randint(-20, 20)
                y += random.randint(30, 70)
                x = max(0, min(width, x))
                points.append((x, y))
            
            # Draw vein with varying thickness - MORE VISIBLE
            if len(points) >= 2:
                for i in range(len(points) - 1):
                    thickness = random.randint(1, 3)
                    alpha = random.randint(30, 60)  # More visible
                    draw.line([points[i], points[i+1]], fill=(*accent, alpha), width=thickness)
                    
                    # Add branches more often
                    if random.random() > 0.6:
                        bx = points[i][0] + random.randint(-80, 80)
                        by = points[i][1] + random.randint(30, 70)
                        draw.line([points[i], (bx, by)], fill=(*accent, 25), width=1)
                        
                        # Sub-branches
                        if random.random() > 0.5:
                            bx2 = bx + random.randint(-40, 40)
                            by2 = by + random.randint(20, 40)
                            draw.line([(bx, by), (bx2, by2)], fill=(*accent, 15), width=1)
    
    @staticmethod
    def add_vignette(img: Image.Image, strength: float = 0.6):
        """Add vignette effect (darker edges)."""
        width, height = img.size
        cx, cy = width // 2, height // 2
        max_dist = math.sqrt(cx**2 + cy**2)
        
        for y in range(height):
            for x in range(width):
                dist = math.sqrt((x - cx)**2 + (y - cy)**2)
                factor = dist / max_dist
                # Apply vignette curve
                darken = int(255 * strength * (factor ** 1.5))
                px = img.getpixel((x, y))
                new_r = max(0, px[0] - darken)
                new_g = max(0, px[1] - darken)
                new_b = max(0, px[2] - darken)
                img.putpixel((x, y), (new_r, new_g, new_b, px[3] if len(px) > 3 else 255))
    
    @staticmethod
    def add_center_glow(img: Image.Image, color_theme: dict, intensity: float = 0.3):
        """Add a soft glow in the center of the image."""
        width, height = img.size
        cx, cy = width // 2, height // 2
        max_radius = min(width, height) * 0.6
        
        accent = color_theme.get("accent", (100, 100, 150))
        
        for y in range(height):
            for x in range(width):
                dist = math.sqrt((x - cx)**2 + (y - cy)**2)
                if dist < max_radius:
                    factor = 1 - (dist / max_radius)
                    glow = int(40 * intensity * (factor ** 2))
                    px = img.getpixel((x, y))
                    new_r = min(255, px[0] + int(accent[0] * glow / 255))
                    new_g = min(255, px[1] + int(accent[1] * glow / 255))
                    new_b = min(255, px[2] + int(accent[2] * glow / 255))
                    img.putpixel((x, y), (new_r, new_g, new_b, px[3] if len(px) > 3 else 255))
    
    @classmethod
    def create_background(cls, width: int, height: int, color_theme: dict, texture: dict, seed: int = 42) -> Image.Image:
        """Create complete background with color theme and texture."""
        img = cls.create_base(width, height, color_theme)
        
        # Add gradient for all textures
        cls.add_gradient(img, color_theme)
        
        # Add texture-specific elements
        texture_id = texture["id"]
        
        if texture_id == "marble":
            cls.add_marble(img, color_theme, seed)
        
        if texture.get("has_mesh"):
            cls.add_mesh(img, color_theme, seed)
        
        if texture.get("has_logistics"):
            cls.add_logistics(img, color_theme, seed)
        
        # Add stars
        cls.add_stars(img, texture.get("star_count", 200), seed)
        
        # Add orbs if enabled
        if texture.get("has_orbs", True):
            cls.add_orbs(img, color_theme, seed)
        
        # Add center glow (subtle)
        cls.add_center_glow(img, color_theme, intensity=0.25)
        
        # Add vignette effect
        cls.add_vignette(img, strength=0.5)
        
        return img


class CarouselRenderer:
    """Main renderer for carousel slides."""
    
    def __init__(self, color_id: str = "black", texture_id: str = "stars", layout_id: str = "centered_left_text"):
        self.assets_path = Path(settings.logo_image_path).parent
        self.text_renderer = TextRenderer(str(self.assets_path))
        self.logo = self._load_logo()
        
        # Load settings
        self.color_theme = get_color_theme(color_id)
        self.texture = get_texture(texture_id)
        self.layout = get_layout(layout_id)
        
        # Create background
        self.background = BackgroundGenerator.create_background(
            WIDTH, HEIGHT, self.color_theme, self.texture
        )
        
        # Load fonts - ALL SAME SIZE except headline and last slide CTA
        self.font_headline = self.text_renderer.get_font("extrabold", HEADLINE_SIZE)
        self.font_body = self.text_renderer.get_font("regular", BODY_SIZE)
        self.font_body_bold = self.text_renderer.get_font("bold", BODY_SIZE)  # Bold same size
        # CTA fonts - BIGGER for last slide only
        self.font_cta = self.text_renderer.get_font("semibold", CTA_SIZE)
        self.font_cta_extrabold = self.text_renderer.get_font("extrabold", CTA_BIG_SIZE)
        
    def _load_logo(self) -> Image.Image:
        """Load the official STRUCTURE logo."""
        logo_path = self.assets_path / "logo_white.png"
        if logo_path.exists():
            logo = Image.open(logo_path).convert("RGBA")
            max_width = 200
            ratio = max_width / logo.width
            new_height = int(logo.height * ratio)
            return logo.resize((max_width, new_height), Image.Resampling.LANCZOS)
        return None
    
    def _wrap_text(self, text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.ImageDraw) -> list:
        """Wrap text to fit within max_width."""
        words = text.split()
        lines = []
        current_line = []
        
        for word in words:
            test_line = ' '.join(current_line + [word])
            bbox = draw.textbbox((0, 0), test_line, font=font)
            width = bbox[2] - bbox[0]
            
            if width <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return lines
    
    def _get_text_x(self, text: str, font: ImageFont.FreeTypeFont, draw: ImageDraw.ImageDraw) -> int:
        """Get x position based on layout alignment."""
        left_margin = (WIDTH - MAX_TEXT_WIDTH) // 2
        
        if self.layout["text_align"] == "center":
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            return (WIDTH - text_width) // 2
        else:
            return left_margin
    
    def render_slide_1(self, headline: str, subheadline: str) -> Image.Image:
        """Render slide 1 - MASSIVE headline."""
        img = self.background.copy()
        draw = ImageDraw.Draw(img)
        
        # Add logo
        if self.logo:
            if self.layout["logo_position"] == "top_center":
                logo_x = (WIDTH - self.logo.width) // 2
            else:
                logo_x = 80
            logo_y = 60
            img.paste(self.logo, (logo_x, logo_y), self.logo)
        
        # Wrap headline
        headline_lines = self._wrap_text(headline.upper(), self.font_headline, MAX_TEXT_WIDTH, draw)
        sub_lines = self._wrap_text(subheadline, self.font_body, MAX_TEXT_WIDTH, draw)
        
        # Calculate heights
        headline_height = len(headline_lines) * LINE_HEIGHT_HEADLINE
        sub_height = len(sub_lines) * LINE_HEIGHT_BODY
        total_height = headline_height + PARAGRAPH_SPACING + sub_height
        
        # Center vertically
        start_y = max(220, (HEIGHT - total_height) // 2)
        
        current_y = start_y
        
        # Draw MASSIVE headline
        for line in headline_lines:
            x = self._get_text_x(line, self.font_headline, draw)
            self.text_renderer.draw_text_with_shadow(draw, line, (x, current_y), self.font_headline, shadow_strength=5)
            current_y += LINE_HEIGHT_HEADLINE
        
        current_y += PARAGRAPH_SPACING
        
        # Draw subheadline
        for line in sub_lines:
            x = self._get_text_x(line, self.font_body, draw)
            self.text_renderer.draw_text_with_shadow(draw, line, (x, current_y), self.font_body)
            current_y += LINE_HEIGHT_BODY
        
        return img
    
    def _parse_content(self, content: str) -> list:
        """Parse content into structured blocks with proper type identification."""
        blocks = []
        prev_was_empty = False
        
        for line in content.strip().split('\n'):
            line = line.strip()
            
            # Track empty lines for paragraph spacing
            if not line:
                prev_was_empty = True
                continue
                
            if line.startswith('[LOGO]'):
                continue
            
            is_emphasis = line.startswith('**') and line.endswith('**')
            is_header = ('how ai' in line.lower() or 'real outcome' in line.lower() or 
                        'the problem' in line.lower() or 'why this matters' in line.lower() or
                        'key insight' in line.lower())
            is_bullet = line.startswith('•') or line.startswith('-')
            is_numbered = len(line) >= 2 and line[0].isdigit() and line[1] == '.'
            
            clean_line = line.replace('**', '')
            
            # Determine block type
            if is_header or (is_emphasis and not is_bullet):
                block_type = 'header'
            elif is_bullet:
                block_type = 'bullet'
            elif is_numbered:
                block_type = 'numbered'
            else:
                block_type = 'paragraph'
            
            blocks.append({
                'text': clean_line,
                'type': block_type,
                'is_emphasis': is_emphasis or is_header,
                'is_bold': is_bullet or is_numbered or is_emphasis or is_header,
                'add_space_before': prev_was_empty and len(blocks) > 0,
            })
            
            prev_was_empty = False
        
        return blocks
    
    def render_slide_2(self, content: str) -> Image.Image:
        """Render slide 2 - Problem description with LEFT alignment, same size text, bold for emphasis."""
        img = self.background.copy()
        draw = ImageDraw.Draw(img)
        
        blocks = self._parse_content(content)
        left_margin = (WIDTH - MAX_TEXT_WIDTH) // 2
        
        # Calculate total height - ALL SAME SIZE
        total_height = 0
        prev_was_bullet = False
        
        for block in blocks:
            is_bullet = block['type'] == 'bullet'
            line_height = BULLET_LINE_HEIGHT if is_bullet else LINE_HEIGHT_BODY
            font = self.font_body_bold if block['is_bold'] else self.font_body
            
            wrapped = self._wrap_text(block['text'], font, MAX_TEXT_WIDTH, draw)
            total_height += len(wrapped) * line_height
            
            # Add spacing between sections
            if is_bullet and not prev_was_bullet:
                total_height += PARAGRAPH_SPACING
            elif not is_bullet and prev_was_bullet:
                total_height += PARAGRAPH_SPACING
            elif block['add_space_before'] and not is_bullet:
                total_height += PARAGRAPH_SPACING
            
            prev_was_bullet = is_bullet
        
        # Center vertically
        start_y = max(80, (HEIGHT - total_height) // 2)
        current_y = start_y
        
        accent_band = self.color_theme["accent_band"]
        prev_was_bullet = False
        
        for block in blocks:
            is_bullet = block['type'] == 'bullet'
            
            # Spacing between sections
            if is_bullet and not prev_was_bullet:
                current_y += PARAGRAPH_SPACING
            elif not is_bullet and prev_was_bullet:
                current_y += PARAGRAPH_SPACING
            elif block['add_space_before'] and not is_bullet:
                current_y += PARAGRAPH_SPACING
            
            # ALL SAME SIZE - just bold or regular
            line_height = BULLET_LINE_HEIGHT if is_bullet else LINE_HEIGHT_BODY
            font = self.font_body_bold if block['is_bold'] else self.font_body
            
            wrapped = self._wrap_text(block['text'], font, MAX_TEXT_WIDTH, draw)
            
            for line in wrapped:
                if current_y > HEIGHT - 80:
                    break
                
                # Accent band only for explicit headers like "How AI fixes this"
                if block['type'] == 'header':
                    draw.rectangle(
                        [left_margin - 15, current_y - 5, left_margin + MAX_TEXT_WIDTH + 15, current_y + LINE_HEIGHT_BODY - 15],
                        fill=accent_band
                    )
                
                # LEFT ALIGNED
                x = left_margin
                self.text_renderer.draw_text_with_shadow(draw, line, (x, current_y), font)
                current_y += line_height
            
            prev_was_bullet = is_bullet
        
        return img
    
    def render_slide_3(self, content: str) -> Image.Image:
        """Render slide 3 - Solution slide with LEFT alignment, same size text, bold for emphasis, logo at bottom."""
        img = self.background.copy()
        draw = ImageDraw.Draw(img)
        
        blocks = self._parse_content(content)
        left_margin = (WIDTH - MAX_TEXT_WIDTH) // 2
        
        # Reserve space for logo at bottom
        logo_area_height = 120 if self.logo else 0
        max_y = HEIGHT - logo_area_height - 60
        
        # Calculate total height - ALL SAME SIZE
        total_height = 0
        prev_was_bullet = False
        
        for block in blocks:
            is_bullet = block['type'] == 'bullet'
            line_height = BULLET_LINE_HEIGHT if is_bullet else LINE_HEIGHT_BODY
            font = self.font_body_bold if block['is_bold'] else self.font_body
            
            wrapped = self._wrap_text(block['text'], font, MAX_TEXT_WIDTH, draw)
            total_height += len(wrapped) * line_height
            
            # Add spacing between sections
            if is_bullet and not prev_was_bullet:
                total_height += PARAGRAPH_SPACING
            elif not is_bullet and prev_was_bullet:
                total_height += PARAGRAPH_SPACING
            elif block['add_space_before'] and not is_bullet:
                total_height += PARAGRAPH_SPACING
            
            prev_was_bullet = is_bullet
        
        # Center content vertically (accounting for logo area)
        available_height = max_y - 80
        start_y = max(80, 80 + (available_height - total_height) // 2)
        current_y = start_y
        
        accent_band = self.color_theme["accent_band"]
        prev_was_bullet = False
        
        for block in blocks:
            if current_y > max_y:
                break
            
            is_bullet = block['type'] == 'bullet'
            
            # Spacing between sections
            if is_bullet and not prev_was_bullet:
                current_y += PARAGRAPH_SPACING
            elif not is_bullet and prev_was_bullet:
                current_y += PARAGRAPH_SPACING
            elif block['add_space_before'] and not is_bullet:
                current_y += PARAGRAPH_SPACING
            
            # ALL SAME SIZE - just bold or regular
            line_height = BULLET_LINE_HEIGHT if is_bullet else LINE_HEIGHT_BODY
            font = self.font_body_bold if block['is_bold'] else self.font_body
            
            wrapped = self._wrap_text(block['text'], font, MAX_TEXT_WIDTH, draw)
            
            for line in wrapped:
                if current_y > max_y:
                    break
                
                # Accent band only for explicit headers
                if block['type'] == 'header':
                    draw.rectangle(
                        [left_margin - 15, current_y - 5, left_margin + MAX_TEXT_WIDTH + 15, current_y + LINE_HEIGHT_BODY - 15],
                        fill=accent_band
                    )
                
                # ALWAYS LEFT ALIGNED for middle slides
                x = left_margin
                self.text_renderer.draw_text_with_shadow(draw, line, (x, current_y), font)
                current_y += line_height
            
            prev_was_bullet = is_bullet
        
        # Add logo at bottom
        if self.logo:
            logo_small = self.logo.resize(
                (int(self.logo.width * 0.6), int(self.logo.height * 0.6)),
                Image.Resampling.LANCZOS
            )
            logo_x = (WIDTH - logo_small.width) // 2
            logo_y = HEIGHT - logo_small.height - 50
            img.paste(logo_small, (logo_x, logo_y), logo_small)
        
        return img
    
    def render_slide_4(self, content: str) -> Image.Image:
        """Render slide 4 - CTA with BIGGER text and super bold underlined STRUCTURE."""
        img = self.background.copy()
        draw = ImageDraw.Draw(img)
        
        lines = [l.strip() for l in content.split('\n') if l.strip() and not l.startswith('[LOGO]')]
        left_margin = (WIDTH - MAX_TEXT_WIDTH) // 2
        
        underline_color = self.color_theme["underline"]
        
        # Find which line has "Comment" and "STRUCTURE"
        cta_line = None
        other_lines = []
        for line in lines:
            if 'Comment' in line and 'STRUCTURE' in line:
                cta_line = line
            else:
                other_lines.append(line)
        
        # Calculate heights
        # CTA line (Comment "STRUCTURE") gets special treatment
        cta_height = 0
        if cta_line:
            # Split into parts: before STRUCTURE, STRUCTURE, after
            cta_height = LINE_HEIGHT_CTA + 30  # Extra space for the CTA line
        
        # Other lines use CTA font
        wrapped_others = []
        for line in other_lines:
            wrapped = self._wrap_text(line, self.font_cta, MAX_TEXT_WIDTH, draw)
            wrapped_others.extend(wrapped)
        
        other_height = len(wrapped_others) * LINE_HEIGHT_CTA
        total_height = cta_height + other_height + PARAGRAPH_SPACING
        
        # Reserve space for logo
        logo_area = 130 if self.logo else 0
        available_height = HEIGHT - logo_area
        start_y = max(100, (available_height - total_height) // 2)
        current_y = start_y
        
        # Draw CTA line first (Comment "STRUCTURE" - with STRUCTURE super bold and underlined)
        if cta_line:
            # Find STRUCTURE in the line
            struct_idx = cta_line.find("STRUCTURE")
            if struct_idx >= 0:
                before = cta_line[:struct_idx]
                after = cta_line[struct_idx + 9:]  # After "STRUCTURE"
                
                # Calculate positions
                before_bbox = draw.textbbox((0, 0), before, font=self.font_cta)
                before_width = before_bbox[2] - before_bbox[0]
                
                struct_bbox = draw.textbbox((0, 0), "STRUCTURE", font=self.font_cta_extrabold)
                struct_width = struct_bbox[2] - struct_bbox[0]
                
                total_width = before_width + struct_width
                if after:
                    after_bbox = draw.textbbox((0, 0), after, font=self.font_cta)
                    total_width += after_bbox[2] - after_bbox[0]
                
                # Center the whole line
                x = (WIDTH - total_width) // 2 if self.layout["text_align"] == "center" else left_margin
                
                # Draw "Comment " part
                self.text_renderer.draw_text_with_shadow(draw, before, (x, current_y), self.font_cta)
                
                # Draw "STRUCTURE" in extrabold
                struct_x = x + before_width
                self.text_renderer.draw_text_with_shadow(draw, "STRUCTURE", (struct_x, current_y), self.font_cta_extrabold)
                
                # Draw thick underline under STRUCTURE
                underline_y = current_y + LINE_HEIGHT_CTA - 5
                draw.line([(struct_x, underline_y), (struct_x + struct_width, underline_y)], fill=underline_color, width=6)
                
                # Draw remaining text after STRUCTURE
                if after:
                    after_x = struct_x + struct_width
                    self.text_renderer.draw_text_with_shadow(draw, after, (after_x, current_y), self.font_cta)
            else:
                # No STRUCTURE found, draw normally
                x = self._get_text_x(cta_line, self.font_cta, draw) if self.layout["text_align"] == "center" else left_margin
                self.text_renderer.draw_text_with_shadow(draw, cta_line, (x, current_y), self.font_cta)
            
            current_y += LINE_HEIGHT_CTA + 30
        
        # Add paragraph spacing before other lines
        current_y += PARAGRAPH_SPACING
        
        # Draw other CTA lines (TO GET THE 90-DAY... etc)
        for line in wrapped_others:
            x = self._get_text_x(line, self.font_cta, draw) if self.layout["text_align"] == "center" else left_margin
            self.text_renderer.draw_text_with_shadow(draw, line, (x, current_y), self.font_cta)
            current_y += LINE_HEIGHT_CTA
        
        # Add logo at bottom
        if self.logo:
            logo_small = self.logo.resize(
                (int(self.logo.width * 0.6), int(self.logo.height * 0.6)),
                Image.Resampling.LANCZOS
            )
            logo_x = (WIDTH - logo_small.width) // 2
            logo_y = HEIGHT - logo_small.height - 50
            img.paste(logo_small, (logo_x, logo_y), logo_small)
        
        return img
    
    def render_all_slides(self, slide_texts: list) -> list:
        """Render all slides and save to files.
        
        Args:
            slide_texts: List of slide text content (variable length 4-10)
            
        Returns:
            List of file paths for rendered images
        """
        slide_count = len(slide_texts)
        slides = []
        
        for i, text in enumerate(slide_texts):
            slide_num = i + 1
            
            if slide_num == 1:
                # First slide - hook with headline
                lines = [l.strip() for l in text.split('\n') if l.strip() and not l.startswith('[LOGO]')]
                headline = lines[0] if lines else "YOUR HEADLINE HERE"
                subheadline = lines[1] if len(lines) > 1 else ""
                slides.append(self.render_slide_1(headline, subheadline))
            elif slide_num == slide_count:
                # Last slide - CTA
                slides.append(self.render_slide_4(text))
            elif slide_num == slide_count - 1:
                # Second to last - usually outcomes with logo
                slides.append(self.render_slide_3(text))
            else:
                # Middle slides - content
                slides.append(self.render_slide_2(text))
        
        output_dir = Path("generated_images")
        output_dir.mkdir(exist_ok=True)
        
        post_id = uuid.uuid4().hex[:8]
        paths = []
        
        for i, slide in enumerate(slides, 1):
            if slide.mode == "RGBA":
                rgb_slide = Image.new("RGB", slide.size, (0, 0, 0))
                rgb_slide.paste(slide, mask=slide.split()[-1] if len(slide.split()) == 4 else None)
                slide = rgb_slide
            
            filename = f"{post_id}_slide_{i}.png"
            filepath = output_dir / filename
            slide.save(filepath, "PNG", quality=95)
            paths.append(f"generated_images/{filename}")
        
        return paths


def get_renderer(color_id: str = "black", texture_id: str = "stars", layout_id: str = "centered_left_text") -> CarouselRenderer:
    """Get renderer instance with specified settings."""
    return CarouselRenderer(color_id, texture_id, layout_id)
