"""Caption generation module - ASS subtitles with karaoke word highlighting."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .transcribe import Word

logger = logging.getLogger(__name__)

OUTPUT_WIDTH = 1080
OUTPUT_HEIGHT = 1920


@dataclass
class CaptionStyle:
    """Caption styling configuration."""
    font_name: str = "Arial"
    font_size: int = 48
    primary_color: str = "&H00FFFFFF"
    secondary_color: str = "&H0000FFFF"
    outline_color: str = "&H00000000"
    back_color: str = "&H80000000"
    bold: bool = True
    outline: float = 3.0
    shadow: float = 2.0
    margin_v: int = 120
    margin_l: int = 40
    margin_r: int = 40
    alignment: int = 2
    max_chars_per_line: int = 35


STYLE_PRESETS = {
    "default": CaptionStyle(),
    "bold_yellow": CaptionStyle(
        primary_color="&H00FFFFFF",
        secondary_color="&H0000FFFF",
        font_size=52,
        outline=4.0,
    ),
    "minimal": CaptionStyle(
        font_size=42,
        outline=2.0,
        shadow=0.0,
        primary_color="&H00FFFFFF",
        secondary_color="&H00FFFFFF",
    ),
    "neon": CaptionStyle(
        primary_color="&H00FF00FF",
        secondary_color="&H0000FF00",
        outline_color="&H00000000",
        font_size=50,
        outline=4.0,
        shadow=3.0,
    ),
    "tiktok": CaptionStyle(
        font_name="Arial Black",
        font_size=54,
        primary_color="&H00FFFFFF",
        secondary_color="&H0000FFFF",
        outline=5.0,
        shadow=0.0,
        margin_v=150,
    ),
}


def get_style_preset(name: str) -> CaptionStyle:
    """Get a caption style preset by name."""
    return STYLE_PRESETS.get(name, STYLE_PRESETS["default"])


def generate_ass_header(style: CaptionStyle) -> str:
    """Generate ASS file header with style definitions."""
    header = f"""[Script Info]
Title: Clipper Captioner
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709
PlayResX: {OUTPUT_WIDTH}
PlayResY: {OUTPUT_HEIGHT}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{style.font_name},{style.font_size},{style.primary_color},{style.secondary_color},{style.outline_color},{style.back_color},{int(style.bold)},0,0,0,100,100,0,0,1,{style.outline},{style.shadow},{style.alignment},{style.margin_l},{style.margin_r},{style.margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    return header


def format_ass_time(seconds: float) -> str:
    """Convert seconds to ASS timestamp format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centisecs = int((seconds % 1) * 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centisecs:02d}"


def calculate_karaoke_timing(word: Word, line_start: float) -> int:
    """Calculate karaoke timing for a word."""
    duration = word.end - word.start
    return max(1, int(duration * 100))


def split_into_lines(
    words: list[Word],
    max_chars: int = 35,
    max_words: int = 8,
) -> list[list[Word]]:
    """Split words into display lines."""
    if not words:
        return []
    
    lines = []
    current_line = []
    current_chars = 0
    
    for word in words:
        word_len = len(word.word) + 1
        
        if current_line and (
            current_chars + word_len > max_chars or
            len(current_line) >= max_words
        ):
            lines.append(current_line)
            current_line = []
            current_chars = 0
        
        current_line.append(word)
        current_chars += word_len
    
    if current_line:
        lines.append(current_line)
    
    if len(lines) > 2:
        all_words = [w for line in lines for w in line]
        mid = len(all_words) // 2
        lines = [all_words[:mid], all_words[mid:]]
    
    return lines


def generate_karaoke_text(
    words: list[Word],
    style: CaptionStyle,
) -> tuple[str, float, float]:
    """Generate karaoke-style ASS text for a group of words."""
    if not words:
        return "", 0, 0
    
    start_time = words[0].start
    end_time = words[-1].end
    
    lines = split_into_lines(words, style.max_chars_per_line)
    
    ass_lines = []
    for line_words in lines:
        line_parts = []
        for word in line_words:
            duration_cs = calculate_karaoke_timing(word, start_time)
            line_parts.append(f"{{\\kf{duration_cs}}}{word.word}")
        
        ass_lines.append(" ".join(line_parts))
    
    ass_text = "\\N".join(ass_lines)
    
    return ass_text, start_time, end_time


def group_words_for_display(
    words: list[Word],
    group_duration: float = 3.0,
    max_words_per_group: int = 12,
) -> list[list[Word]]:
    """Group words into display chunks for caption timing."""
    if not words:
        return []
    
    groups = []
    current_group = []
    group_start = words[0].start
    
    for word in words:
        should_split = False
        
        if current_group:
            elapsed = word.end - group_start
            if elapsed > group_duration:
                should_split = True
            if len(current_group) >= max_words_per_group:
                should_split = True
            if current_group[-1].word.rstrip()[-1:] in '.!?' and elapsed > 1.0:
                should_split = True
        
        if should_split and current_group:
            groups.append(current_group)
            current_group = []
            group_start = word.start
        
        current_group.append(word)
    
    if current_group:
        groups.append(current_group)
    
    return groups


def generate_ass_subtitles(
    words: list[Word],
    output_path: str | Path,
    style: Optional[CaptionStyle] = None,
    time_offset: float = 0.0,
) -> Path:
    """Generate ASS subtitle file with karaoke word highlighting."""
    if style is None:
        style = CaptionStyle()
    
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    adjusted_words = []
    for word in words:
        adjusted_words.append(Word(
            word=word.word,
            start=max(0, word.start - time_offset),
            end=max(0, word.end - time_offset),
            confidence=word.confidence
        ))
    
    groups = group_words_for_display(adjusted_words)
    
    ass_content = generate_ass_header(style)
    
    for group in groups:
        text, start, end = generate_karaoke_text(group, style)
        if text:
            start_str = format_ass_time(start)
            end_str = format_ass_time(end)
            ass_content += f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{text}\n"
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(ass_content)
    
    logger.info(f"Generated ASS subtitles: {output_path}")
    return output_path


def generate_clip_captions(
    words: list[Word],
    clip_start: float,
    clip_end: float,
    output_path: str | Path,
    style: Optional[CaptionStyle] = None,
) -> Path:
    """Generate captions for a specific clip segment."""
    clip_words = [
        w for w in words
        if w.start >= clip_start - 0.1 and w.end <= clip_end + 0.1
    ]
    
    if not clip_words:
        logger.warning(f"No words found for clip {clip_start:.1f}-{clip_end:.1f}")
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        style = style or CaptionStyle()
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(generate_ass_header(style))
        return output_path
    
    return generate_ass_subtitles(
        clip_words,
        output_path,
        style=style,
        time_offset=clip_start
    )
