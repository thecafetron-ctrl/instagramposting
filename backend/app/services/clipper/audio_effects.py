"""
Audio effects module - background music, sound effects, and audio ducking.
Makes clips more engaging with viral-style audio production.
"""

import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, List
import urllib.request

from .crop import get_ffmpeg_path

logger = logging.getLogger(__name__)

# Directory for audio assets
ASSETS_DIR = Path(__file__).parent.parent.parent.parent / "assets" / "audio"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

# Royalty-free music URLs (using free public domain sources)
# These are direct download links that work without authentication
MUSIC_URLS = {
    "upbeat": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",  # Upbeat electronic
    "chill": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-2.mp3",   # Chill vibe
    "dramatic": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-3.mp3", # Dramatic
    "funny": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-4.mp3",   # Quirky
}

# Fallback: Generate simple beat with FFmpeg if download fails
def generate_simple_beat(output_path: Path, duration: float = 60, style: str = "upbeat") -> Optional[Path]:
    """Generate a simple beat using FFmpeg audio synthesis."""
    ffmpeg = get_ffmpeg_path()
    
    # Different beats for different styles
    if style == "dramatic":
        # Deep bass pulse
        audio_filter = "sine=f=50:d=60,volume=0.3,asetrate=44100"
    elif style == "chill":
        # Soft ambient pad
        audio_filter = "anoisesrc=d=60:c=brown:r=44100:a=0.1,lowpass=f=500"
    else:
        # Upbeat click pattern (120 BPM)
        audio_filter = "sine=f=1000:d=0.05,apad=pad_dur=0.45|sine=f=800:d=0.05,apad=pad_dur=0.45,aloop=loop=120:size=44100"
    
    cmd = [
        ffmpeg, '-y',
        '-f', 'lavfi',
        '-i', f'anoisesrc=d={duration}:c=pink:r=44100:a=0.05',  # Simple ambient
        '-af', 'lowpass=f=2000,volume=0.3',
        '-t', str(duration),
        '-c:a', 'libmp3lame',
        '-q:a', '4',
        str(output_path)
    ]
    
    try:
        subprocess.run(cmd, capture_output=True, check=True, timeout=30)
        return output_path
    except Exception as e:
        logger.warning(f"Failed to generate beat: {e}")
        return None


def download_music_if_needed(style: str = "upbeat") -> Optional[Path]:
    """Download royalty-free background music if not already cached."""
    music_path = ASSETS_DIR / f"music_{style}.mp3"
    
    if music_path.exists() and music_path.stat().st_size > 10000:
        return music_path
    
    url = MUSIC_URLS.get(style, MUSIC_URLS["upbeat"])
    
    try:
        logger.info(f"Downloading {style} music from {url}...")
        
        # Use requests-style download with headers
        import urllib.request
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        with urllib.request.urlopen(req, timeout=30) as response:
            with open(music_path, 'wb') as f:
                f.write(response.read())
        
        if music_path.exists() and music_path.stat().st_size > 10000:
            logger.info(f"Music downloaded: {music_path}")
            return music_path
        else:
            raise Exception("Downloaded file too small")
            
    except Exception as e:
        logger.warning(f"Failed to download music: {e}")
        
        # Fallback: Generate simple ambient track
        logger.info("Generating ambient background track...")
        generated_path = ASSETS_DIR / f"generated_{style}.mp3"
        if generate_simple_beat(generated_path, duration=120, style=style):
            return generated_path
        
        return None


def generate_whoosh_sound(output_path: Path, duration: float = 0.5) -> Path:
    """Generate a whoosh/swoosh sound effect using FFmpeg."""
    ffmpeg = get_ffmpeg_path()
    
    # Generate a swoosh using filtered noise
    cmd = [
        ffmpeg, '-y',
        '-f', 'lavfi',
        '-i', f'anoisesrc=d={duration}:c=pink:r=44100:a=0.5',
        '-af', f'afade=t=in:st=0:d={duration*0.3},afade=t=out:st={duration*0.5}:d={duration*0.5},highpass=f=2000,lowpass=f=8000,volume=0.6',
        '-c:a', 'libmp3lame',
        '-q:a', '4',
        str(output_path)
    ]
    
    try:
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path
    except Exception as e:
        logger.warning(f"Failed to generate whoosh: {e}")
        return None


