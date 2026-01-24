"""Render module - final video assembly with burned-in captions and effects."""

import logging
import os
import subprocess
from pathlib import Path
from typing import Optional

from .crop import check_ffmpeg, get_ffmpeg_install_instructions, get_video_info, build_crop_filter, detect_motion_center, get_ffmpeg_path

logger = logging.getLogger(__name__)

# Use fast encoding preset for cloud deployments (detected by RAILWAY or similar env vars)
IS_CLOUD = os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('RENDER') or os.environ.get('FLY_APP_NAME')


def render_final_clip(
    source_video: str | Path,
    output_path: str | Path,
    start_time: float,
    end_time: float,
    ass_path: Optional[str | Path] = None,
    crop_vertical: bool = True,
    auto_center: bool = True,
    enable_effects: bool = True,
    scene_change_interval: float = 1.5,
    color_grade: str = "viral",
) -> Path:
    """
    Render a final clip with cropping, captions, and AI-style effects.
    
    Features:
    - Vertical crop with auto-centering
    - Dynamic scene changes (zoom in/out every 1.5s)
    - Color grading for viral look
    - Burned-in captions
    """
    if not check_ffmpeg():
        raise RuntimeError(get_ffmpeg_install_instructions())
    
    source_video = Path(source_video)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    duration = end_time - start_time
    video_info = get_video_info(source_video)
    
    filters = []
    
    if crop_vertical:
        center_x = None
        if auto_center:
            center_x = detect_motion_center(source_video, start_time, min(duration, 5))
        
        crop_filter = build_crop_filter(video_info, center_x)
        filters.append(crop_filter)
    
    # Add scene change zoom effect (every 1.5 seconds) - ALWAYS enabled
    if enable_effects:
        # Use simple scale oscillation for zoom effect - works better on Railway
        # This creates subtle zoom in/out every 1.5 seconds
        # Using scale filter which is more compatible than zoompan
        interval = scene_change_interval
        # Scale between 100% and 106% with smooth sine wave
        zoom_filter = (
            f"scale=iw*(1.0+0.06*sin(2*3.14159*t/{interval})):"
            f"ih*(1.0+0.06*sin(2*3.14159*t/{interval})),"
            f"crop=1080:1920"
        )
        filters.append(zoom_filter)
    
    # Add color grading for viral look
    if enable_effects:
        color_grades = {
            "viral": "eq=contrast=1.12:brightness=0.02:saturation=1.2",
            "cinematic": "colorbalance=rs=0.08:gs=-0.03:bs=-0.08,eq=contrast=1.1:saturation=1.05",
            "clean": "eq=contrast=1.05:brightness=0.01:saturation=1.08",
            "moody": "eq=contrast=1.08:brightness=-0.01:saturation=0.95",
        }
        if color_grade in color_grades:
            filters.append(color_grades[color_grade])
    
    if ass_path:
        ass_path = Path(ass_path)
        if ass_path.exists():
            ass_escaped = str(ass_path).replace('\\', '/').replace(':', '\\:').replace("'", "\\'")
            filters.append(f"ass='{ass_escaped}'")
    
    # Use faster encoding preset for cloud (Railway etc) to avoid timeouts
    # ultrafast is ~5x faster than medium but larger file size
    preset = 'ultrafast' if IS_CLOUD else 'medium'
    
    cmd = [
        get_ffmpeg_path(), '-y',
        '-ss', str(start_time),
        '-i', str(source_video),
        '-t', str(duration),
    ]
    
    if filters:
        cmd.extend(['-vf', ','.join(filters)])
    
    cmd.extend([
        '-c:v', 'libx264',
        '-preset', preset,
        '-crf', '18',  # Lower = better quality (18 is visually lossless)
        '-c:a', 'aac',
        '-b:a', '128k',
        '-movflags', '+faststart',
        str(output_path)
    ])
    
    logger.info(f"Using encoding preset: {preset}")
    
    logger.info(f"Rendering final clip: {output_path.name}")
    logger.debug(f"Command: {' '.join(cmd)}")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        if ass_path and filters:
            ass_escaped = str(ass_path).replace('\\', '/').replace(':', '\\:').replace("'", "\\'")
            filters[-1] = f"ass={ass_escaped}"
            cmd_idx = cmd.index('-vf') + 1
            cmd[cmd_idx] = ','.join(filters)
            result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg render failed: {result.stderr}")
    
    logger.info(f"Final clip saved: {output_path}")
    return output_path


def create_thumbnail(
    video_path: str | Path,
    output_path: str | Path,
    timestamp: Optional[float] = None,
) -> Path:
    """Create a thumbnail image from a video."""
    if not check_ffmpeg():
        raise RuntimeError(get_ffmpeg_install_instructions())
    
    video_path = Path(video_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    if timestamp is None:
        timestamp = 1.0
    
    cmd = [
        get_ffmpeg_path(), '-y',
        '-ss', str(timestamp),
        '-i', str(video_path),
        '-vframes', '1',
        '-q:v', '2',
        str(output_path)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        raise RuntimeError(f"Thumbnail creation failed: {result.stderr}")
    
    return output_path
