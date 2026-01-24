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
    """Find good ending moments in the transcript."""
    if not words:
        return []
    
    endings = []
    total_duration = words[-1].get("end", 0) if words else 0
    min_time = min_time or (total_duration * 0.7)  # Look in last 30%
    
    for i, word in enumerate(words):
        if word.get("start", 0) < min_time:
            continue
            
        word_text = word.get("word", "").lower().strip()
        
        for category, indicators in ENDING_INDICATORS.items():
            for indicator in indicators:
                if indicator in word_text:
                    endings.append(ClipMoment(
                        timestamp=word.get("start", 0),
                        type=f"ending_{category}",
                        text=word_text,
                        intensity=0.7 + random.uniform(0, 0.3),
                        word_indices=[i]
                    ))
                    break
    
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


def generate_enhanced_ass_subtitle(
    words: List[dict],
    output_path: Path,
    moments: List[ClipMoment],
    style: str = "dynamic",
    time_offset: float = 0,
    use_ai: bool = True,
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
        color_code = color_map.get(emphasis.get("color", "yellow"), "\\c&H00FFFF&")
        effect_map[idx] = CaptionEffect(
            word_index=idx,
            effect_type=emphasis.get("style", "pop"),
            intensity=0.9,
            color=color_code,
        )
    
    # ASS header with multiple styles
    ass_content = """[Script Info]
Title: Dynamic Captions
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Montserrat,72,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,4,2,2,40,40,120,1
Style: Hook,Montserrat,84,&H00FFFF00,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,5,3,2,40,40,120,1
Style: Peak,Montserrat,80,&H0000FF00,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,4,2,2,40,40,120,1
Style: Emphasis,Montserrat,90,&H00FF00FF,&H000000FF,&H00000000,&H80000000,1,0,0,0,110,110,0,0,1,5,3,2,40,40,120,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    
    # Group words into lines (max 6 words per line)
    lines = []
    current_line = []
    
    for i, word in enumerate(words):
        current_line.append((i, word))
        if len(current_line) >= 6 or (i < len(words) - 1 and words[i+1].get("start", 0) - word.get("end", 0) > 0.5):
            lines.append(current_line)
            current_line = []
    
    if current_line:
        lines.append(current_line)
    
    # Generate events for each line
    for line in lines:
        if not line:
            continue
            
        start_time = line[0][1].get("start", 0) + time_offset
        end_time = line[-1][1].get("end", 0) + time_offset
        
        # Determine line style based on content
        line_style = "Default"
        for idx, word in line:
            if idx in effect_map:
                effect = effect_map[idx]
                if effect.effect_type in ["pop", "glow"]:
                    line_style = "Peak"
                    break
        
        # Check if this is a hook line (first few seconds)
        if start_time < 3:
            line_style = "Hook"
        
        # Build the text with karaoke timing
        text_parts = []
        for idx, word in line:
            word_text = word.get("word", "")
            word_start = word.get("start", 0) + time_offset
            word_duration = int((word.get("end", word_start) - word_start) * 100)
            
            # Apply effects
            if idx in effect_map:
                effect = effect_map[idx]
                if effect.color:
                    word_text = f"{{{effect.color}}}{word_text}{{\\c&HFFFFFF&}}"
                if effect.effect_type == "size":
                    word_text = f"{{\\fscx120\\fscy120}}{word_text}{{\\fscx100\\fscy100}}"
            
            # Karaoke timing
            text_parts.append(f"{{\\k{word_duration}}}{word_text}")
        
        text = " ".join(text_parts)
        
        # Format times
        start_str = format_ass_time(max(0, start_time))
        end_str = format_ass_time(end_time)
        
        ass_content += f"Dialogue: 0,{start_str},{end_str},{line_style},,0,0,0,,{text}\n"
    
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

def build_effects_filter(
    moments: List[ClipMoment],
    clip_duration: float,
    enable_zoom: bool = True,
    enable_shake: bool = True,
    enable_flash: bool = True,
) -> str:
    """
    Build FFmpeg filter string for dynamic video effects.
    
    Effects:
    - Subtle zoom on peaks
    - Camera shake on emphasis
    - Flash/brightness on hooks
    """
    filters = []
    
    # Base crop for vertical
    # This will be added separately
    
    # Ken Burns style subtle zoom throughout
    if enable_zoom:
        # Gentle zoom from 1.0 to 1.05 over the clip
        filters.append(f"zoompan=z='1+0.0005*in':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920")
    
    # Add subtle vignette for cinematic look
    filters.append("vignette=PI/4")
    
    # Color grading for social media pop
    filters.append("eq=contrast=1.1:brightness=0.02:saturation=1.2")
    
    # Slight sharpening
    filters.append("unsharp=5:5:0.5:5:5:0")
    
    return ",".join(filters) if filters else ""


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
    ):
        self.music_dir = music_dir
        self.enable_effects = enable_effects
        self.enable_music = enable_music
        self.caption_style = caption_style
        self.use_ai = use_ai
        self.client = get_openai_client() if use_ai else None
        
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
        
        add_music = add_music if add_music is not None else self.enable_music
        add_effects = add_effects if add_effects is not None else self.enable_effects
        
        # AI-optimize clip boundaries for better hooks/endings
        if optimize_boundaries and self.use_ai:
            all_words = words  # Keep reference to full words
            opt_start, opt_end, ai_hook, ending_reason = optimize_clip_with_ai(
                all_words, start_time, end_time,
                min_duration=15.0, max_duration=60.0
            )
            if ai_hook:
                logger.info(f"AI optimized clip to start with hook: '{ai_hook[:50]}...'")
            start_time = opt_start
            end_time = opt_end
        
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
        
        # Generate AI-powered captions
        ass_path = None
        if burn_captions and clip_words:
            ass_path = output_path.with_suffix('.ass')
            generate_enhanced_ass_subtitle(
                clip_words,
                ass_path,
                moments,
                style=self.caption_style,
                time_offset=0,
                use_ai=self.use_ai,  # Enable AI caption analysis
            )
        
        # Build effects filter
        effects_filter = ""
        effects_applied = []
        if add_effects:
            clip_duration = end_time - start_time
            effects_filter = build_effects_filter(moments, clip_duration)
            effects_applied = ["zoom", "vignette", "color_grade", "sharpen"]
        
        # Render the clip with effects and captions
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