def generate_bass_drop(output_path: Path, duration: float = 0.3) -> Path:
    """Generate a bass drop/impact sound effect."""
    ffmpeg = get_ffmpeg_path()
    
    # Generate a bass impact using sine wave with envelope
    cmd = [
        ffmpeg, '-y',
        '-f', 'lavfi',
        '-i', f'sine=f=60:d={duration}',
        '-af', f'afade=t=in:st=0:d=0.01,afade=t=out:st=0.05:d={duration-0.05},volume=0.8',
        '-c:a', 'libmp3lame',
        '-q:a', '4',
        str(output_path)
    ]
    
    try:
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path
    except Exception as e:
        logger.warning(f"Failed to generate bass drop: {e}")
        return None


def generate_transition_sound(output_path: Path, style: str = "whoosh") -> Path:
    """Generate a transition sound effect."""
    if style == "whoosh":
        return generate_whoosh_sound(output_path, duration=0.4)
    elif style == "bass":
        return generate_bass_drop(output_path, duration=0.3)
    elif style == "click":
        # Short click/pop
        ffmpeg = get_ffmpeg_path()
        cmd = [
            ffmpeg, '-y',
            '-f', 'lavfi', '-i', 'sine=f=1000:d=0.05',
            '-af', 'afade=t=out:st=0:d=0.05,volume=0.5',
            '-c:a', 'libmp3lame', '-q:a', '4',
            str(output_path)
        ]
        try:
            subprocess.run(cmd, capture_output=True, check=True)
            return output_path
        except:
            return None
    return None


