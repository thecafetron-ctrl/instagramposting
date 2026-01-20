"""
News Post Renderer - Creates single-image news posts like the reference style.
- Full background image
- Brand "STRUCTURE NEWS" at top
- Category with underline in middle
- Big bold headline at bottom with accent-colored keywords
"""

import os
import uuid
import random
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from pathlib import Path

# Dimensions
WIDTH = 1080
HEIGHT = 1350

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
ACCENT_CYAN = (0, 200, 255)  # Cyan/blue for highlighted words
DARK_OVERLAY = (0, 0, 0, 180)

# Font paths
ASSETS_DIR = Path(__file__).parent.parent.parent / "assets"
FONTS_DIR = ASSETS_DIR / "fonts" / "montserrat"

# Output directory
OUTPUT_DIR = Path(__file__).parent.parent.parent / "generated_images"
OUTPUT_DIR.mkdir(exist_ok=True)


class NewsPostRenderer:
    """Renderer for single-image news posts."""
    
    def __init__(self):
        self.width = WIDTH
        self.height = HEIGHT
        self._load_fonts()
    
    def _load_fonts(self):
        """Load Montserrat fonts."""
        try:
            self.font_brand = ImageFont.truetype(str(FONTS_DIR / "Montserrat-Bold.ttf"), 48)
            self.font_category = ImageFont.truetype(str(FONTS_DIR / "Montserrat-SemiBold.ttf"), 32)
            self.font_headline = ImageFont.truetype(str(FONTS_DIR / "Montserrat-ExtraBold.ttf"), 64)
            self.font_headline_small = ImageFont.truetype(str(FONTS_DIR / "Montserrat-ExtraBold.ttf"), 52)
        except Exception as e:
            print(f"Font loading error: {e}")
            # Fallback to default
            self.font_brand = ImageFont.load_default()
            self.font_category = ImageFont.load_default()
            self.font_headline = ImageFont.load_default()
            self.font_headline_small = ImageFont.load_default()
    
    def create_background(self, color_theme: str = "dark") -> Image.Image:
        """Create a news-style background."""
        img = Image.new("RGBA", (self.width, self.height), (20, 20, 30, 255))
        draw = ImageDraw.Draw(img)
        
        # Add gradient overlay effect
        for y in range(self.height):
            # Darker at bottom for text readability
            if y > self.height * 0.5:
                alpha = int(180 * ((y - self.height * 0.5) / (self.height * 0.5)))
                draw.line([(0, y), (self.width, y)], fill=(0, 0, 0, min(alpha, 220)))
        
        # Add some visual elements
        self._add_logistics_elements(img)
        
        return img
    
    def _add_logistics_elements(self, img: Image.Image):
        """Add subtle logistics-themed visual elements."""
        draw = ImageDraw.Draw(img)
        
        # Draw world map style grid lines (very subtle)
        for i in range(0, self.width, 80):
            draw.line([(i, 0), (i, self.height)], fill=(40, 40, 50, 30), width=1)
        for i in range(0, self.height, 80):
            draw.line([(0, i), (self.width, i)], fill=(40, 40, 50, 30), width=1)
        
        # Add some hub nodes
        hubs = [(200, 300), (800, 200), (500, 400), (300, 600), (700, 500)]
        for x, y in hubs:
            # Outer glow
            for r in range(20, 5, -3):
                alpha = int(20 * (1 - r/20))
                draw.ellipse([x-r, y-r, x+r, y+r], fill=(0, 150, 200, alpha))
            # Inner dot
            draw.ellipse([x-4, y-4, x+4, y+4], fill=(0, 180, 220, 60))
        
        # Draw connection lines between hubs
        for i, (x1, y1) in enumerate(hubs):
            for x2, y2 in hubs[i+1:]:
                if random.random() > 0.5:
                    draw.line([(x1, y1), (x2, y2)], fill=(0, 150, 200, 20), width=1)
    
    def add_dark_gradient_overlay(self, img: Image.Image) -> Image.Image:
        """Add dark gradient at bottom for text readability."""
        overlay = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        
        # Strong gradient at bottom half
        for y in range(self.height // 2, self.height):
            progress = (y - self.height // 2) / (self.height // 2)
            alpha = int(200 * progress)
            draw.line([(0, y), (self.width, y)], fill=(0, 0, 0, alpha))
        
        return Image.alpha_composite(img.convert("RGBA"), overlay)
    
    def render_news_post(
        self,
        headline: str,
        category: str = "SUPPLY CHAIN",
        color_theme: str = "dark",
        accent_words: list[str] = None,
    ) -> str:
        """
        Render a news post image.
        
        Args:
            headline: The news headline text
            category: Category label (e.g., "SUPPLY CHAIN", "LOGISTICS")
            color_theme: Background color theme
            accent_words: Words to highlight in accent color
        
        Returns:
            Path to the generated image
        """
        # Create background
        img = self.create_background(color_theme)
        img = self.add_dark_gradient_overlay(img)
        draw = ImageDraw.Draw(img)
        
        # Draw brand name at top left
        self._draw_brand(draw)
        
        # Draw category with underline in middle area
        self._draw_category(draw, category)
        
        # Draw headline at bottom
        self._draw_headline(draw, headline, accent_words)
        
        # Save image
        post_id = uuid.uuid4().hex[:8]
        filename = f"{post_id}_news.png"
        filepath = OUTPUT_DIR / filename
        
        img.convert("RGB").save(filepath, "PNG", quality=95)
        
        return str(filepath)
    
    def _draw_brand(self, draw: ImageDraw.Draw):
        """Draw STRUCTURE NEWS brand at top left."""
        brand_text = "STRUCTURE"
        news_text = "NEWS"
        
        x, y = 60, 60
        
        # Draw STRUCTURE
        draw.text((x, y), brand_text, font=self.font_brand, fill=WHITE)
        
        # Draw NEWS below
        draw.text((x, y + 50), news_text, font=self.font_brand, fill=WHITE)
    
    def _draw_category(self, draw: ImageDraw.Draw, category: str):
        """Draw category label with underline."""
        # Position in middle area
        y = self.height // 2 + 100
        
        # Get text size
        bbox = draw.textbbox((0, 0), category, font=self.font_category)
        text_width = bbox[2] - bbox[0]
        
        # Center horizontally
        x = (self.width - text_width) // 2
        
        # Draw category text
        draw.text((x, y), category, font=self.font_category, fill=WHITE)
        
        # Draw underline
        line_y = y + 45
        line_padding = 20
        draw.line(
            [(x - line_padding, line_y), (x + text_width + line_padding, line_y)],
            fill=WHITE,
            width=2
        )
    
    def _draw_headline(self, draw: ImageDraw.Draw, headline: str, accent_words: list[str] = None):
        """Draw headline at bottom with accent-colored keywords."""
        if accent_words is None:
            # Auto-detect words to highlight (every 3rd-4th important word)
            accent_words = self._auto_accent_words(headline)
        
        # Convert to uppercase for impact
        headline = headline.upper()
        accent_words = [w.upper() for w in accent_words]
        
        # Wrap text to fit width
        max_width = self.width - 120  # Padding on sides
        lines = self._wrap_text_for_headline(headline, max_width)
        
        # Calculate total height
        line_height = 75
        total_height = len(lines) * line_height
        
        # Start position (bottom area)
        start_y = self.height - total_height - 80
        
        # Draw each line
        for i, line in enumerate(lines):
            y = start_y + i * line_height
            self._draw_headline_line(draw, line, y, accent_words)
    
    def _wrap_text_for_headline(self, text: str, max_width: int) -> list[str]:
        """Wrap headline text to fit width."""
        words = text.split()
        lines = []
        current_line = []
        
        # Create a temporary image for measuring
        temp_img = Image.new("RGB", (1, 1))
        temp_draw = ImageDraw.Draw(temp_img)
        
        for word in words:
            test_line = " ".join(current_line + [word])
            bbox = temp_draw.textbbox((0, 0), test_line, font=self.font_headline)
            width = bbox[2] - bbox[0]
            
            if width <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]
        
        if current_line:
            lines.append(" ".join(current_line))
        
        return lines
    
    def _draw_headline_line(self, draw: ImageDraw.Draw, line: str, y: int, accent_words: list[str]):
        """Draw a single headline line with accent colors."""
        words = line.split()
        
        # Calculate total line width first
        temp_img = Image.new("RGB", (1, 1))
        temp_draw = ImageDraw.Draw(temp_img)
        
        total_width = 0
        word_widths = []
        space_width = temp_draw.textbbox((0, 0), " ", font=self.font_headline)[2]
        
        for word in words:
            bbox = temp_draw.textbbox((0, 0), word, font=self.font_headline)
            word_width = bbox[2] - bbox[0]
            word_widths.append(word_width)
            total_width += word_width
        
        total_width += space_width * (len(words) - 1)
        
        # Start position (centered)
        x = (self.width - total_width) // 2
        
        # Draw each word
        for i, word in enumerate(words):
            # Check if word should be accented
            is_accent = any(accent.upper() in word.upper() for accent in accent_words)
            color = ACCENT_CYAN if is_accent else WHITE
            
            # Draw shadow first
            shadow_offset = 3
            draw.text((x + shadow_offset, y + shadow_offset), word, font=self.font_headline, fill=(0, 0, 0, 150))
            
            # Draw word
            draw.text((x, y), word, font=self.font_headline, fill=color)
            
            x += word_widths[i] + space_width
    
    def _auto_accent_words(self, headline: str) -> list[str]:
        """Automatically select words to highlight."""
        words = headline.split()
        
        # Keywords that should be highlighted
        important_keywords = [
            "rising", "falling", "breaking", "urgent", "major", "crisis",
            "disruption", "shortage", "surge", "record", "new", "first",
            "ai", "automation", "technology", "innovation", "future",
            "impact", "change", "transform", "revolution", "growth",
            "decline", "increase", "decrease", "billion", "million",
            "global", "worldwide", "industry", "market", "supply", "chain"
        ]
        
        accent = []
        
        # First, check for important keywords
        for word in words:
            clean_word = word.lower().strip(".,!?\"'")
            if clean_word in important_keywords:
                accent.append(word)
        
        # If no keywords found, highlight every 3rd-4th word
        if not accent and len(words) > 4:
            indices = [2, 5, 8, 11]  # Positions to highlight
            for idx in indices:
                if idx < len(words):
                    accent.append(words[idx])
        
        return accent[:4]  # Max 4 highlighted words


def render_news_post(
    headline: str,
    category: str = "SUPPLY CHAIN",
    accent_words: list[str] = None,
) -> str:
    """
    Convenience function to render a news post.
    
    Returns:
        Path to the generated image
    """
    renderer = NewsPostRenderer()
    return renderer.render_news_post(
        headline=headline,
        category=category,
        accent_words=accent_words,
    )


# Test
if __name__ == "__main__":
    path = render_news_post(
        headline="Global Supply Chain Disruptions Rising Amid Port Congestion Crisis",
        category="SUPPLY CHAIN",
        accent_words=["RISING", "CRISIS"]
    )
    print(f"Generated: {path}")
