"""
News Post Renderer - Creates single-image news posts.
- Square format (1080x1080)
- Top 60%: Unsplash image related to the news
- Bottom 40%: MASSIVE ALL CAPS headline with accent colors
- Brand "STRUCTURE" + logo above the black section
- Category label with underline
"""

import os
import uuid
import httpx
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from pathlib import Path

from app.config import get_settings

settings = get_settings()

# Square dimensions
WIDTH = 1080
HEIGHT = 1080

# Layout proportions - more space for text
IMAGE_HEIGHT_RATIO = 0.58  # 58% for image
TEXT_HEIGHT_RATIO = 0.42   # 42% for text (BIGGER)

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
ACCENT_CYAN = (0, 200, 255)  # Cyan for highlighted words
DARK_BG = (12, 12, 18)

# Font paths
ASSETS_DIR = Path(__file__).parent.parent.parent / "assets"
FONTS_DIR = ASSETS_DIR / "fonts" / "montserrat"
LOGO_PATH = ASSETS_DIR / "logo.svg"

# Output directory
OUTPUT_DIR = Path(__file__).parent.parent.parent / "generated_images"
OUTPUT_DIR.mkdir(exist_ok=True)


async def fetch_unsplash_image(query: str) -> Image.Image | None:
    """Fetch a relevant image from Unsplash API."""
    access_key = settings.unsplash_access_key
    
    if not access_key:
        print("No Unsplash access key configured")
        return None
    
    # Build better search query
    search_terms = []
    
    # Extract key concepts from headline
    keywords_map = {
        "supply chain": "supply chain warehouse logistics",
        "logistics": "logistics warehouse shipping",
        "shipping": "cargo ship container port",
        "freight": "freight truck cargo transport",
        "warehouse": "warehouse storage logistics",
        "port": "shipping port cargo container",
        "retail": "retail store shopping",
        "ecommerce": "ecommerce warehouse packages",
        "technology": "technology business office",
        "ai": "artificial intelligence technology",
        "automation": "automation robotics factory",
        "truck": "semi truck freight highway",
        "cargo": "cargo container shipping",
        "delivery": "delivery truck packages",
        "amazon": "ecommerce warehouse packages",
        "trade": "international trade shipping port",
        "tariff": "international trade shipping",
        "inflation": "business economy finance",
        "prices": "business economy market",
    }
    
    query_lower = query.lower()
    for keyword, search_term in keywords_map.items():
        if keyword in query_lower:
            search_terms.append(search_term)
            break
    
    if not search_terms:
        search_terms = ["logistics shipping cargo business"]
    
    search_query = search_terms[0]
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                "https://api.unsplash.com/search/photos",
                params={
                    "query": search_query,
                    "per_page": 10,
                    "orientation": "landscape",
                },
                headers={
                    "Authorization": f"Client-ID {access_key}"
                }
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
                    img = Image.open(BytesIO(img_response.content))
                    return img.convert("RGB")
            
            return None
            
        except Exception as e:
            print(f"Unsplash API error: {e}")
            return None


def create_fallback_background() -> Image.Image:
    """Create a fallback background if Unsplash fails."""
    img = Image.new("RGB", (WIDTH, int(HEIGHT * IMAGE_HEIGHT_RATIO)), (30, 35, 50))
    draw = ImageDraw.Draw(img)
    
    # Add grid pattern
    for x in range(0, WIDTH, 50):
        draw.line([(x, 0), (x, img.height)], fill=(40, 45, 60), width=1)
    for y in range(0, img.height, 50):
        draw.line([(0, y), (WIDTH, y)], fill=(40, 45, 60), width=1)
    
    return img


