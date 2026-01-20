"""
News Post Renderer - Creates single-image news posts.
- Square format (1080x1080)
- Top 58%: Unsplash image related to the news
- Bottom 42%: MASSIVE ALL CAPS headline
- Logo + STRUCTURE branding top left only
"""

import os
import uuid
import httpx
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from pathlib import Path

from app.config import get_settings

settings = get_settings()

# Square dimensions
WIDTH = 1080
HEIGHT = 1080

# Layout - ORIGINAL proportions
IMAGE_HEIGHT_RATIO = 0.58  # 58% for image
TEXT_HEIGHT_RATIO = 0.42   # 42% for text

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
ACCENT_CYAN = (0, 200, 255)
DARK_BG = (12, 12, 18)

# Font paths
ASSETS_DIR = Path(__file__).parent.parent.parent / "assets"
FONTS_DIR = ASSETS_DIR / "fonts" / "Montserrat"

# Output directory
OUTPUT_DIR = Path(__file__).parent.parent.parent / "generated_images"
OUTPUT_DIR.mkdir(exist_ok=True)


async def fetch_unsplash_image(query: str) -> Image.Image | None:
    """Fetch a relevant image from Unsplash API."""
    access_key = settings.unsplash_access_key
    
    if not access_key:
        print("No Unsplash access key configured")
        return None
    
    keywords_map = {
        "supply chain": "warehouse logistics shipping",
        "logistics": "warehouse shipping cargo",
        "shipping": "cargo ship container port",
        "freight": "freight truck cargo",
        "warehouse": "warehouse storage",
        "port": "shipping port container",
        "retail": "retail store",
        "ecommerce": "ecommerce warehouse",
        "technology": "technology business",
        "ai": "artificial intelligence",
        "automation": "robotics factory",
        "truck": "semi truck freight",
        "cargo": "cargo container",
        "delivery": "delivery packages",
        "trade": "international trade",
        "tariff": "international shipping",
        "ocean": "cargo ship ocean",
        "grain": "grain agriculture export",
    }
    
    query_lower = query.lower()
    search_query = "logistics shipping cargo"
    
    for keyword, search_term in keywords_map.items():
        if keyword in query_lower:
            search_query = search_term
            break
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                "https://api.unsplash.com/search/photos",
                params={
                    "query": search_query,
                    "per_page": 10,
                    "orientation": "landscape",
                },
                headers={"Authorization": f"Client-ID {access_key}"}
            )
            response.raise_for_status()
            data = response.json()
            
            results = data.get("results", [])
            if results:
                import random
                photo = random.choice(results[:5]) if len(results) >= 5 else results[0]
                image_url = photo.get("urls", {}).get("regular")
                
                if image_url:
                    img_response = await client.get(image_url)
                    img_response.raise_for_status()
                    return Image.open(BytesIO(img_response.content)).convert("RGB")
            return None
        except Exception as e:
            print(f"Unsplash API error: {e}")
            return None


def create_fallback_background() -> Image.Image:
    """Create fallback background."""
    img = Image.new("RGB", (WIDTH, int(HEIGHT * IMAGE_HEIGHT_RATIO)), (30, 35, 50))
    draw = ImageDraw.Draw(img)
    for x in range(0, WIDTH, 50):
        draw.line([(x, 0), (x, img.height)], fill=(40, 45, 60), width=1)
    for y in range(0, img.height, 50):
        draw.line([(0, y), (WIDTH, y)], fill=(40, 45, 60), width=1)
    return img


