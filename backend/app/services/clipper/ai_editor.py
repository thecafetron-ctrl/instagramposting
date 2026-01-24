"""
AI-powered video editor for creating engaging short-form content.
Handles dynamic captions, music, effects, and smart clip selection.
Uses OpenAI GPT for intelligent content analysis.
"""

import json
import logging
import os
import random
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple, Dict

logger = logging.getLogger(__name__)

# Try to import OpenAI
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


def get_openai_client():
    """Get OpenAI client if available."""
    if not HAS_OPENAI:
        return None
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        return None
    return OpenAI(api_key=api_key)

# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class EditedClip:
    """Result of AI editing a clip."""
    video_path: Path
    thumbnail_path: Optional[Path]
    hook_text: str
    ending_text: str
    peak_moments: List[float]  # Timestamps of emotional peaks
    music_track: Optional[str]
    effects_applied: List[str]
    caption_style: str


@dataclass 
class ClipMoment:
    """A moment within a clip that has special significance."""
    timestamp: float
    type: str  # 'hook', 'peak', 'ending', 'punchline', 'question'
    text: str
    intensity: float  # 0-1, how impactful this moment is
    word_indices: List[int] = field(default_factory=list)


# ============================================================================
# Hook & Ending Detection
# ============================================================================

# Words that often indicate a strong hook
HOOK_INDICATORS = {
    "questions": ["why", "how", "what", "when", "did you know", "have you ever", "imagine", "picture this"],
    "controversy": ["actually", "wrong", "truth", "secret", "nobody", "everyone", "myth", "lie", "fake"],
    "surprise": ["shocking", "insane", "crazy", "unbelievable", "mind-blowing", "wild", "wait"],
    "urgency": ["stop", "listen", "watch", "look", "attention", "important", "breaking"],
    "numbers": ["one", "two", "three", "first", "second", "#1", "top", "biggest", "worst", "best"],
}

# Words that indicate a satisfying ending
ENDING_INDICATORS = {
    "conclusion": ["so", "therefore", "that's why", "in conclusion", "finally", "ultimately"],
    "call_to_action": ["follow", "subscribe", "like", "comment", "share", "check out", "link"],
    "resolution": ["and that's", "now you know", "remember", "don't forget", "the key is"],
    "impact": ["changed", "forever", "never", "always", "life", "everything", "world"],
}

# Words that indicate emotional peaks
PEAK_INDICATORS = {
    "emphasis": ["literally", "absolutely", "completely", "totally", "extremely", "incredibly"],
    "emotion": ["love", "hate", "amazing", "terrible", "beautiful", "horrible", "perfect"],
    "revelation": ["realized", "discovered", "found out", "turns out", "actually", "secretly"],
}


