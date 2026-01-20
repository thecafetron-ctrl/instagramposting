"""
News Post Renderer - Creates single-image news posts.
- Square format (1080x1080)
- Top 65%: Unsplash image related to the news
- Bottom 35%: Large ALL CAPS headline with accent colors
- Brand "STRUCTURE NEWS" at top left
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

# Layout proportions
IMAGE_HEIGHT_RATIO = 0.65  # 65% for image
TEXT_HEIGHT_RATIO = 0.35   # 35% for text

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
ACCENT_CYAN = (0, 200, 255)  # Cyan for highlighted words
DARK_BG = (15, 15, 20)

# Font paths
ASSETS_DIR = Path(__file__).parent.parent.parent / "assets"
FONTS_DIR = ASSETS_DIR / "fonts" / "montserrat"

# Output directory
OUTPUT_DIR = Path(__file__).parent.parent.parent / "generated_images"
OUTPUT_DIR.mkdir(exist_ok=True)


async def fetch_unsplash_image(query: str) -> Image.Image | None:
    """Fetch a relevant image from Unsplash API."""
    access_key = settings.unsplash_access_key
    
    if not access_key:
        print("No Unsplash access key configured")
        return None
    
    # Clean up query for better results
    search_terms = query.lower()
    # Add logistics-related terms if not present
    logistics_terms = ["logistics", "supply chain", "shipping", "freight", "warehouse", "cargo", "port", "truck"]
    has_logistics = any(term in search_terms for term in logistics_terms)
    
    if not has_logistics:
        # Try to extract key topics and add logistics context
        search_query = f"{query[:50]} logistics shipping"
    else:
        search_query = query[:80]
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                "https://api.unsplash.com/search/photos",
                params={
                    "query": search_query,
                    "per_page": 5,
                    "orientation": "landscape",
                },
                headers={
                    "Authorization": f"Client-ID {access_key}"
                }
            )
            response.raise_for_status()
            data = response.json()
            
            results = data.get("results", [])
            if not results:
                # Fallback to generic logistics search
                response = await client.get(
                    "https://api.unsplash.com/search/photos",
                    params={
                        "query": "logistics shipping cargo port",
                        "per_page": 5,
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
                # Get the first result's regular size URL
                import random
                photo = random.choice(results[:3]) if len(results) >= 3 else results[0]
                image_url = photo.get("urls", {}).get("regular")
                
                if image_url:
                    # Download the image
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
    img = Image.new("RGB", (WIDTH, int(HEIGHT * IMAGE_HEIGHT_RATIO)), DARK_BG)
    draw = ImageDraw.Draw(img)
    
    # Add grid pattern for logistics feel
    for x in range(0, WIDTH, 60):
        draw.line([(x, 0), (x, img.height)], fill=(30, 30, 40), width=1)
    for y in range(0, img.height, 60):
        draw.line([(0, y), (WIDTH, y)], fill=(30, 30, 40), width=1)
    
    # Add some nodes
    import random
    for _ in range(10):
        x, y = random.randint(50, WIDTH-50), random.randint(50, img.height-50)
        for r in range(15, 3, -2):
            alpha = int(60 * (1 - r/15))
            draw.ellipse([x-r, y-r, x+r, y+r], fill=(0, 150, 200))
    
    return img


class NewsPostRenderer:
    """Renderer for single-image news posts."""
    
    def __init__(self):
        self.width = WIDTH
        self.height = HEIGHT
        self._load_fonts()
    
    def _load_fonts(self):
        """Load Montserrat fonts."""
        try:
            # Brand font
            self.font_brand = ImageFont.truetype(str(FONTS_DIR / "Montserrat-Bold.ttf"), 36)
            # Category font
            self.font_category = ImageFont.truetype(str(FONTS_DIR / "Montserrat-SemiBold.ttf"), 24)
            # Headline font - LARGE
            self.font_headline = ImageFont.truetype(str(FONTS_DIR / "Montserrat-ExtraBold.ttf"), 56)
            self.font_headline_large = ImageFont.truetype(str(FONTS_DIR / "Montserrat-ExtraBold.ttf"), 48)
            self.font_headline_med = ImageFont.truetype(str(FONTS_DIR / "Montserrat-ExtraBold.ttf"), 42)
        except Exception as e:
            print(f"Font loading error: {e}")
            self.font_brand = ImageFont.load_default()
            self.font_category = ImageFont.load_default()
            self.font_headline = ImageFont.load_default()
            self.font_headline_large = ImageFont.load_default()
            self.font_headline_med = ImageFont.load_default()
    
    async def render_news_post(
        self,
        headline: str,
        category: str = "SUPPLY CHAIN",
        accent_words: list[str] = None,
    ) -> str:
        """
        Render a news post image.
        
        Args:
            headline: The news headline text
            category: Category label
            accent_words: Words to highlight in accent color
        
        Returns:
            Path to the generated image
        """
        # Create base image
        img = Image.new("RGB", (self.width, self.height), DARK_BG)
        
        # Fetch Unsplash image for top section
        image_height = int(self.height * IMAGE_HEIGHT_RATIO)
        text_height = self.height - image_height
        
        # Get relevant image from Unsplash
        unsplash_img = await fetch_unsplash_image(headline)
        
        if unsplash_img:
            # Crop/resize to fit top portion
            top_img = self._fit_image_to_area(unsplash_img, self.width, image_height)
        else:
            top_img = create_fallback_background()
        
        # Paste the image at top
        img.paste(top_img, (0, 0))
        
        # Add gradient overlay at bottom of image for text readability
        self._add_gradient_overlay(img, image_height)
        
        draw = ImageDraw.Draw(img)
        
        # Draw brand at top left (on the image)
        self._draw_brand(draw)
        
        # Draw category with underline (at the boundary)
        self._draw_category(draw, category, image_height)
        
        # Draw headline in the bottom 35%
        self._draw_headline(draw, headline, image_height, text_height, accent_words)
        
        # Save image
        post_id = uuid.uuid4().hex[:8]
        filename = f"{post_id}_news.png"
        filepath = OUTPUT_DIR / filename
        
        img.save(filepath, "PNG", quality=95)
        
        return str(filepath)
    
    def _fit_image_to_area(self, img: Image.Image, target_width: int, target_height: int) -> Image.Image:
        """Crop and resize image to fit target area (cover mode)."""
        # Calculate aspect ratios
        img_ratio = img.width / img.height
        target_ratio = target_width / target_height
        
        if img_ratio > target_ratio:
            # Image is wider - crop sides
            new_width = int(img.height * target_ratio)
            left = (img.width - new_width) // 2
            img = img.crop((left, 0, left + new_width, img.height))
        else:
            # Image is taller - crop top/bottom
            new_height = int(img.width / target_ratio)
            top = (img.height - new_height) // 2
            img = img.crop((0, top, img.width, top + new_height))
        
        # Resize to target
        img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
        
        # Slightly darken for better text contrast
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(0.85)
        
        return img
    
    def _add_gradient_overlay(self, img: Image.Image, image_height: int):
        """Add gradient at bottom of image area for text contrast."""
        draw = ImageDraw.Draw(img)
        
        # Gradient starting from middle of image to bottom of image section
        gradient_start = image_height - 150
        for y in range(gradient_start, image_height):
            progress = (y - gradient_start) / (image_height - gradient_start)
            alpha = int(200 * progress)
            # Draw semi-transparent black line
            for x in range(self.width):
                r, g, b = img.getpixel((x, y))
                new_r = int(r * (1 - progress * 0.8))
                new_g = int(g * (1 - progress * 0.8))
                new_b = int(b * (1 - progress * 0.8))
                img.putpixel((x, y), (new_r, new_g, new_b))
    
    def _draw_brand(self, draw: ImageDraw.Draw):
        """Draw STRUCTURE NEWS brand at top left."""
        x, y = 40, 40
        
        # Draw with shadow
        draw.text((x+2, y+2), "STRUCTURE", font=self.font_brand, fill=(0, 0, 0, 150))
        draw.text((x, y), "STRUCTURE", font=self.font_brand, fill=WHITE)
        
        draw.text((x+2, y+42), "NEWS", font=self.font_brand, fill=(0, 0, 0, 150))
        draw.text((x, y+40), "NEWS", font=self.font_brand, fill=WHITE)
    
    def _draw_category(self, draw: ImageDraw.Draw, category: str, image_height: int):
        """Draw category label with underline."""
        # Position at the boundary between image and text area
        y = image_height - 60
        
        # Get text size
        bbox = draw.textbbox((0, 0), category, font=self.font_category)
        text_width = bbox[2] - bbox[0]
        
        # Center horizontally
        x = (self.width - text_width) // 2
        
        # Draw category text with shadow
        draw.text((x+2, y+2), category, font=self.font_category, fill=(0, 0, 0, 150))
        draw.text((x, y), category, font=self.font_category, fill=WHITE)
        
        # Draw underline
        line_y = y + 35
        line_padding = 30
        draw.line(
            [(x - line_padding, line_y), (x + text_width + line_padding, line_y)],
            fill=WHITE,
            width=2
        )
    
    def _draw_headline(self, draw: ImageDraw.Draw, headline: str, image_height: int, text_height: int, accent_words: list[str] = None):
        """Draw headline in the bottom section with accent-colored keywords."""
        if accent_words is None:
            accent_words = self._auto_accent_words(headline)
        
        # Convert to uppercase
        headline = headline.upper()
        accent_words = [w.upper() for w in accent_words]
        
        # Wrap text to fit width
        max_width = self.width - 80  # Padding on sides
        
        # Try different font sizes to fit
        for font in [self.font_headline, self.font_headline_large, self.font_headline_med]:
            lines = self._wrap_text(headline, font, max_width, draw)
            line_height = font.size + 10
            total_height = len(lines) * line_height
            
            if total_height <= text_height - 40:
                break
        
        # Calculate starting Y position (center in text area)
        start_y = image_height + (text_height - total_height) // 2
        
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
        """Draw a single headline line with accent colors."""
        words = line.split()
        
        # Calculate total line width
        total_width = 0
        word_widths = []
        space_bbox = draw.textbbox((0, 0), " ", font=font)
        space_width = space_bbox[2] - space_bbox[0]
        
        for word in words:
            bbox = draw.textbbox((0, 0), word, font=font)
            word_width = bbox[2] - bbox[0]
            word_widths.append(word_width)
            total_width += word_width
        
        total_width += space_width * (len(words) - 1)
        
        # Start position (centered)
        x = (self.width - total_width) // 2
        
        # Draw each word
        for i, word in enumerate(words):
            # Check if word should be accented
            word_clean = word.strip(".,!?\"'")
            is_accent = any(accent.upper() == word_clean or accent.upper() in word_clean for accent in accent_words)
            color = ACCENT_CYAN if is_accent else WHITE
            
            # Draw shadow
            draw.text((x + 3, y + 3), word, font=font, fill=(0, 0, 0))
            
            # Draw word
            draw.text((x, y), word, font=font, fill=color)
            
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
            "global", "worldwide", "inflation", "prices", "costs",
            "shipping", "freight", "supply", "chain", "logistics"
        ]
        
        accent = []
        
        for word in words:
            clean_word = word.lower().strip(".,!?\"'")
            if clean_word in important_keywords:
                accent.append(word)
        
        # If not enough, add some words at specific positions
        if len(accent) < 2 and len(words) > 4:
            for idx in [1, 4, 7]:
                if idx < len(words) and words[idx] not in accent:
                    accent.append(words[idx])
                    if len(accent) >= 3:
                        break
        
        return accent[:4]


async def render_news_post(
    headline: str,
    category: str = "SUPPLY CHAIN",
    accent_words: list[str] = None,
) -> str:
    """
    Convenience function to render a news post.
    """
    renderer = NewsPostRenderer()
    return await renderer.render_news_post(
        headline=headline,
        category=category,
        accent_words=accent_words,
    )