class NewsPostRenderer:
    def __init__(self):
        self.width = WIDTH
        self.height = HEIGHT
        self._load_fonts()
        self._load_logo()
    
    def _load_fonts(self):
        """Load fonts - EXTRABOLD and HUGE."""
        try:
            # Top left brand
            self.font_brand = ImageFont.truetype(str(FONTS_DIR / "Montserrat-ExtraBold.ttf"), 38)
            # Category - centered
            self.font_category = ImageFont.truetype(str(FONTS_DIR / "Montserrat-Bold.ttf"), 28)
            # Headlines - MASSIVE EXTRABOLD
            self.font_headline_huge = ImageFont.truetype(str(FONTS_DIR / "Montserrat-ExtraBold.ttf"), 120)
            self.font_headline_xl = ImageFont.truetype(str(FONTS_DIR / "Montserrat-ExtraBold.ttf"), 100)
            self.font_headline_lg = ImageFont.truetype(str(FONTS_DIR / "Montserrat-ExtraBold.ttf"), 85)
            self.font_headline_md = ImageFont.truetype(str(FONTS_DIR / "Montserrat-ExtraBold.ttf"), 72)
            self.font_headline_sm = ImageFont.truetype(str(FONTS_DIR / "Montserrat-ExtraBold.ttf"), 60)
            print("✓ Loaded ExtraBold fonts successfully")
        except Exception as e:
            print(f"Font loading error: {e}")
            self.font_brand = ImageFont.load_default()
            self.font_category = ImageFont.load_default()
            self.font_headline_huge = ImageFont.load_default()
            self.font_headline_xl = ImageFont.load_default()
            self.font_headline_lg = ImageFont.load_default()
            self.font_headline_md = ImageFont.load_default()
            self.font_headline_sm = ImageFont.load_default()
    
    def _load_logo(self):
        """Load SVG logo."""
        self.logo = None
        try:
            import cairosvg
            logo_svg = ASSETS_DIR / "logo.svg"
            if logo_svg.exists():
                png_data = cairosvg.svg2png(url=str(logo_svg), output_width=150)
                self.logo = Image.open(BytesIO(png_data)).convert("RGBA")
                print("✓ Loaded logo from SVG")
            else:
                logo_path = ASSETS_DIR / "logo.png"
                if logo_path.exists():
                    self.logo = Image.open(logo_path).convert("RGBA")
        except Exception as e:
            print(f"Logo loading error: {e}")
    
    async def render_news_post(self, headline: str, category: str = "SUPPLY CHAIN", accent_words: list[str] = None) -> str:
        """Render news post with MASSIVE text."""
        # Create base
        img = Image.new("RGB", (self.width, self.height), DARK_BG)
        
        image_height = int(self.height * IMAGE_HEIGHT_RATIO)
        text_height = self.height - image_height
        
        # Get image
        unsplash_img = await fetch_unsplash_image(headline)
        if unsplash_img:
            top_img = self._fit_image(unsplash_img, self.width, image_height)
        else:
            top_img = create_fallback_background()
        
        img.paste(top_img, (0, 0))
        
        # Gradient
        self._add_gradient(img, image_height)
        
        draw = ImageDraw.Draw(img)
        
        # Draw elements - ONLY logo + STRUCTURE top left, category centered, headline
        self._draw_top_brand(img, draw)
        self._draw_category(draw, category, image_height)
        self._draw_headline_massive(draw, headline, image_height, text_height, accent_words)
        
        # Save
        post_id = uuid.uuid4().hex[:8]
        filename = f"{post_id}_news.png"
        filepath = OUTPUT_DIR / filename
        img.save(filepath, "PNG", quality=95)
        
        return str(filepath)
    
    def _fit_image(self, img: Image.Image, target_width: int, target_height: int) -> Image.Image:
        """Crop and resize."""
        img_ratio = img.width / img.height
        target_ratio = target_width / target_height
        
        if img_ratio > target_ratio:
            new_width = int(img.height * target_ratio)
            left = (img.width - new_width) // 2
            img = img.crop((left, 0, left + new_width, img.height))
        else:
            new_height = int(img.width / target_ratio)
            top = (img.height - new_height) // 2
            img = img.crop((0, top, img.width, top + new_height))
        
        img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
        enhancer = ImageEnhance.Brightness(img)
        return enhancer.enhance(0.75)
    
    def _add_gradient(self, img: Image.Image, image_height: int):
        """Gradient at bottom of image."""
        gradient_start = image_height - 150
        for y in range(gradient_start, image_height):
            progress = (y - gradient_start) / (image_height - gradient_start)
            for x in range(self.width):
                r, g, b = img.getpixel((x, y))
                new_r = int(r * (1 - progress) + DARK_BG[0] * progress)
                new_g = int(g * (1 - progress) + DARK_BG[1] * progress)
                new_b = int(b * (1 - progress) + DARK_BG[2] * progress)
                img.putpixel((x, y), (new_r, new_g, new_b))
    
    def _draw_top_brand(self, img: Image.Image, draw: ImageDraw.Draw):
        """Logo + STRUCTURE on top left ONLY (no NEWS)."""
        x, y = 35, 35
        
        # Draw logo
        if self.logo:
            logo_size = 55
            logo_resized = self.logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
            img.paste(logo_resized, (x, y), logo_resized)
            text_x = x + logo_size + 15
        else:
            text_x = x
        
        # STRUCTURE text next to logo - vertically centered
        text_y = y + 10
        # Shadow
        for offset in range(4, 0, -1):
            draw.text((text_x + offset, text_y + offset), "STRUCTURE", font=self.font_brand, fill=BLACK)
        draw.text((text_x, text_y), "STRUCTURE", font=self.font_brand, fill=WHITE)
    
    def _draw_category(self, draw: ImageDraw.Draw, category: str, image_height: int):
        """Category with underline - PROPERLY CENTERED."""
        y = image_height - 55
        
        # Get text dimensions for PERFECT centering
        bbox = draw.textbbox((0, 0), category, font=self.font_category)
        text_width = bbox[2] - bbox[0]
        
        # Center X position
        x = (self.width - text_width) // 2
        
        # Shadow
        for offset in range(3, 0, -1):
            draw.text((x + offset, y + offset), category, font=self.font_category, fill=BLACK)
        draw.text((x, y), category, font=self.font_category, fill=WHITE)
        
        # Centered underline
        line_y = y + 38
        line_start = x - 30
        line_end = x + text_width + 30
        draw.line([(line_start, line_y), (line_end, line_y)], fill=WHITE, width=3)
    
    def _draw_headline_massive(self, draw: ImageDraw.Draw, headline: str, image_height: int, text_height: int, accent_words: list[str] = None):
        """MASSIVE headline that FILLS the text area."""
        if accent_words is None:
            accent_words = self._auto_accent_words(headline)
        
        headline = headline.upper()
        accent_words = [w.upper() for w in accent_words]
        
        # Text area - starts right after image, more room now without watermark
        text_start_y = image_height + 50
        available_height = self.height - text_start_y - 40
        max_width = self.width - 80
        
        # Try fonts from HUGE to smaller until it fits
        fonts = [
            self.font_headline_huge,  # 120pt
            self.font_headline_xl,    # 100pt
            self.font_headline_lg,    # 85pt
            self.font_headline_md,    # 72pt
            self.font_headline_sm,    # 60pt
        ]
        
        best_font = fonts[-1]
        best_lines = []
        best_line_height = 70
        
        for font in fonts:
            lines = self._wrap_text(headline, font, max_width, draw)
            line_height = int(font.size * 1.15)
            total_height = len(lines) * line_height
            
            if total_height <= available_height and len(lines) <= 4:
                best_font = font
                best_lines = lines
                best_line_height = line_height
                break
            
            best_font = font
            best_lines = lines
            best_line_height = line_height
        
        # Center vertically
        total_height = len(best_lines) * best_line_height
        start_y = text_start_y + (available_height - total_height) // 2
        
        # Draw each line MASSIVE
        for i, line in enumerate(best_lines):
            y = start_y + i * best_line_height
            self._draw_line_massive(draw, line, y, best_font, accent_words)
    
    def _wrap_text(self, text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.Draw) -> list[str]:
        """Wrap text."""
        words = text.split()
        lines = []
        current_line = []
        
        for word in words:
            test_line = " ".join(current_line + [word])
            bbox = draw.textbbox((0, 0), test_line, font=font)
            
            if bbox[2] - bbox[0] <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]
        
        if current_line:
            lines.append(" ".join(current_line))
        
        return lines
    
    def _draw_line_massive(self, draw: ImageDraw.Draw, line: str, y: int, font: ImageFont.FreeTypeFont, accent_words: list[str]):
        """Draw line with MASSIVE text and accent colors."""
        words = line.split()
        
        # Calculate total width
        total_width = 0
        word_widths = []
        space_bbox = draw.textbbox((0, 0), " ", font=font)
        space_width = space_bbox[2] - space_bbox[0]
        
        for word in words:
            bbox = draw.textbbox((0, 0), word, font=font)
            word_widths.append(bbox[2] - bbox[0])
            total_width += word_widths[-1]
        
        total_width += space_width * (len(words) - 1)
        
        # Center
        x = (self.width - total_width) // 2
        
        for i, word in enumerate(words):
            word_clean = word.strip(".,!?\"'")
            is_accent = any(a == word_clean or a in word_clean for a in accent_words)
            color = ACCENT_CYAN if is_accent else WHITE
            
            # Heavy shadow for visibility
            for offset in range(6, 0, -1):
                draw.text((x + offset, y + offset), word, font=font, fill=BLACK)
            
            draw.text((x, y), word, font=font, fill=color)
            x += word_widths[i] + space_width
    
    def _auto_accent_words(self, headline: str) -> list[str]:
        """Auto-select accent words."""
        words = headline.split()
        important = [
            "rising", "falling", "breaking", "crisis", "surge", "record",
            "new", "first", "major", "global", "billion", "million",
            "supply", "chain", "shipping", "freight", "logistics", "ocean",
            "ai", "automation", "technology", "disruption", "shortage",
            "prices", "costs", "inflation", "growth", "decline", "cutting",
            "game", "changing", "ecommerce", "success", "grain", "exports"
        ]
        
        accent = []
        for word in words:
            if word.lower().strip(".,!?\"'") in important:
                accent.append(word)
        
        if len(accent) < 2 and len(words) > 3:
            for idx in [1, 3]:
                if idx < len(words) and words[idx] not in accent:
                    accent.append(words[idx])
                    if len(accent) >= 2:
                        break
        
        return accent[:3]


async def render_news_post(headline: str, category: str = "SUPPLY CHAIN", accent_words: list[str] = None) -> str:
    """Convenience function."""
    renderer = NewsPostRenderer()
    return await renderer.render_news_post(headline=headline, category=category, accent_words=accent_words)
