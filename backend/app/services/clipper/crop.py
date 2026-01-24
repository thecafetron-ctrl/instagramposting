"""Crop module - vertical video cropping with auto-center."""

import json
import logging
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

OUTPUT_WIDTH = 1080
OUTPUT_HEIGHT = 1920


@dataclass
class VideoInfo:
    """Video metadata."""
    width: int
    height: int
    duration: float
    fps: float
    has_audio: bool


def check_ffmpeg() -> bool:
    """Check if FFmpeg is installed and accessible."""
    return shutil.which('ffmpeg') is not None


def get_ffmpeg_install_instructions() -> str:
    """Get FFmpeg installation instructions."""
    return """
FFmpeg is required but not found. Please install it:

macOS:
    brew install ffmpeg

Windows:
    choco install ffmpeg OR winget install ffmpeg

Linux:
    sudo apt install ffmpeg
"""


def get_video_info(video_path: str | Path) -> VideoInfo:
    """Get video metadata using ffprobe."""
    if not check_ffmpeg():
        raise RuntimeError(get_ffmpeg_install_instructions())
    
    video_path = Path(video_path)
    
    cmd = [
        'ffprobe',
        '-v', 'quiet',
        '-print_format', 'json',
        '-show_format',
        '-show_streams',
        str(video_path)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")
    
    data = json.loads(result.stdout)
    
    video_stream = None
    has_audio = False
    for stream in data.get('streams', []):
        if stream['codec_type'] == 'video' and video_stream is None:
            video_stream = stream
        elif stream['codec_type'] == 'audio':
            has_audio = True
    
    if not video_stream:
        raise RuntimeError("No video stream found")
    
    fps_str = video_stream.get('r_frame_rate', '30/1')
    if '/' in fps_str:
        num, den = fps_str.split('/')
        fps = float(num) / float(den) if float(den) != 0 else 30.0
    else:
        fps = float(fps_str)
    
    return VideoInfo(
        width=int(video_stream['width']),
        height=int(video_stream['height']),
        duration=float(data['format'].get('duration', 0)),
        fps=fps,
        has_audio=has_audio
    )


def calculate_crop_region(
    video_info: VideoInfo,
    center_x: Optional[float] = None,
) -> tuple[int, int, int, int]:
    """Calculate crop region for vertical output."""
    src_w, src_h = video_info.width, video_info.height
    target_ratio = OUTPUT_WIDTH / OUTPUT_HEIGHT
    src_ratio = src_w / src_h
    
    if src_ratio > target_ratio:
        crop_h = src_h
        crop_w = int(src_h * target_ratio)
    else:
        crop_w = src_w
        crop_h = int(src_w / target_ratio)
    
    if center_x is not None:
        crop_x = int(center_x * src_w - crop_w / 2)
        crop_x = max(0, min(crop_x, src_w - crop_w))
    else:
        crop_x = (src_w - crop_w) // 2
    
    crop_y = (src_h - crop_h) // 2
    
    return crop_x, crop_y, crop_w, crop_h


def detect_motion_center(
    video_path: str | Path,
    start_time: float = 0,
    duration: float = 5,
) -> float:
    """Detect the horizontal center of motion in a video segment."""
    if not check_ffmpeg():
        logger.warning("FFmpeg not available, using center crop")
        return 0.5
    
    video_path = Path(video_path)
    video_info = get_video_info(video_path)
    
    cmd = [
        'ffmpeg',
        '-ss', str(start_time),
        '-t', str(duration),
        '-i', str(video_path),
        '-vf', 'cropdetect=24:16:0',
        '-f', 'null',
        '-'
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    crop_values = []
    for line in result.stderr.split('\n'):
        match = re.search(r'crop=(\d+):(\d+):(\d+):(\d+)', line)
        if match:
            w, h, x, y = map(int, match.groups())
            center = (x + w / 2) / video_info.width
            crop_values.append(center)
    
    if crop_values:
        avg_center = sum(crop_values) / len(crop_values)
        logger.debug(f"Detected motion center: {avg_center:.3f}")
        return avg_center
    
    return 0.5


def build_crop_filter(
    video_info: VideoInfo,
    center_x: Optional[float] = None,
) -> str:
    """Build FFmpeg filter string for vertical crop."""
    crop_x, crop_y, crop_w, crop_h = calculate_crop_region(video_info, center_x)
    
    filter_str = (
        f"crop={crop_w}:{crop_h}:{crop_x}:{crop_y},"
        f"scale={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:flags=lanczos"
    )
    
    return filter_str