def analyze_caption_emphasis_with_ai(text: str, words: List[dict]) -> Dict[int, dict]:
    """
    Use GPT to intelligently determine which words should be emphasized in captions.
    Returns a dict mapping word index to emphasis style.
    """
    client = get_openai_client()
    if not client:
        return {}
    
    # Build word list with indices
    word_list = [f"{i}: {w.get('word', '')}" for i, w in enumerate(words)]
    
    prompt = f"""Analyze this text for a TikTok/Reels caption overlay. Identify which words should be visually emphasized.

TEXT: "{text}"

WORDS (index: word):
{chr(10).join(word_list)}

For engaging captions, identify:
1. HOOK words (first 3-5 words that grab attention) - make these POP
2. KEY words (the main point/punchline) - highlight in color
3. EMOTIONAL words (strong feelings) - animate these
4. NUMBERS/STATS - make these stand out

Return JSON only:
{{
  "emphasized_words": [
    {{"index": 0, "style": "pop", "color": "yellow", "reason": "hook word"}},
    {{"index": 5, "style": "highlight", "color": "green", "reason": "key point"}},
    {{"index": 12, "style": "shake", "color": "red", "reason": "emotional"}}
  ]
}}

Styles: pop (scale up), highlight (color change), shake (wiggle), glow (outline)
Colors: yellow, green, red, cyan, magenta, white
Only emphasize 5-10 most important words. Less is more."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a social media caption expert. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=500,
        )
        
        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            content = re.sub(r'^```json?\n?', '', content)
            content = re.sub(r'\n?```$', '', content)
        
        result = json.loads(content)
        
        emphasis_map = {}
        for item in result.get("emphasized_words", []):
            idx = item.get("index")
            if idx is not None:
                emphasis_map[idx] = {
                    "style": item.get("style", "pop"),
                    "color": item.get("color", "yellow"),
                    "reason": item.get("reason", ""),
                }
        
        logger.info(f"AI identified {len(emphasis_map)} words to emphasize")
        return emphasis_map
        
    except Exception as e:
        logger.warning(f"AI caption analysis failed: {e}")
        return {}


def detect_hook_moments(words: List[dict], max_time: float = 5.0) -> List[ClipMoment]:
    """Find hook moments in the first few seconds of transcript."""
    hooks = []
    
    for i, word in enumerate(words):
        if word.get("start", 0) > max_time:
            break
            
        word_text = word.get("word", "").lower().strip()
        
        # Check each hook category
        for category, indicators in HOOK_INDICATORS.items():
            for indicator in indicators:
                if indicator in word_text or (i > 0 and f"{words[i-1].get('word', '')} {word_text}".lower().strip().startswith(indicator)):
                    hooks.append(ClipMoment(
                        timestamp=word.get("start", 0),
                        type=f"hook_{category}",
                        text=word_text,
                        intensity=0.8 + random.uniform(0, 0.2),
                        word_indices=[i]
                    ))
                    break
    
    return hooks


def detect_ending_moments(words: List[dict], min_time: float = None) -> List[ClipMoment]:
    """Find good ending moments in the transcript - prioritize sentence endings and pauses."""
    if not words:
        return []
    
    endings = []
    total_duration = words[-1].get("end", 0) if words else 0
    min_time = min_time or (total_duration * 0.7)  # Look in last 30%
    
    for i, word in enumerate(words):
        word_start = word.get("start", 0)
        word_end = word.get("end", word_start)
        if word_start < min_time:
            continue
            
        word_text = word.get("word", "").strip()
        intensity = 0.5
        ending_type = "neutral"
        
        # Check for sentence-ending punctuation (strong endings)
        if word_text.endswith('.') or word_text.endswith('!') or word_text.endswith('?'):
            intensity = 0.95
            ending_type = "sentence_end"
        
        # Check for natural pause after this word (gap > 0.4s)
        elif i < len(words) - 1:
            next_start = words[i + 1].get("start", word_end)
            gap = next_start - word_end
            if gap > 0.4:
                intensity = 0.85
                ending_type = "pause"
        
        # Check for ending indicator words
        lower_text = word_text.lower()
        for category, indicators in ENDING_INDICATORS.items():
            for indicator in indicators:
                if indicator in lower_text:
                    intensity = max(intensity, 0.7 + random.uniform(0, 0.3))
                    ending_type = f"ending_{category}"
                    break
        
        # Only add if it's a decent ending
        if intensity >= 0.6:
            endings.append(ClipMoment(
                timestamp=word_end,  # Use end of word, not start
                type=ending_type,
                text=word_text,
                intensity=intensity,
                word_indices=[i]
            ))
    
    # Sort by intensity (best endings first)
    endings.sort(key=lambda e: e.intensity, reverse=True)
    
    return endings


def detect_peak_moments(words: List[dict]) -> List[ClipMoment]:
    """Find emotional peak moments throughout the transcript."""
    peaks = []
    
    for i, word in enumerate(words):
        word_text = word.get("word", "").lower().strip()
        
        for category, indicators in PEAK_INDICATORS.items():
            for indicator in indicators:
                if indicator in word_text:
                    peaks.append(ClipMoment(
                        timestamp=word.get("start", 0),
                        type=f"peak_{category}",
                        text=word_text,
                        intensity=0.6 + random.uniform(0, 0.4),
                        word_indices=[i]
                    ))
                    break
    
    return peaks


def remove_silence_gaps(
    words: List[dict],
    max_gap: float = 0.2,
) -> List[Tuple[float, float]]:
    """
    Identify segments of speech with gaps no longer than max_gap.
    Returns list of (start, end) tuples representing continuous speech.
    
    This removes long silences to keep videos engaging.
    """
    if not words:
        return []
    
    segments = []
    current_start = words[0].get("start", 0)
    current_end = words[0].get("end", 0)
    
    for i in range(1, len(words)):
        word = words[i]
        word_start = word.get("start", 0)
        word_end = word.get("end", 0)
        
        gap = word_start - current_end
        
        if gap <= max_gap:
            # Continue current segment
            current_end = word_end
        else:
            # Gap too large, save current segment and start new one
            segments.append((current_start, current_end))
            current_start = word_start
            current_end = word_end
    
    # Don't forget the last segment
    segments.append((current_start, current_end))
    
    return segments


def get_speech_only_words(
    words: List[dict],
    max_gap: float = 0.2,
) -> List[dict]:
    """
    Adjust word timestamps to remove silence gaps.
    Returns words with adjusted timestamps for continuous speech.
    """
    if not words:
        return []
    
    adjusted_words = []
    time_offset = 0
    last_end = words[0].get("start", 0)
    
    for word in words:
        word_start = word.get("start", 0)
        word_end = word.get("end", 0)
        
        gap = word_start - last_end
        if gap > max_gap:
            # Remove excess silence (keep max_gap worth)
            time_offset += gap - max_gap
        
        adjusted_words.append({
            **word,
            "start": word_start - time_offset,
            "end": word_end - time_offset,
            "original_start": word_start,
            "original_end": word_end,
        })
        
        last_end = word_end
    
    return adjusted_words


def build_silence_removal_filter(
    words: List[dict],
    max_gap: float = 0.2,
) -> Tuple[str, List[dict]]:
    """
    Build FFmpeg filter to remove silence gaps and return adjusted words.
    
    Returns:
        - FFmpeg select/concat filter string
        - List of words with adjusted timestamps
    """
    segments = remove_silence_gaps(words, max_gap)
    
    if len(segments) <= 1:
        return "", words  # No significant gaps to remove
    
    # Build FFmpeg select filter
    # Format: select='between(t,start1,end1)+between(t,start2,end2)+...',setpts=N/FRAME_RATE/TB
    select_parts = []
    for start, end in segments:
        select_parts.append(f"between(t,{start},{end})")
    
    select_filter = f"select='{'+'.join(select_parts)}',setpts=N/FRAME_RATE/TB"
    audio_filter = f"aselect='{'+'.join(select_parts)}',asetpts=N/SR/TB"
    
    # Adjust word timestamps
    adjusted_words = get_speech_only_words(words, max_gap)
    
    return f"{select_filter};{audio_filter}", adjusted_words


def find_best_clip_boundaries(
    words: List[dict],
    target_duration: float = 30.0,
    min_duration: float = 15.0,
    max_duration: float = 60.0,
) -> Tuple[float, float, List[ClipMoment]]:
    """
    Find the best start and end times for a clip that:
    1. Starts with a hook
    2. Ends on a satisfying note
    3. Contains emotional peaks
    """
    if not words:
        return 0, target_duration, []
    
    total_duration = words[-1].get("end", 0)
    
    # Detect all moments
    hooks = detect_hook_moments(words)
    peaks = detect_peak_moments(words)
    
    # Find best start (prioritize hooks)
    best_start = 0
    if hooks:
        # Start just before the hook
        best_hook = max(hooks, key=lambda h: h.intensity)
        best_start = max(0, best_hook.timestamp - 0.5)
    
    # Calculate end time based on target duration
    potential_end = best_start + target_duration
    
    # Find endings after potential_end
    endings = detect_ending_moments(words, min_time=potential_end - 5)
    
    # Adjust end to a good ending if found
    best_end = min(potential_end, total_duration)
    if endings:
        # Find ending closest to our target that's within bounds
        valid_endings = [e for e in endings if min_duration <= (e.timestamp - best_start) <= max_duration]
        if valid_endings:
            best_ending = min(valid_endings, key=lambda e: abs(e.timestamp - potential_end))
            best_end = best_ending.timestamp + 1.0  # Include the ending word
    
    # Ensure we're within bounds
    best_end = min(best_end, total_duration)
    best_end = max(best_end, best_start + min_duration)
    
    # Collect all significant moments in the clip
    clip_moments = []
    for moment in hooks + peaks + endings:
        if best_start <= moment.timestamp <= best_end:
            clip_moments.append(moment)
    
    return best_start, best_end, clip_moments


# ============================================================================
# Dynamic Captions
# ============================================================================

@dataclass
class CaptionEffect:
    """Effect to apply to a caption word."""
    word_index: int
    effect_type: str  # 'pop', 'shake', 'glow', 'color', 'size'
    intensity: float
    color: Optional[str] = None


def generate_dynamic_caption_effects(words: List[dict], moments: List[ClipMoment]) -> List[CaptionEffect]:
    """Generate visual effects for caption words based on content analysis."""
    effects = []
    
    # Create a set of important word indices from moments
    important_indices = set()
    for moment in moments:
        important_indices.update(moment.word_indices)
    
    for i, word in enumerate(words):
        word_text = word.get("word", "").lower().strip()
        
        # Emphasis words get pop effect
        if any(ind in word_text for ind in PEAK_INDICATORS.get("emphasis", [])):
            effects.append(CaptionEffect(i, "pop", 0.8, color="\\c&H00FFFF&"))  # Yellow
        
        # Emotion words get color
        if any(ind in word_text for ind in PEAK_INDICATORS.get("emotion", [])):
            effects.append(CaptionEffect(i, "color", 0.7, color="\\c&H00FF00&"))  # Green
        
        # Questions get different treatment
        if "?" in word_text:
            effects.append(CaptionEffect(i, "pop", 0.9, color="\\c&HFF00FF&"))  # Magenta
        
        # Numbers/stats get highlight
        if any(c.isdigit() for c in word_text) or word_text in ["one", "two", "three", "first", "second", "third"]:
            effects.append(CaptionEffect(i, "size", 0.8, color="\\c&H00FFFF&"))  # Yellow
        
        # Important moment words
        if i in important_indices:
            effects.append(CaptionEffect(i, "glow", 0.9))
    
    return effects


def hex_to_ass_color(hex_color: str) -> str:
    """Convert hex color (#RRGGBB) to ASS color (&HBBGGRR&)."""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 6:
        r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
        return f"&H00{b}{g}{r}&"
    return "&H00FFFFFF&"


def generate_ass_header(
    caption_color: str = "#FFFFFF",
    animation_color: str = "#FFFF00",
    title_color: str = "#FFFF00",
    caption_size: int = 80,
    caption_position: str = "middle-lower",  # "top", "middle", "middle-lower", "bottom"
) -> str:
    """Generate ASS header with custom colors, size, and position for BOX-PER-WORD style."""
    # Convert colors
    main_color = hex_to_ass_color(caption_color)
    highlight_color = hex_to_ass_color(animation_color)
    header_color = hex_to_ass_color(title_color)
    # Background color for boxes (animation color with transparency)
    box_bg_color = hex_to_ass_color(animation_color).replace("&H00", "&H80")  # 50% transparent
    
    # Calculate scaled sizes
    header_size = int(caption_size * 1.375)  # 37% larger for title
    
    # Position mapping (MarginV value and Alignment)
    # Alignment: 1-3 = bottom, 4-6 = middle, 7-9 = top
    # Within each row: 1/4/7 = left, 2/5/8 = center, 3/6/9 = right
    position_config = {
        "top": {"margin": 200, "align": 8},
        "middle": {"margin": 0, "align": 5},
        "middle-lower": {"margin": 400, "align": 5},  # 400 below center
        "bottom": {"margin": 150, "align": 2},
    }
    pos = position_config.get(caption_position, position_config["middle-lower"])
    margin_v = pos["margin"]
    alignment = pos["align"]
    
    # ASS header with BOX-PER-WORD styles
    return f"""[Script Info]
Title: Dynamic Captions - Box Per Word
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Montserrat ExtraBold,{caption_size},{main_color},&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,5,3,{alignment},40,40,{margin_v},1
Style: BoxWord,Montserrat ExtraBold,{caption_size},{main_color},&H000000FF,{box_bg_color},{box_bg_color},1,0,0,0,100,100,0,0,3,14,0,{alignment},40,40,{margin_v},1
Style: ActiveWord,Montserrat ExtraBold,{int(caption_size*1.15)},{highlight_color},&H000000FF,&H00000000,&HFF000000,1,0,0,0,110,110,0,0,3,16,0,{alignment},40,40,{margin_v},1
Style: Header,Montserrat ExtraBold,{header_size},{header_color},&H000000FF,&H00000000,&HCC000000,1,0,0,0,100,100,0,0,1,8,5,8,40,40,180,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def generate_enhanced_ass_subtitle(
    words: List[dict],
    output_path: Path,
    moments: List[ClipMoment],
    style: str = "dynamic",
    time_offset: float = 0,
    use_ai: bool = True,
    caption_color: str = "#FFFFFF",
    animation_color: str = "#FFFF00",
    title_color: str = "#FFFF00",
    caption_animation: str = "karaoke",
    caption_size: int = 80,
) -> Path:
    """
    Generate ASS subtitles with dynamic effects based on content.
    Uses AI to intelligently determine which words to emphasize.
    
    Styles:
    - dynamic: AI-powered color and size changes
    - karaoke: Word-by-word highlight
    - bounce: Words pop in with animation
    - minimal: Clean, simple captions
    """
    
    # Try AI-powered analysis first
    ai_emphasis = {}
    if use_ai and words:
        text = " ".join(w.get("word", "") for w in words)
        ai_emphasis = analyze_caption_emphasis_with_ai(text, words)
    
    # Fallback to rule-based effects
    effects = generate_dynamic_caption_effects(words, moments)
    effect_map = {e.word_index: e for e in effects}
    
    # Use custom animation color
    custom_color_code = hex_to_ass_color(animation_color).replace("&H00", "\\c&H").replace("&", "&")
    
    # Merge AI emphasis with rule-based (AI takes priority)
    color_map = {
        "yellow": "\\c&H00FFFF&",
        "green": "\\c&H00FF00&",
        "red": "\\c&H0000FF&",
        "cyan": "\\c&HFFFF00&",
        "magenta": "\\c&HFF00FF&",
        "white": "\\c&HFFFFFF&",
    }
    
    for idx, emphasis in ai_emphasis.items():
        # Use custom animation color instead of preset
        color_code = custom_color_code if emphasis.get("style") in ["pop", "highlight"] else color_map.get(emphasis.get("color", "yellow"), custom_color_code)
        effect_map[idx] = CaptionEffect(
            word_index=idx,
            effect_type=emphasis.get("style", "pop"),
            intensity=0.9,
            color=color_code,
        )
    
    # Generate header with custom colors and size
    logger.info(f"🎨 Generating captions with: text={caption_color}, highlight={animation_color}, title={title_color}, size={caption_size}")
    ass_content = generate_ass_header(caption_color, animation_color, title_color, caption_size)
    
    # Convert user's custom colors for inline use
    user_text_color = hex_to_ass_color(caption_color).replace("&H00", "\\c&H").rstrip("&")
    user_highlight_color = hex_to_ass_color(animation_color).replace("&H00", "\\c&H").rstrip("&")
    user_box_color = hex_to_ass_color(animation_color).replace("&H00", "\\3c&H").rstrip("&")  # Border/box color
    
    # Group words into lines (max 5 words per line for box style)
    lines = []
    current_line = []
    
    for i, word in enumerate(words):
        current_line.append((i, word))
        # Smaller groups for box-per-word style
        if len(current_line) >= 5 or (i < len(words) - 1 and words[i+1].get("start", 0) - word.get("end", 0) > 0.4):
            lines.append(current_line)
            current_line = []
    
    if current_line:
        lines.append(current_line)
    
    # Generate hook header for first 3-4 seconds
    if words:
        full_text = " ".join(w.get("word", "") for w in words)
        hook_header = generate_hook_header(full_text)
        
        # Add header at top of screen for first 3.5 seconds
        ass_content += f"Dialogue: 1,0:00:00.00,0:00:03.50,Header,,0,0,0,,{hook_header}\n"
    
    # Generate BOX-PER-WORD captions
    # Each word gets highlighted when it's being spoken
    for line in lines:
        if not line:
            continue
            
        line_start = line[0][1].get("start", 0) + time_offset
        line_end = line[-1][1].get("end", 0) + time_offset
        
        # Skip negative times
        if line_end < 0:
            continue
        line_start = max(0, line_start)
        
        # For each word timing, create a dialogue line with that word highlighted
        for word_idx, (idx, word) in enumerate(line):
            word_start = word.get("start", 0) + time_offset
            word_end = word.get("end", word_start + 0.3) + time_offset
            word_start = max(0, word_start)
            
            # Build the text with current word highlighted in a box
            text_parts = []
            for j, (jdx, w) in enumerate(line):
                w_text = w.get("word", "")
                if j == word_idx:
                    # This is the active word - highlight with box and pop effect
                    # Using BorderStyle 3 (opaque box) via style override
                    text_parts.append(f"{{\\bord12{user_box_color}\\shad0\\fscx110\\fscy110}}{w_text}{{\\r}}")
                else:
                    # Inactive word - normal style with user's text color
                    text_parts.append(f"{{{user_text_color}}}{w_text}")
            
            text = " ".join(text_parts)
            
            # Format times
            start_str = format_ass_time(word_start)
            end_str = format_ass_time(word_end)
            
            ass_content += f"Dialogue: 0,{start_str},{end_str},BoxWord,,0,0,0,,{text}\n"
    
    # Write file
    output_path = Path(output_path)
    output_path.write_text(ass_content)
    
    return output_path


def format_ass_time(seconds: float) -> str:
    """Format seconds as ASS timestamp (H:MM:SS.cc)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centiseconds = int((seconds % 1) * 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centiseconds:02d}"


# ============================================================================
# Video Effects via FFmpeg
# ============================================================================

def build_scene_change_filter(clip_duration: float, interval: float = 1.5) -> str:
    """
    Build FFmpeg filter for scene changes every X seconds.
    Alternates between zoom in and zoom out for dynamic feel.
    """
    # Calculate number of scene changes
    num_scenes = int(clip_duration / interval)
    if num_scenes < 2:
        return ""
    
    # Create alternating zoom expressions
    # Using sendcmd to change zoom at intervals
    zoom_expressions = []
    
    for i in range(num_scenes):
        start_time = i * interval
        end_time = (i + 1) * interval
        
        # Alternate between zoom in (1.0 -> 1.15) and zoom out (1.15 -> 1.0)
        if i % 2 == 0:
            # Zoom in during this segment
            zoom_expr = f"if(between(t,{start_time},{end_time}),1+0.1*((t-{start_time})/{interval})"
        else:
            # Zoom out during this segment  
            zoom_expr = f"if(between(t,{start_time},{end_time}),1.1-0.1*((t-{start_time})/{interval})"
        
        zoom_expressions.append(zoom_expr)
    
    # Fallback to 1.0 if no condition matches
    combined_zoom = "+".join([f"({z},0)" for z in zoom_expressions]) + "+1)"
    
    return f"zoompan=z='{combined_zoom}':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps=30"


def build_effects_filter(
    moments: List[ClipMoment],
    clip_duration: float,
    enable_zoom: bool = True,
    enable_color_grade: bool = True,
    scene_change_interval: float = 1.5,
) -> str:
    """
    Build FFmpeg filter string for dynamic video effects.
    
    Effects:
    - Scene changes every 1.5s (zoom in/out)
    - Color grading for viral look
    - Subtle vignette
    - Sharpening
    """
    filters = []
    
    # Dynamic zoom with scene changes every 1.5 seconds
    if enable_zoom:
        # Simpler approach: continuous subtle zoom pulse
        # Zoom oscillates between 1.0 and 1.1 every 1.5 seconds
        zoom_filter = f"zoompan=z='1.05+0.05*sin(2*PI*t/{scene_change_interval})':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps=30"
        filters.append(zoom_filter)
    
    if enable_color_grade:
        # Cinematic color grading - boost contrast and saturation for viral look
        filters.append("eq=contrast=1.15:brightness=0.03:saturation=1.25:gamma=1.05")
        
        # Add subtle vignette for cinematic look
        filters.append("vignette=PI/5")
        
        # Slight sharpening for crisp text/faces
        filters.append("unsharp=5:5:0.8:5:5:0.4")
        
        # Curves for that "Instagram filter" look - lift shadows, compress highlights
        filters.append("curves=preset=lighter")
    
    return ",".join(filters) if filters else ""


def build_color_grade_filter(style: str = "viral") -> str:
    """
    Build color grading filter based on style preset.
    
    Styles:
    - viral: High contrast, saturated, punchy
    - cinematic: Teal and orange, film look
    - clean: Subtle enhancement
    - moody: Darker, desaturated
    """
    presets = {
        "viral": "eq=contrast=1.2:brightness=0.02:saturation=1.3:gamma=1.05,curves=preset=lighter",
        "cinematic": "colorbalance=rs=0.1:gs=-0.05:bs=-0.1:rm=0.05:gm=0:bm=0.05,eq=contrast=1.15:saturation=1.1",
        "clean": "eq=contrast=1.05:brightness=0.01:saturation=1.1",
        "moody": "eq=contrast=1.1:brightness=-0.02:saturation=0.9:gamma=0.95,colorbalance=rs=-0.05:gs=-0.05:bs=0.05",
    }
    return presets.get(style, presets["viral"])


def add_background_music(
    video_path: Path,
    output_path: Path,
    music_path: Optional[Path] = None,
    music_volume: float = 0.15,
    fade_duration: float = 2.0,
) -> Path:
    """
    Add background music to video with proper mixing.
    
    - Ducks music under speech
    - Fades in/out
    - Loops if needed
    """
    from .crop import get_ffmpeg_path
    ffmpeg = get_ffmpeg_path()
    
    if not music_path or not music_path.exists():
        # No music, just copy
        import shutil
        shutil.copy(video_path, output_path)
        return output_path
    
    # Get video duration
    probe_cmd = [
        ffmpeg.replace('ffmpeg', 'ffprobe'),
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'json',
        str(video_path)
    ]
    
    try:
        result = subprocess.run(probe_cmd, capture_output=True, text=True)
        duration = float(json.loads(result.stdout)['format']['duration'])
    except:
        duration = 30.0
    
    # Build FFmpeg command with audio mixing
    cmd = [
        ffmpeg,
        '-i', str(video_path),
        '-stream_loop', '-1',  # Loop music if needed
        '-i', str(music_path),
        '-filter_complex', f'''
            [1:a]volume={music_volume},afade=t=in:st=0:d={fade_duration},afade=t=out:st={duration-fade_duration}:d={fade_duration}[music];
            [0:a][music]amix=inputs=2:duration=first:dropout_transition=2[aout]
        ''',
        '-map', '0:v',
        '-map', '[aout]',
        '-c:v', 'copy',
        '-c:a', 'aac',
        '-b:a', '192k',
        '-t', str(duration),
        '-y',
        str(output_path)
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return output_path
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to add music: {e.stderr.decode()}")
        # Fall back to original
        import shutil
        shutil.copy(video_path, output_path)
        return output_path


# ============================================================================
# Main AI Editor Pipeline
# ============================================================================

# ============================================================================
# AI-Powered Clip Stitching - Combine Related Moments
# ============================================================================

@dataclass
class ClipSegment:
    """A segment of video to include in a stitched clip."""
    start_time: float
    end_time: float
    text: str
    purpose: str  # 'hook', 'context', 'punchline', 'payoff'
    

def find_related_moments_with_ai(
    transcript_words: List[dict],
    topic: str,
    max_segments: int = 3,
    min_segment_duration: float = 5.0,
    max_total_duration: float = 60.0,
) -> List[ClipSegment]:
    """
    Use AI to find related moments throughout a video that can be stitched together.
    For example: setup in minute 1, punchline in minute 5, callback in minute 8.
    """
    client = get_openai_client()
    if not client:
        return []
    
    # Build full transcript with timestamps
    full_text = ""
    for w in transcript_words:
        full_text += f"[{w.get('start', 0):.1f}s] {w.get('word', '')} "
    
    prompt = f"""Analyze this video transcript and find RELATED moments that could be stitched together into one viral clip about "{topic}".

TRANSCRIPT:
{full_text[:8000]}  # Limit to avoid token limits

TASK: Find up to {max_segments} segments that together tell a complete, engaging story:
1. HOOK - The attention-grabbing opening (should come first in final clip)
2. CONTEXT/SETUP - Any necessary background or buildup
3. PAYOFF/PUNCHLINE - The satisfying conclusion or funny moment

These segments might be from DIFFERENT parts of the video but relate to the same topic/joke/story.

RULES:
- Each segment should be at least {min_segment_duration}s long
- Total combined duration should be under {max_total_duration}s
- Segments should flow naturally when combined
- Prioritize entertainment value and virality

Return ONLY valid JSON:
{{
  "segments": [
    {{
      "start_time": 12.5,
      "end_time": 18.2,
      "text": "exact quote",
      "purpose": "hook"
    }},
    {{
      "start_time": 145.0,
      "end_time": 158.3,
      "text": "exact quote",
      "purpose": "payoff"
    }}
  ],
  "stitch_reasoning": "Why these segments work together"
}}"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a viral video editor. Find related moments that can be stitched into one engaging clip. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1000,
        )
        
        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            content = re.sub(r'^```json?\n?', '', content)
            content = re.sub(r'\n?```$', '', content)
        
        result = json.loads(content)
        
        segments = []
        for seg in result.get("segments", []):
            segments.append(ClipSegment(
                start_time=float(seg.get("start_time", 0)),
                end_time=float(seg.get("end_time", 0)),
                text=seg.get("text", ""),
                purpose=seg.get("purpose", "content"),
            ))
        
        logger.info(f"AI found {len(segments)} related segments to stitch: {result.get('stitch_reasoning', '')}")
        return segments
        
    except Exception as e:
        logger.warning(f"AI clip stitching failed: {e}")
        return []


def generate_hook_header(text: str, duration: float = 3.5) -> str:
    """
    Use AI to generate a compelling hook header for the first 3-4 seconds.
    Returns the header text to display at the top of the video.
    """
    client = get_openai_client()
    if not client:
        # Fallback: use first few words
        words = text.split()[:5]
        return " ".join(words).upper() + "..."
    
    prompt = f"""Create a SHORT, punchy hook header for this video clip (to show at the top in first 3 seconds).

CLIP CONTENT: "{text[:500]}"

REQUIREMENTS:
- Maximum 4-6 words
- ALL CAPS
- Creates curiosity/intrigue
- Makes viewer want to watch
- No emojis

Good examples:
- "THE TRUTH ABOUT..."
- "NOBODY TALKS ABOUT THIS"
- "WAIT FOR IT..."
- "THIS CHANGED EVERYTHING"

Return ONLY the header text, nothing else."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You create viral video hooks. Be punchy and intriguing."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.8,
            max_tokens=50,
        )
        
        header = response.choices[0].message.content.strip()
        # Clean up
        header = header.replace('"', '').replace("'", "").strip()
        # Ensure it's not too long
        if len(header) > 40:
            header = " ".join(header.split()[:5])
        
        return header.upper()
        
    except Exception as e:
        logger.warning(f"AI header generation failed: {e}")
        return text.split()[0].upper() + "..." if text else "WATCH THIS"


def optimize_clip_with_ai(
    words: List[dict],
    start_time: float,
    end_time: float,
    min_duration: float = 15.0,
    max_duration: float = 60.0,
) -> Tuple[float, float, str, str]:
    """
    Use AI to find the optimal start/end points for a clip.
    Ensures it starts with a hook and ends satisfyingly.
    
    Returns: (optimized_start, optimized_end, hook_text, ending_reason)
    """
    client = get_openai_client()
    if not client:
        return start_time, end_time, "", ""
    
    # Get words in range with some buffer
    buffer = 10.0  # Look 10 seconds before/after
    extended_words = [
        w for w in words
        if (start_time - buffer) <= w.get("start", 0) <= (end_time + buffer)
    ]
    
    if not extended_words:
        return start_time, end_time, "", ""
    
    # Format for GPT
    word_text = " ".join(f"[{w.get('start', 0):.1f}s]{w.get('word', '')}" for w in extended_words)
    
    prompt = f"""Optimize this video clip for TikTok/Reels. Current selection: {start_time:.1f}s - {end_time:.1f}s

TRANSCRIPT WITH TIMESTAMPS:
{word_text}

REQUIREMENTS:
1. START with a HOOK - a strong opening that grabs attention immediately
   - Look for: questions, bold statements, "here's the thing", surprising facts
   - AVOID: "um", "so", filler words, incomplete thoughts
   
2. END on a SATISFYING note - not mid-sentence!
   - Look for: punchlines, revelations, conclusions, call-to-action
   - AVOID: trailing off, incomplete points
   
3. Duration should be {min_duration}-{max_duration} seconds

Return JSON only:
{{
  "optimized_start": 45.2,
  "optimized_end": 72.5,
  "hook_text": "The exact opening words that hook viewers",
  "ending_reason": "Why this is a good ending point"
}}"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a viral video editor. Optimize clip boundaries for maximum engagement. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=300,
        )
        
        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            content = re.sub(r'^```json?\n?', '', content)
            content = re.sub(r'\n?```$', '', content)
        
        result = json.loads(content)
        
        opt_start = float(result.get("optimized_start", start_time))
        opt_end = float(result.get("optimized_end", end_time))
        hook = result.get("hook_text", "")
        ending = result.get("ending_reason", "")
        
        # Validate the optimization
        duration = opt_end - opt_start
        if min_duration <= duration <= max_duration:
            logger.info(f"AI optimized clip: {start_time:.1f}-{end_time:.1f} -> {opt_start:.1f}-{opt_end:.1f}")
            return opt_start, opt_end, hook, ending
        else:
            logger.warning(f"AI optimization resulted in invalid duration ({duration:.1f}s), using original")
            return start_time, end_time, hook, ""
            
    except Exception as e:
        logger.warning(f"AI clip optimization failed: {e}")
        return start_time, end_time, "", ""


class AIVideoEditor:
    """
    AI-powered video editor that creates engaging short-form content.
    
    Features:
    - Smart clip selection with hooks and endings (AI-powered)
    - Dynamic animated captions (AI-analyzed emphasis)
    - Customizable caption colors and animations
    - Background music with ducking
    - Video effects (zoom, color grading)
    - Automatic content analysis with GPT
    """
    
    def __init__(
        self,
        music_dir: Optional[Path] = None,
        enable_effects: bool = True,
        enable_music: bool = True,
        caption_style: str = "dynamic",
        use_ai: bool = True,
        style_config: dict = None,
    ):
        self.music_dir = music_dir
        self.enable_effects = enable_effects
        self.enable_music = enable_music
        self.caption_style = caption_style
        self.use_ai = use_ai
        self.client = get_openai_client() if use_ai else None
        
        # Style configuration with defaults
        self.style_config = style_config or {
            "caption_animation": "karaoke",
            "caption_color": "#FFFFFF",
            "animation_color": "#FFFF00",
            "title_style": "bold",
            "title_color": "#FFFF00",
            "video_vibe": "default",
            "caption_size": 80,
            "add_stock_images": False,
        }
        
        # Default music tracks (royalty-free paths if available)
        self.music_tracks = []
        if music_dir and music_dir.exists():
            self.music_tracks = list(music_dir.glob("*.mp3")) + list(music_dir.glob("*.wav"))
    
    def analyze_clip(
        self,
        words: List[dict],
        start_time: float,
        end_time: float,
    ) -> Tuple[List[ClipMoment], str, str]:
        """
        Analyze a clip to find hooks, peaks, and endings.
        
        Returns:
            moments: List of significant moments
            hook_text: The hook/opening text
            ending_text: The ending text
        """
        # Filter words to clip range
        clip_words = [
            w for w in words
            if start_time <= w.get("start", 0) <= end_time
        ]
        
        # Adjust timestamps to be relative to clip start
        adjusted_words = []
        for w in clip_words:
            adjusted = w.copy()
            adjusted["start"] = w.get("start", 0) - start_time
            adjusted["end"] = w.get("end", 0) - start_time
            adjusted_words.append(adjusted)
        
        # Detect moments
        hooks = detect_hook_moments(adjusted_words)
        peaks = detect_peak_moments(adjusted_words)
        endings = detect_ending_moments(adjusted_words)
        
        all_moments = hooks + peaks + endings
        
        # Extract hook text (first sentence or first 10 words)
        hook_text = " ".join(w.get("word", "") for w in adjusted_words[:10])
        
        # Extract ending text (last sentence or last 10 words)  
        ending_text = " ".join(w.get("word", "") for w in adjusted_words[-10:])
        
        return all_moments, hook_text, ending_text
    
    def edit_clip(
        self,
        source_video: Path,
        output_path: Path,
        words: List[dict],
        start_time: float,
        end_time: float,
        burn_captions: bool = True,
        add_music: bool = None,
        add_effects: bool = None,
        optimize_boundaries: bool = True,
        log_callback=None,  # Optional callback to send logs to frontend
    ) -> EditedClip:
        """
        Apply AI editing to create an engaging clip.
        
        1. AI-optimizes clip boundaries (hook at start, good ending)
        2. Analyzes content for peaks/emphasis
        3. Generates AI-powered dynamic captions
        4. Applies video effects
        5. Adds background music
        """
        from .crop import get_ffmpeg_path, get_video_info
        from .render import render_final_clip, create_thumbnail
        
        # Helper to send logs
        def log(msg, level="info"):
            if log_callback:
                log_callback(f"      {msg}", level)
            logger.info(msg)
        
        add_music = add_music if add_music is not None else self.enable_music
        add_effects = add_effects if add_effects is not None else self.enable_effects
        
        log("🎯 Optimizing clip boundaries...")
        
        # AI-optimize clip boundaries for better hooks/endings
        if optimize_boundaries and self.use_ai:
            all_words = words  # Keep reference to full words
            opt_start, opt_end, ai_hook, ending_reason = optimize_clip_with_ai(
                all_words, start_time, end_time,
                min_duration=15.0, max_duration=60.0
            )
            if ai_hook:
                log(f"🪝 Found hook: '{ai_hook[:40]}...'", "success")
            start_time = opt_start
            end_time = opt_end
        
        log("🔍 Analyzing clip for emotional moments...")
        
        # Analyze the clip
        moments, hook_text, ending_text = self.analyze_clip(words, start_time, end_time)
        
        # Use AI hook if we got one
        if optimize_boundaries and self.use_ai and ai_hook:
            hook_text = ai_hook
        
        # Filter words for this clip
        clip_words = [
            {
                "word": w.get("word", ""),
                "start": w.get("start", 0) - start_time,
                "end": w.get("end", 0) - start_time,
                "confidence": w.get("confidence", 1.0),
            }
            for w in words
            if start_time <= w.get("start", 0) <= end_time
        ]
        
        # Generate AI-powered captions with custom styles
        log(f"📝 Generating box-per-word captions ({len(clip_words)} words)...")
        ass_path = None
        if burn_captions and clip_words:
            ass_path = output_path.with_suffix('.ass')
            generate_enhanced_ass_subtitle(
                clip_words,
                ass_path,
                moments,
                style=self.caption_style,
                time_offset=0,
                use_ai=self.use_ai,
                caption_color=self.style_config.get("caption_color", "#FFFFFF"),
                animation_color=self.style_config.get("animation_color", "#FFFF00"),
                title_color=self.style_config.get("title_color", "#FFFF00"),
                caption_animation=self.style_config.get("caption_animation", "karaoke"),
                caption_size=self.style_config.get("caption_size", 80),
            )
            log("✓ Captions generated with highlight colors", "success")
        
        # Build effects filter
        effects_filter = ""
        effects_applied = []
        if add_effects:
            log("🎨 Applying color grading + visual effects...")
            clip_duration = end_time - start_time
            effects_filter = build_effects_filter(moments, clip_duration)
            effects_applied = ["zoom", "vignette", "color_grade", "sharpen"]
        
        # Render the clip with effects and captions
        log("🎬 Rendering video with FFmpeg...")
        temp_output = output_path.with_stem(output_path.stem + "_temp")
        
        render_final_clip(
            source_video,
            temp_output,
            start_time,
            end_time,
            ass_path=ass_path,
            crop_vertical=True,
            auto_center=True,
        )
        log("✓ Video rendered", "success")
        
        # Add music if enabled
        music_track = None
        if add_music and self.music_tracks:
            music_path = random.choice(self.music_tracks)
            music_track = music_path.name
            add_background_music(temp_output, output_path, music_path)
            temp_output.unlink(missing_ok=True)
        else:
            temp_output.rename(output_path)
        
        # Create thumbnail
        thumb_path = output_path.with_stem(output_path.stem + "_thumb").with_suffix('.jpg')
        try:
            create_thumbnail(output_path, thumb_path)
        except:
            thumb_path = None
        
        return EditedClip(
            video_path=output_path,
            thumbnail_path=thumb_path,
            hook_text=hook_text,
            ending_text=ending_text,
            peak_moments=[m.timestamp for m in moments if m.type.startswith("peak")],
            music_track=music_track,
            effects_applied=effects_applied,
            caption_style=self.caption_style,
        )
    
    def find_best_clips(
        self,
        words: List[dict],
        num_clips: int = 5,
        min_duration: float = 15.0,
        max_duration: float = 60.0,
        target_duration: float = 30.0,
    ) -> List[Tuple[float, float, List[ClipMoment], float]]:
        """
        Find the best clip segments that start with hooks and end well.
        
        Returns list of (start_time, end_time, moments, score) tuples.
        """
        if not words:
            return []
        
        total_duration = words[-1].get("end", 0)
        candidates = []
        
        # Slide through the transcript looking for good starting points
        window_step = 5.0  # Check every 5 seconds
        
        for start in range(0, int(total_duration - min_duration), int(window_step)):
            start_time = float(start)
            
            # Get words from this point
            segment_words = [w for w in words if w.get("start", 0) >= start_time]
            if not segment_words:
                continue
            
            # Find best boundaries from this start
            best_start, best_end, moments = find_best_clip_boundaries(
                segment_words,
                target_duration=target_duration,
                min_duration=min_duration,
                max_duration=max_duration,
            )
            
            # Adjust back to absolute times
            actual_start = start_time + best_start
            actual_end = start_time + best_end
            
            # Score this clip
            score = self._score_clip(moments, actual_end - actual_start, target_duration)
            
            candidates.append((actual_start, actual_end, moments, score))
        
        # Remove overlapping clips, keeping highest scored
        candidates.sort(key=lambda x: x[3], reverse=True)
        
        selected = []
        for candidate in candidates:
            start, end = candidate[0], candidate[1]
            
            # Check for overlap with already selected
            overlaps = False
            for sel_start, sel_end, _, _ in selected:
                if not (end < sel_start or start > sel_end):
                    overlaps = True
                    break
            
            if not overlaps:
                selected.append(candidate)
                if len(selected) >= num_clips:
                    break
        
        # Sort by time
        selected.sort(key=lambda x: x[0])
        
        return selected
    
    def _score_clip(
        self,
        moments: List[ClipMoment],
        duration: float,
        target_duration: float,
    ) -> float:
        """Score a clip based on its content quality."""
        score = 50.0  # Base score
        
        # Bonus for hooks at the start
        hooks = [m for m in moments if m.type.startswith("hook")]
        if hooks:
            earliest_hook = min(h.timestamp for h in hooks)
            if earliest_hook < 3.0:  # Hook in first 3 seconds
                score += 25
            elif earliest_hook < 5.0:
                score += 15
        
        # Bonus for good endings
        endings = [m for m in moments if m.type.startswith("ending")]
        if endings:
            score += 15
        
        # Bonus for emotional peaks
        peaks = [m for m in moments if m.type.startswith("peak")]
        score += min(len(peaks) * 5, 20)  # Up to 20 points for peaks
        
        # Penalty for being too far from target duration
        duration_diff = abs(duration - target_duration)
        score -= duration_diff * 0.5
        
        # Penalty for being too short or too long
        if duration < 15:
            score -= 20
        elif duration > 60:
            score -= 10
        
        return max(0, score)
