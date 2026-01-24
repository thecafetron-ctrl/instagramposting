"""Render module - final video assembly with burned-in captions."""

import logging
import subprocess
from pathlib import Path
from typing import Optional

from .crop import check_ffmpeg, get_ffmpeg_install_instructions, get_video_info, build_crop_filter, detect_motion_center

logger = logging.getLogger(__name__)


def render_final_clip(
    source_video: str | Path,
    output_path: str | Path,
    start_time: float,
    end_time: float,
    ass_path: Optional[str | Path] = None,
    crop_vertical: bool = True,
    auto_center: bool = True,
) -> Path:
    """Render a final clip with cropping and optional captions in one pass."""
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
    
    if ass_path:
        ass_path = Path(ass_path)
        if ass_path.exists():
            ass_escaped = str(ass_path).replace('\\', '/').replace(':', '\\:').replace("'", "\\'")
            filters.append(f"ass='{ass_escaped}'")
    
    cmd = [
        'ffmpeg', '-y',
        '-ss', str(start_time),
        '-i', str(source_video),
        '-t', str(duration),
    ]
    
    if filters:
        cmd.extend(['-vf', ','.join(filters)])
    
    cmd.extend([
        '-c:v', 'libx264',
        '-preset', 'medium',
        '-crf', '23',
        '-c:a', 'aac',
        '-b:a', '128k',
        '-movflags', '+faststart',
        str(output_path)
    ])
    
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
        'ffmpeg', '-y',
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