class NewsPostRenderer:
    """Renderer for single-image news posts."""
    
    def __init__(self):
        self.width = WIDTH
        self.height = HEIGHT
        self._load_fonts()
        self._load_logo()
    
    def _load_fonts(self):
        """Load Montserrat fonts - MASSIVE sizes."""
        try:
            # Brand font
            self.font_brand = ImageFont.truetype(str(FONTS_DIR / "Montserrat-Bold.ttf"), 28)
            # Category font
            self.font_category = ImageFont.truetype(str(FONTS_DIR / "Montserrat-SemiBold.ttf"), 20)
            # Headline fonts - MASSIVE and ULTRA BOLD
            self.font_headline_xl = ImageFont.truetype(str(FONTS_DIR / "Montserrat-ExtraBold.ttf"), 72)
            self.font_headline_lg = ImageFont.truetype(str(FONTS_DIR / "Montserrat-ExtraBold.ttf"), 62)
            self.font_headline_md = ImageFont.truetype(str(FONTS_DIR / "Montserrat-ExtraBold.ttf"), 52)
            self.font_headline_sm = ImageFont.truetype(str(FONTS_DIR / "Montserrat-ExtraBold.ttf"), 44)
        except Exception as e:
            print(f"Font loading error: {e}")
            self.font_brand = ImageFont.load_default()
            self.font_category = ImageFont.load_default()
            self.font_headline_xl = ImageFont.load_default()
            self.font_headline_lg = ImageFont.load_default()
            self.font_headline_md = ImageFont.load_default()
            self.font_headline_sm = ImageFont.load_default()
    
    def _load_logo(self):
        """Load the STRUCTURE logo."""
        self.logo = None
        try:
            # Try PNG first
            logo_png = ASSETS_DIR / "logo.png"
            if logo_png.exists():
                self.logo = Image.open(logo_png).convert("RGBA")
            else:
                # Try converting SVG
                try:
                    import cairosvg
                    logo_svg = ASSETS_DIR / "logo.svg"
                    if logo_svg.exists():
                        png_data = cairosvg.svg2png(url=str(logo_svg), output_width=120)
                        self.logo = Image.open(BytesIO(png_data)).convert("RGBA")
                except:
                    pass
        except Exception as e:
            print(f"Logo loading error: {e}")
    
    async def render_news_post(
        self,
        headline: str,
        category: str = "SUPPLY CHAIN",
        accent_words: list[str] = None,
    ) -> str:
        """Render a news post image."""
        # Create base image
        img = Image.new("RGB", (self.width, self.height), DARK_BG)
        
        # Calculate sections
        image_height = int(self.height * IMAGE_HEIGHT_RATIO)
        text_height = self.height - image_height
        
        # Get Unsplash image
        unsplash_img = await fetch_unsplash_image(headline)
        
        if unsplash_img:
            top_img = self._fit_image_to_area(unsplash_img, self.width, image_height)
        else:
            top_img = create_fallback_background()
        
        # Paste image at top
        img.paste(top_img, (0, 0))
        
        # Add gradient at bottom of image
        self._add_gradient_overlay(img, image_height)
        
        draw = ImageDraw.Draw(img)
        
        # Draw brand "STRUCTURE NEWS" at top left
        self._draw_brand(draw)
        
        # Draw category with underline at boundary
        self._draw_category(draw, category, image_height)
        
        # Draw STRUCTURE + logo above black section
        self._draw_structure_branding(img, draw, image_height)
        
        # Draw MASSIVE headline in bottom section
        self._draw_headline(draw, headline, image_height, text_height, accent_words)
        
        # Save
        post_id = uuid.uuid4().hex[:8]
        filename = f"{post_id}_news.png"
        filepath = OUTPUT_DIR / filename
        
        img.save(filepath, "PNG", quality=95)
        
        return str(filepath)
    
    def _fit_image_to_area(self, img: Image.Image, target_width: int, target_height: int) -> Image.Image:
        """Crop and resize image to fit target area."""
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
        
        # Slightly darken
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(0.8)
        
        return img
    
    def _add_gradient_overlay(self, img: Image.Image, image_height: int):
        """Add gradient at bottom of image for smooth transition."""
        gradient_start = image_height - 120
        for y in range(gradient_start, image_height):
            progress = (y - gradient_start) / (image_height - gradient_start)
            for x in range(self.width):
                r, g, b = img.getpixel((x, y))
                # Blend toward dark background color
                new_r = int(r * (1 - progress) + DARK_BG[0] * progress)
                new_g = int(g * (1 - progress) + DARK_BG[1] * progress)
                new_b = int(b * (1 - progress) + DARK_BG[2] * progress)
                img.putpixel((x, y), (new_r, new_g, new_b))
    
    def _draw_brand(self, draw: ImageDraw.Draw):
        """Draw STRUCTURE NEWS at top left."""
        x, y = 40, 35
        
        # Shadow
        draw.text((x+2, y+2), "STRUCTURE", font=self.font_brand, fill=(0, 0, 0))
        draw.text((x, y), "STRUCTURE", font=self.font_brand, fill=WHITE)
        
        draw.text((x+2, y+32), "NEWS", font=self.font_brand, fill=(0, 0, 0))
        draw.text((x, y+30), "NEWS", font=self.font_brand, fill=WHITE)
    
    def _draw_category(self, draw: ImageDraw.Draw, category: str, image_height: int):
        """Draw category with underline."""
        y = image_height - 50
        
        bbox = draw.textbbox((0, 0), category, font=self.font_category)
        text_width = bbox[2] - bbox[0]
        x = (self.width - text_width) // 2
        
        # Shadow
        draw.text((x+1, y+1), category, font=self.font_category, fill=(0, 0, 0))
        draw.text((x, y), category, font=self.font_category, fill=WHITE)
        
        # Underline
        line_y = y + 28
        draw.line([(x - 20, line_y), (x + text_width + 20, line_y)], fill=WHITE, width=2)
    
    def _draw_structure_branding(self, img: Image.Image, draw: ImageDraw.Draw, image_height: int):
        """Draw STRUCTURE text and logo above the black section."""
        # Position just above the text area
        y = image_height + 15
        
        # Draw logo if available
        if self.logo:
            logo_size = 35
            logo_resized = self.logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
            
            # Calculate position (centered with text)
            brand_text = "STRUCTURE"
            bbox = draw.textbbox((0, 0), brand_text, font=self.font_brand)
            text_width = bbox[2] - bbox[0]
            total_width = logo_size + 10 + text_width
            
            start_x = (self.width - total_width) // 2
            
            # Paste logo
            img.paste(logo_resized, (start_x, y), logo_resized)
            
            # Draw STRUCTURE text
            text_x = start_x + logo_size + 10
            draw.text((text_x, y + 5), brand_text, font=self.font_brand, fill=(150, 150, 160))
        else:
            # Just draw text centered
            brand_text = "STRUCTURE"
            bbox = draw.textbbox((0, 0), brand_text, font=self.font_brand)
            text_width = bbox[2] - bbox[0]
            x = (self.width - text_width) // 2
            draw.text((x, y), brand_text, font=self.font_brand, fill=(150, 150, 160))
    
    def _draw_headline(self, draw: ImageDraw.Draw, headline: str, image_height: int, text_height: int, accent_words: list[str] = None):
        """Draw MASSIVE headline in bottom section."""
        if accent_words is None:
            accent_words = self._auto_accent_words(headline)
        
        # ALL CAPS
        headline = headline.upper()
        accent_words = [w.upper() for w in accent_words]
        
        # Available space for text (leave room for branding at top)
        text_start_y = image_height + 60
        available_height = text_height - 80
        
        max_width = self.width - 80
        
        # Try fonts from largest to smallest
        fonts = [self.font_headline_xl, self.font_headline_lg, self.font_headline_md, self.font_headline_sm]
        
        for font in fonts:
            lines = self._wrap_text(headline, font, max_width, draw)
            line_height = font.size + 12
            total_height = len(lines) * line_height
            
            if total_height <= available_height and len(lines) <= 5:
                break
        
        # Center vertically in available space
        start_y = text_start_y + (available_height - total_height) // 2
        
        # Draw each line
        for i, line in enumerate(lines):
            y = start_y + i * line_height
            self._draw_headline_line(draw, line, y, font, accent_words)
    
    def _wrap_text(self, text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.Draw) -> list[str]:
        """Wrap text to fit width."""
        words = text.split()
        lines = []
        current_line = []
        
        for word in words:
            test_line = " ".join(current_line + [word])
            bbox = draw.textbbox((0, 0), test_line, font=font)
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
    
    def _draw_headline_line(self, draw: ImageDraw.Draw, line: str, y: int, font: ImageFont.FreeTypeFont, accent_words: list[str]):
        """Draw headline line with accent colors."""
        words = line.split()
        
        # Calculate widths
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
            
            # Strong shadow for readability
            draw.text((x + 3, y + 3), word, font=font, fill=(0, 0, 0))
            draw.text((x + 2, y + 2), word, font=font, fill=(20, 20, 20))
            draw.text((x, y), word, font=font, fill=color)
            
            x += word_widths[i] + space_width
    
    def _auto_accent_words(self, headline: str) -> list[str]:
        """Auto-select words to highlight."""
        words = headline.split()
        
        important = [
            "rising", "falling", "breaking", "crisis", "surge", "record",
            "new", "first", "major", "global", "billion", "million",
            "supply", "chain", "shipping", "freight", "logistics",
            "ai", "automation", "technology", "disruption", "shortage",
            "prices", "costs", "inflation", "growth", "decline"
        ]
        
        accent = []
        for word in words:
            if word.lower().strip(".,!?\"'") in important:
                accent.append(word)
        
        if len(accent) < 2 and len(words) > 3:
            for idx in [1, 3, 5]:
                if idx < len(words) and words[idx] not in accent:
                    accent.append(words[idx])
                    if len(accent) >= 2:
                        break
        
        return accent[:3]


async def render_news_post(
    headline: str,
    category: str = "SUPPLY CHAIN",
    accent_words: list[str] = None,
) -> str:
    """Convenience function to render a news post."""
    renderer = NewsPostRenderer()
    return await renderer.render_news_post(
        headline=headline,
        category=category,
        accent_words=accent_words,
    )