def add_background_music_with_ducking(
    video_path: Path,
    output_path: Path,
    music_path: Optional[Path] = None,
    music_style: str = "upbeat",
    music_volume: float = 0.15,
    duck_threshold: float = 0.02,
    duck_ratio: float = 3.0,
) -> Path:
    """
    Add background music with automatic voice ducking.
    Music volume automatically lowers when speech is detected.
    
    Args:
        video_path: Input video with voice
        output_path: Output video with music added
        music_path: Custom music file (or None to download)
        music_style: Style if downloading (upbeat, chill, dramatic, funny)
        music_volume: Base music volume (0.0-1.0)
        duck_threshold: Voice detection threshold
        duck_ratio: How much to reduce music during speech
    """
    ffmpeg = get_ffmpeg_path()
    
    # Get or download music
    if not music_path:
        music_path = download_music_if_needed(music_style)
    
    if not music_path or not music_path.exists():
        logger.warning("No music available, copying original")
        import shutil
        shutil.copy(video_path, output_path)
        return output_path
    
    # Get video duration
    probe_cmd = [
        ffmpeg.replace('ffmpeg', 'ffprobe'),
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        str(video_path)
    ]
    
    try:
        result = subprocess.run(probe_cmd, capture_output=True, text=True)
        duration = float(result.stdout.strip())
    except:
        duration = 60.0
    
    # Build FFmpeg command with sidechaining for ducking
    # This uses the voice audio to control the music volume
    filter_complex = f'''
        [1:a]aloop=loop=-1:size=2e+09,atrim=0:{duration},volume={music_volume}[music];
        [0:a]asplit=2[voice][voice_sc];
        [music][voice_sc]sidechaincompress=threshold={duck_threshold}:ratio={duck_ratio}:attack=50:release=300[ducked_music];
        [voice][ducked_music]amix=inputs=2:duration=first:weights=1 0.8[aout]
    '''
    
    cmd = [
        ffmpeg, '-y',
        '-i', str(video_path),
        '-stream_loop', '-1',
        '-i', str(music_path),
        '-filter_complex', filter_complex,
        '-map', '0:v',
        '-map', '[aout]',
        '-c:v', 'copy',
        '-c:a', 'aac',
        '-b:a', '192k',
        '-t', str(duration),
        str(output_path)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            # Fallback to simpler mixing without ducking
            logger.warning("Ducking failed, using simple mix")
            return add_simple_music(video_path, output_path, music_path, music_volume, duration)
        return output_path
    except Exception as e:
        logger.error(f"Music mixing failed: {e}")
        import shutil
        shutil.copy(video_path, output_path)
        return output_path


def add_simple_music(
    video_path: Path,
    output_path: Path,
    music_path: Path,
    volume: float = 0.12,
    duration: float = None,
) -> Path:
    """Simple music overlay without ducking (fallback)."""
    ffmpeg = get_ffmpeg_path()
    
    cmd = [
        ffmpeg, '-y',
        '-i', str(video_path),
        '-stream_loop', '-1',
        '-i', str(music_path),
        '-filter_complex', f'''
            [1:a]volume={volume},afade=t=in:st=0:d=2,afade=t=out:st={duration-2}:d=2[music];
            [0:a][music]amix=inputs=2:duration=first:weights=1 0.7[aout]
        ''',
        '-map', '0:v',
        '-map', '[aout]',
        '-c:v', 'copy',
        '-c:a', 'aac',
        '-b:a', '192k',
        str(output_path)
    ]
    
    try:
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path
    except Exception as e:
        logger.error(f"Simple music failed: {e}")
        import shutil
        shutil.copy(video_path, output_path)
        return output_path


def add_sound_effect_at_time(
    video_path: Path,
    output_path: Path,
    effect_path: Path,
    timestamp: float,
    volume: float = 0.7,
) -> Path:
    """Add a sound effect at a specific timestamp."""
    ffmpeg = get_ffmpeg_path()
    
    cmd = [
        ffmpeg, '-y',
        '-i', str(video_path),
        '-i', str(effect_path),
        '-filter_complex', f'''
            [1:a]volume={volume},adelay={int(timestamp*1000)}|{int(timestamp*1000)}[sfx];
            [0:a][sfx]amix=inputs=2:duration=first[aout]
        ''',
        '-map', '0:v',
        '-map', '[aout]',
        '-c:v', 'copy',
        '-c:a', 'aac',
        '-b:a', '192k',
        str(output_path)
    ]
    
    try:
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path
    except Exception as e:
        logger.error(f"Sound effect failed: {e}")
        import shutil
        shutil.copy(video_path, output_path)
        return output_path


def create_transition_video(
    clip1_path: Path,
    clip2_path: Path,
    output_path: Path,
    transition_type: str = "fade",
    transition_duration: float = 0.5,
    add_whoosh: bool = True,
) -> Path:
    """
    Create a video with transition between two clips.
    
    Transition types:
    - fade: Cross-fade
    - wipe: Wipe left to right
    - zoom: Zoom transition
    - slide: Slide transition
    """
    ffmpeg = get_ffmpeg_path()
    
    # Get durations
    def get_duration(path):
        cmd = [
            ffmpeg.replace('ffmpeg', 'ffprobe'),
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            str(path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return float(result.stdout.strip())
    
    dur1 = get_duration(clip1_path)
    dur2 = get_duration(clip2_path)
    
    # Calculate offset for transition
    offset = dur1 - transition_duration
    
    # Build transition filter
    if transition_type == "fade":
        xfade_filter = f"xfade=transition=fade:duration={transition_duration}:offset={offset}"
    elif transition_type == "wipe":
        xfade_filter = f"xfade=transition=wipeleft:duration={transition_duration}:offset={offset}"
    elif transition_type == "zoom":
        xfade_filter = f"xfade=transition=zoomin:duration={transition_duration}:offset={offset}"
    elif transition_type == "slide":
        xfade_filter = f"xfade=transition=slideleft:duration={transition_duration}:offset={offset}"
    else:
        xfade_filter = f"xfade=transition=fade:duration={transition_duration}:offset={offset}"
    
    # Audio crossfade
    audio_fade = f"acrossfade=d={transition_duration}:c1=tri:c2=tri"
    
    cmd = [
        ffmpeg, '-y',
        '-i', str(clip1_path),
        '-i', str(clip2_path),
        '-filter_complex', f'''
            [0:v][1:v]{xfade_filter}[vout];
            [0:a][1:a]{audio_fade}[aout]
        ''',
        '-map', '[vout]',
        '-map', '[aout]',
        '-c:v', 'libx264',
        '-preset', 'fast',
        '-crf', '23',
        '-c:a', 'aac',
        '-b:a', '192k',
        str(output_path)
    ]
    
    try:
        subprocess.run(cmd, capture_output=True, check=True)
        
        # Add whoosh sound at transition point if requested
        if add_whoosh:
            whoosh_path = ASSETS_DIR / "whoosh_temp.mp3"
            if generate_whoosh_sound(whoosh_path):
                temp_output = output_path.with_stem(output_path.stem + "_with_sfx")
                add_sound_effect_at_time(output_path, temp_output, whoosh_path, offset, volume=0.5)
                temp_output.rename(output_path)
                whoosh_path.unlink(missing_ok=True)
        
        return output_path
    except Exception as e:
        logger.error(f"Transition creation failed: {e}")
        # Fallback: just concatenate
        return concatenate_clips([clip1_path, clip2_path], output_path)


def concatenate_clips(
    clip_paths: List[Path],
    output_path: Path,
    add_transitions: bool = False,
    transition_type: str = "fade",
) -> Path:
    """Concatenate multiple clips, optionally with transitions."""
    ffmpeg = get_ffmpeg_path()
    
    if len(clip_paths) == 0:
        raise ValueError("No clips to concatenate")
    
    if len(clip_paths) == 1:
        import shutil
        shutil.copy(clip_paths[0], output_path)
        return output_path
    
    if add_transitions and len(clip_paths) == 2:
        return create_transition_video(
            clip_paths[0], clip_paths[1], output_path,
            transition_type=transition_type
        )
    
    # For more clips or no transitions, use concat demuxer
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        for clip in clip_paths:
            f.write(f"file '{clip}'\n")
        concat_file = f.name
    
    cmd = [
        ffmpeg, '-y',
        '-f', 'concat',
        '-safe', '0',
        '-i', concat_file,
        '-c', 'copy',
        str(output_path)
    ]
    
    try:
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path
    except Exception as e:
        logger.error(f"Concatenation failed: {e}")
        # Return first clip as fallback
        import shutil
        shutil.copy(clip_paths[0], output_path)
        return output_path
    finally:
        Path(concat_file).unlink(missing_ok=True)


def add_viral_audio_package(
    video_path: Path,
    output_path: Path,
    music_style: str = "upbeat",
    add_whoosh_at_start: bool = True,
    add_bass_on_hook: bool = True,
    hook_timestamp: float = 0.5,
) -> Path:
    """
    Apply full viral audio treatment to a video:
    1. Background music with voice ducking
    2. Whoosh sound at start
    3. Bass drop on hook moment
    """
    import shutil
    
    # Step 1: Add background music
    temp1 = video_path.with_stem(video_path.stem + "_music")
    add_background_music_with_ducking(
        video_path, temp1,
        music_style=music_style,
        music_volume=0.12,  # Keep music subtle
    )
    
    current = temp1
    
    # Step 2: Add whoosh at start
    if add_whoosh_at_start:
        whoosh_path = ASSETS_DIR / "whoosh_start.mp3"
        if generate_whoosh_sound(whoosh_path, duration=0.4):
            temp2 = video_path.with_stem(video_path.stem + "_whoosh")
            add_sound_effect_at_time(current, temp2, whoosh_path, 0.1, volume=0.6)
            if current != video_path:
                current.unlink(missing_ok=True)
            current = temp2
            whoosh_path.unlink(missing_ok=True)
    
    # Step 3: Add bass drop on hook
    if add_bass_on_hook:
        bass_path = ASSETS_DIR / "bass_hook.mp3"
        if generate_bass_drop(bass_path, duration=0.25):
            temp3 = video_path.with_stem(video_path.stem + "_bass")
            add_sound_effect_at_time(current, temp3, bass_path, hook_timestamp, volume=0.7)
            if current != video_path:
                current.unlink(missing_ok=True)
            current = temp3
            bass_path.unlink(missing_ok=True)
    
    # Move to final output
    if current != output_path:
        shutil.move(current, output_path)
    
    return output_path
