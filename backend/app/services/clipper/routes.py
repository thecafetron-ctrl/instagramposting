"""API routes for video clipper and captioner."""

import asyncio
import json
import logging
import os
import secrets
import shutil
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime

from fastapi import APIRouter, File, UploadFile, HTTPException, BackgroundTasks, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .pipeline import ClipperPipeline, PipelineConfig, PipelineResult
from .crop import check_ffmpeg, get_ffmpeg_install_instructions, get_ffmpeg_path
from .captions import STYLE_PRESETS
from .viral_analyzer import analyze_transcript_for_virality, get_video_cache_key, ViralMoment
from .ai_editor import AIVideoEditor, find_best_clip_boundaries, detect_hook_moments, generate_enhanced_ass_subtitle

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/clipper", tags=["Video Clipper"])

# Store for job progress and control
_job_progress = {}
_job_results = {}
_job_cancel_flags = {}  # Track which jobs should be cancelled
_job_threads = {}  # Track running threads

# Video cache - maps cache_key to job_id that has the video
_video_cache: Dict[str, str] = {}

# Viral analysis results - maps job_id to list of ViralMoment candidates
_viral_candidates: Dict[str, List[dict]] = {}

# Clip history - persisted to disk
_clip_history: List[dict] = []
CLIP_HISTORY_FILE = Path("generated_clips/clip_history.json")

# Output directory
CLIPS_OUTPUT_DIR = Path("generated_clips")
CLIPS_OUTPUT_DIR.mkdir(exist_ok=True)

# Load clip history on startup
def load_clip_history():
    global _clip_history
    if CLIP_HISTORY_FILE.exists():
        try:
            with open(CLIP_HISTORY_FILE) as f:
                _clip_history = json.load(f)
        except:
            _clip_history = []

def save_clip_history():
    global _clip_history
    try:
        with open(CLIP_HISTORY_FILE, "w") as f:
            json.dump(_clip_history, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save clip history: {e}")

def add_to_clip_history(job_id: str, clips: List[dict], youtube_url: str = None):
    """Add completed clips to history."""
    global _clip_history
    try:
        entry = {
            "job_id": job_id,
            "created_at": datetime.now().isoformat(),
            "youtube_url": youtube_url,
            "clips": clips,
        }
        _clip_history.insert(0, entry)  # Add to beginning (newest first)
        # Keep only last 50 jobs
        if len(_clip_history) > 50:
            _clip_history = _clip_history[:50]
        save_clip_history()
    except Exception as e:
        logger.error(f"Failed to add to clip history: {e}")

load_clip_history()


class ClipperConfigRequest(BaseModel):
    """Request configuration for video clipping."""
    num_clips: int = 10
    min_duration: float = 20.0
    max_duration: float = 60.0
    pause_threshold: float = 0.7
    caption_style: str = "default"
    whisper_model: str = "tiny"  # Default to tiny for cloud deployments with limited RAM
    burn_captions: bool = True
    crop_vertical: bool = True
    auto_center: bool = True


class ClipperJobResponse(BaseModel):
    """Response for clip job status."""
    job_id: str
    status: str
    progress: float
    stage: str
    detail: Optional[str] = None
    error: Optional[str] = None
    result: Optional[dict] = None


class ClipInfo(BaseModel):
    """Information about a generated clip."""
    index: int
    video_url: str
    thumbnail_url: Optional[str]
    start_time: float
    end_time: float
    duration: float
    score: float
    text: str


class ClipperResultResponse(BaseModel):
    """Response with clipping results."""
    job_id: str
    success: bool
    source_video: str
    total_duration: float
    processing_time: float
    clips: List[ClipInfo]
    transcript_url: Optional[str]
    error: Optional[str] = None


def update_job_progress(job_id: str, status: str, progress: float, stage: str, detail: str = None, error: str = None):
    """Update job progress with logging."""
    _job_progress[job_id] = {
        "status": status,
        "progress": progress,
        "stage": stage,
        "detail": detail,
        "error": error,
        "updated_at": datetime.now().isoformat()
    }
    logger.info(f"[Job {job_id}] {progress*100:.0f}% - {stage}" + (f" ({detail})" if detail else ""))


def is_job_cancelled(job_id: str) -> bool:
    """Check if a job has been cancelled."""
    return _job_cancel_flags.get(job_id, False)


@router.get("/status")
async def check_clipper_status():
    """Check if video clipper dependencies are available."""
    issues = []
    
    # Check FFmpeg with full path detection
    ffmpeg_ok = check_ffmpeg()
    ffmpeg_path = get_ffmpeg_path() if ffmpeg_ok else None
    
    if ffmpeg_ok:
        issues.append({
            "name": "FFmpeg",
            "status": "installed",
            "path": ffmpeg_path
        })
    else:
        issues.append({
            "name": "FFmpeg",
            "status": "missing",
            "instructions": get_ffmpeg_install_instructions()
        })
    
    # Check faster-whisper
    try:
        import faster_whisper
        issues.append({"name": "faster-whisper", "status": "installed"})
    except ImportError:
        issues.append({
            "name": "faster-whisper",
            "status": "missing",
            "instructions": "pip install faster-whisper"
        })
    
    # Check yt-dlp
    try:
        import yt_dlp
        issues.append({"name": "yt-dlp", "status": "installed"})
    except ImportError:
        issues.append({
            "name": "yt-dlp",
            "status": "missing", 
            "instructions": "pip install yt-dlp"
        })
    
    all_ok = all(d["status"] == "installed" for d in issues)
    
    return {
        "status": "ready" if all_ok else "missing_dependencies",
        "dependencies": issues
    }


@router.get("/styles")
async def get_caption_styles():
    """Get available caption style presets."""
    return [
        {"id": k, "name": k.replace("_", " ").title()}
        for k in STYLE_PRESETS.keys()
    ]


@router.post("/upload")
async def upload_video(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
    num_clips: int = Form(10),
    min_duration: float = Form(20.0),
    max_duration: float = Form(60.0),
    pause_threshold: float = Form(0.7),
    caption_style: str = Form("default"),
    whisper_model: str = Form("tiny"),  # Default to tiny for cloud deployments
    burn_captions: bool = Form(True),
    crop_vertical: bool = Form(True),
    auto_center: bool = Form(True),
):
    """
    Upload a video and start the clipping pipeline.
    
    Returns a job_id to track progress.
    """
    # Validate dependencies
    if not check_ffmpeg():
        raise HTTPException(
            status_code=503,
            detail="FFmpeg is not installed. " + get_ffmpeg_install_instructions()
        )
    
    try:
        import faster_whisper
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="faster-whisper is not installed. Run: pip install faster-whisper"
        )
    
    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    ext = Path(file.filename).suffix.lower()
    if ext not in ['.mp4', '.mov', '.avi', '.mkv', '.webm']:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Use MP4, MOV, AVI, MKV, or WebM."
        )
    
    # Create job ID
    job_id = str(uuid.uuid4())[:8]
    
    # Save uploaded file
    upload_dir = CLIPS_OUTPUT_DIR / job_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    video_path = upload_dir / f"input{ext}"
    
    try:
        update_job_progress(job_id, "processing", 0.01, "Receiving upload", f"Saving {file.filename}")
        with open(video_path, "wb") as f:
            content = await file.read()
            f.write(content)
        update_job_progress(job_id, "processing", 0.05, "Upload complete", f"Saved {len(content)/1024/1024:.1f}MB")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    
    # Initialize cancel flag
    _job_cancel_flags[job_id] = False
    
    # Build config
    config = PipelineConfig(
        num_clips=num_clips,
        min_duration=min_duration,
        max_duration=max_duration,
        pause_threshold=pause_threshold,
        caption_style=caption_style,
        whisper_model=whisper_model,
        burn_captions=burn_captions,
        crop_vertical=crop_vertical,
        auto_center=auto_center,
    )
    
    # Start processing in a dedicated thread
    thread = threading.Thread(
        target=run_clipper_job_sync,
        args=(job_id, str(video_path), str(upload_dir), config),
        daemon=True
    )
    _job_threads[job_id] = thread
    thread.start()
    
    return {
        "job_id": job_id,
        "status": "processing",
        "message": "Video uploaded. Processing started.",
    }


class YouTubeRequest(BaseModel):
    """Request for processing a YouTube video."""
    url: str
    num_clips: int = 10
    min_duration: float = 20.0
    max_duration: float = 60.0
    pause_threshold: float = 0.7
    caption_style: str = "default"
    whisper_model: str = "tiny"  # Default to tiny for cloud deployments
    burn_captions: bool = True
    crop_vertical: bool = True
    auto_center: bool = True


def download_youtube_video(url: str, output_dir: Path, job_id: str) -> str:
    """Download a YouTube video using yt-dlp with progress tracking."""
    import yt_dlp
    
    output_path = output_dir / "input.mp4"
    
    def progress_hook(d):
        """Track download progress."""
        if is_job_cancelled(job_id):
            raise Exception("Job cancelled by user")
        
        if d['status'] == 'downloading':
            try:
                downloaded = d.get('downloaded_bytes', 0)
                total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                speed = d.get('speed', 0)
                eta = d.get('eta', 0)
                
                if total > 0:
                    pct = downloaded / total
                    progress = 0.02 + (pct * 0.08)  # 2% to 10%
                    
                    speed_str = f"{speed/1024/1024:.1f}MB/s" if speed else "calculating..."
                    eta_str = f"{eta}s" if eta else "..."
                    detail = f"Downloaded {downloaded/1024/1024:.1f}MB / {total/1024/1024:.1f}MB ({speed_str}, ETA: {eta_str})"
                else:
                    progress = 0.05
                    detail = f"Downloaded {downloaded/1024/1024:.1f}MB"
                
                update_job_progress(job_id, "processing", progress, "Downloading from YouTube", detail)
            except:
                pass
        elif d['status'] == 'finished':
            update_job_progress(job_id, "processing", 0.10, "Download complete", "Merging audio/video...")
    
    ydl_opts = {
        'format': 'best[height<=1080]/bestvideo[height<=1080]+bestaudio/best',
        'outtmpl': str(output_path.with_suffix('')),
        'merge_output_format': 'mp4',
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'progress_hooks': [progress_hook],
        'socket_timeout': 60,
        'retries': 10,
        'fragment_retries': 10,
        # Fix for 403 Forbidden errors - use android_creator client
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.6261.119 Mobile Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        },
        'extractor_args': {
            'youtube': {
                'player_client': ['android_creator', 'android', 'web'],
            }
        },
        'nocheckcertificate': True,
    }
    
    update_job_progress(job_id, "processing", 0.02, "Connecting to YouTube", "Fetching video info...")
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # First extract info to get video details
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'Unknown')
            duration = info.get('duration', 0)
            
            update_job_progress(
                job_id, "processing", 0.03, 
                "Starting download", 
                f'"{title[:50]}..." ({duration//60}m {duration%60}s)'
            )
            
            # Check cancellation before download
            if is_job_cancelled(job_id):
                raise Exception("Job cancelled by user")
            
            # Now download
            ydl.download([url])
    except Exception as e:
        if "cancelled" in str(e).lower():
            raise
        logger.error(f"yt-dlp download error: {e}")
        raise Exception(f"YouTube download failed: {str(e)}")
    
    # Find the downloaded file
    for ext in ['.mp4', '.mkv', '.webm']:
        candidate = output_dir / f"input{ext}"
        if candidate.exists():
            return str(candidate)
    
    if output_path.exists():
        return str(output_path)
    
    raise FileNotFoundError("Downloaded video file not found. YouTube may have blocked the download.")


@router.post("/youtube")
async def process_youtube_video(
    request: YouTubeRequest,
    background_tasks: BackgroundTasks = None,
):
    """
    Download and process a YouTube video.
    
    Accepts YouTube URLs like:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID
    - https://www.youtube.com/shorts/VIDEO_ID
    
    Returns a job_id to track progress.
    """
    # Validate dependencies
    if not check_ffmpeg():
        raise HTTPException(
            status_code=503,
            detail="FFmpeg is not installed. " + get_ffmpeg_install_instructions()
        )
    
    try:
        import faster_whisper
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="faster-whisper is not installed. Run: pip install faster-whisper"
        )
    
    try:
        import yt_dlp
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="yt-dlp is not installed. Run: pip install yt-dlp"
        )
    
    # Validate URL
    url = request.url.strip()
    if not any(domain in url for domain in ['youtube.com', 'youtu.be']):
        raise HTTPException(
            status_code=400,
            detail="Invalid URL. Please provide a YouTube video URL."
        )
    
    # Create job ID
    job_id = str(uuid.uuid4())[:8]
    
    # Create output directory
    output_dir = CLIPS_OUTPUT_DIR / job_id
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize job
    _job_cancel_flags[job_id] = False
    update_job_progress(job_id, "processing", 0.01, "Initializing", "Starting YouTube download...")
    
    # Build config
    config = PipelineConfig(
        num_clips=request.num_clips,
        min_duration=request.min_duration,
        max_duration=request.max_duration,
        pause_threshold=request.pause_threshold,
        caption_style=request.caption_style,
        whisper_model=request.whisper_model,
        burn_captions=request.burn_captions,
        crop_vertical=request.crop_vertical,
        auto_center=request.auto_center,
    )
    
    # Start processing in a dedicated thread
    thread = threading.Thread(
        target=run_youtube_job_sync,
        args=(job_id, url, str(output_dir), config),
        daemon=True
    )
    _job_threads[job_id] = thread
    thread.start()
    
    return {
        "job_id": job_id,
        "status": "processing",
        "message": "YouTube video download started. Processing will begin after download.",
    }


def run_youtube_job_sync(
    job_id: str,
    url: str,
    output_dir: str,
    config: PipelineConfig
):
    """Synchronous YouTube job runner with cancellation support."""
    try:
        if is_job_cancelled(job_id):
            update_job_progress(job_id, "cancelled", 0, "Cancelled", "Job was cancelled before starting")
            return
        
        # Download video
        video_path = download_youtube_video(url, Path(output_dir), job_id)
        
        if is_job_cancelled(job_id):
            update_job_progress(job_id, "cancelled", 0, "Cancelled", "Job was cancelled after download")
            return
        
        update_job_progress(job_id, "processing", 0.12, "Download complete", "Starting video processing...")
        
        # Now run the regular clipper job
        run_clipper_job_sync(job_id, video_path, output_dir, config)
        
    except Exception as e:
        error_msg = str(e)
        if "cancelled" in error_msg.lower():
            update_job_progress(job_id, "cancelled", 0, "Cancelled", "Job was cancelled by user")
        else:
            logger.exception(f"YouTube job {job_id} failed")
            update_job_progress(job_id, "failed", 0, "Error", error=error_msg)


@router.post("/process-local")
async def process_local_video(
    video_path: str,
    config: ClipperConfigRequest,
    background_tasks: BackgroundTasks = None,
):
    """
    Process a video file already on the server.
    
    Returns a job_id to track progress.
    """
    if not Path(video_path).exists():
        raise HTTPException(status_code=404, detail=f"Video not found: {video_path}")
    
    job_id = str(uuid.uuid4())[:8]
    
    output_dir = CLIPS_OUTPUT_DIR / job_id
    output_dir.mkdir(parents=True, exist_ok=True)
    
    _job_cancel_flags[job_id] = False
    update_job_progress(job_id, "processing", 0.01, "Initializing", "Starting video processing...")
    
    pipeline_config = PipelineConfig(
        num_clips=config.num_clips,
        min_duration=config.min_duration,
        max_duration=config.max_duration,
        pause_threshold=config.pause_threshold,
        caption_style=config.caption_style,
        whisper_model=config.whisper_model,
        burn_captions=config.burn_captions,
        crop_vertical=config.crop_vertical,
        auto_center=config.auto_center,
    )
    
    thread = threading.Thread(
        target=run_clipper_job_sync,
        args=(job_id, video_path, str(output_dir), pipeline_config),
        daemon=True
    )
    _job_threads[job_id] = thread
    thread.start()
    
    return {
        "job_id": job_id,
        "status": "processing",
        "message": "Processing started.",
    }


def run_clipper_job_sync(
    job_id: str,
    video_path: str,
    output_dir: str,
    config: PipelineConfig
):
    """Synchronous clipper job runner with detailed progress and cancellation."""
    
    def progress_callback(stage: str, progress: float):
        """Progress callback with cancellation check."""
        if is_job_cancelled(job_id):
            raise Exception("Job cancelled by user")
        
        # Map pipeline stages to more descriptive messages
        stage_details = {
            "Transcribing video": "Loading Whisper model and transcribing audio...",
            "Transcription complete": "Speech-to-text finished",
            "Segmenting transcript": "Finding natural break points...",
            "Segmentation complete": "Identified candidate clips",
            "Scoring clips": "Analyzing for highlight moments...",
            "Scoring complete": "Ranked clips by engagement potential",
            "Rendering clips": "Processing video with FFmpeg...",
            "Pipeline complete": "All clips generated successfully!",
        }
        
        # Adjust progress to account for download phase (which ends at ~10%)
        adjusted_progress = 0.12 + (progress * 0.88)
        detail = stage_details.get(stage, stage)
        
        update_job_progress(job_id, "processing", adjusted_progress, stage, detail)
    
    try:
        if is_job_cancelled(job_id):
            update_job_progress(job_id, "cancelled", 0, "Cancelled", "Job was cancelled")
            return
        
        update_job_progress(job_id, "processing", 0.12, "Initializing pipeline", "Loading video file...")
        
        pipeline = ClipperPipeline(config, progress_callback=progress_callback)
        result = pipeline.run(video_path, output_dir)
        
        if is_job_cancelled(job_id):
            update_job_progress(job_id, "cancelled", 0, "Cancelled", "Job was cancelled")
            return
        
        if result.success:
            update_job_progress(
                job_id, "completed", 1.0, "Complete",
                f"Generated {len(result.clips)} clips in {result.processing_time:.1f}s"
            )
            _job_results[job_id] = result
        else:
            update_job_progress(job_id, "failed", 0, "Failed", error=result.error)
            _job_results[job_id] = result
            
    except Exception as e:
        error_msg = str(e)
        if "cancelled" in error_msg.lower():
            update_job_progress(job_id, "cancelled", 0, "Cancelled", "Job was cancelled by user")
        else:
            logger.exception(f"Job {job_id} failed")
            update_job_progress(job_id, "failed", 0, "Error", error=error_msg)


@router.get("/job/{job_id}")
async def get_job_status(job_id: str) -> ClipperJobResponse:
    """Get the status of a clipping job."""
    if job_id not in _job_progress:
        raise HTTPException(status_code=404, detail="Job not found")
    
    progress = _job_progress[job_id]
    
    result_data = None
    if progress["status"] == "completed" and job_id in _job_results:
        result = _job_results[job_id]
        result_data = {
            "clips_count": len(result.clips),
            "total_duration": result.total_duration,
            "processing_time": result.processing_time,
        }
    
    return ClipperJobResponse(
        job_id=job_id,
        status=progress["status"],
        progress=progress["progress"],
        stage=progress["stage"],
        detail=progress.get("detail"),
        error=progress.get("error"),
        result=result_data
    )


@router.post("/job/{job_id}/cancel")
async def cancel_job(job_id: str):
    """Cancel a running job."""
    if job_id not in _job_progress:
        raise HTTPException(status_code=404, detail="Job not found")
    
    progress = _job_progress[job_id]
    
    if progress["status"] not in ["processing", "queued"]:
        return {
            "job_id": job_id,
            "cancelled": False,
            "message": f"Job cannot be cancelled (status: {progress['status']})"
        }
    
    # Set cancel flag
    _job_cancel_flags[job_id] = True
    
    # Update progress immediately
    update_job_progress(job_id, "cancelling", progress["progress"], "Cancelling", "Waiting for current operation to complete...")
    
    return {
        "job_id": job_id,
        "cancelled": True,
        "message": "Cancellation requested. Job will stop after current operation completes."
    }


@router.get("/job/{job_id}/result")
async def get_job_result(job_id: str) -> ClipperResultResponse:
    """Get the full results of a completed clipping job."""
    if job_id not in _job_progress:
        raise HTTPException(status_code=404, detail="Job not found")
    
    progress = _job_progress[job_id]
    
    if progress["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Job not completed. Status: {progress['status']}"
        )
    
    if job_id not in _job_results:
        raise HTTPException(status_code=404, detail="Results not found")
    
    result = _job_results[job_id]
    
    # Build clip info with URLs
    clips = []
    for clip in result.clips:
        video_filename = Path(clip.video_path).name
        thumb_filename = Path(clip.thumbnail_path).name if clip.thumbnail_path else None
        
        clips.append(ClipInfo(
            index=clip.index,
            video_url=f"/api/clipper/clips/{job_id}/{video_filename}",
            thumbnail_url=f"/api/clipper/clips/{job_id}/{thumb_filename}" if thumb_filename else None,
            start_time=clip.start_time,
            end_time=clip.end_time,
            duration=clip.duration,
            score=clip.score,
            text=clip.text,
        ))
    
    return ClipperResultResponse(
        job_id=job_id,
        success=result.success,
        source_video=Path(result.source_video).name,
        total_duration=result.total_duration,
        processing_time=result.processing_time,
        clips=clips,
        transcript_url=f"/api/clipper/clips/{job_id}/transcript.json" if result.transcript_json else None,
        error=result.error,
    )


@router.get("/clips/{job_id}/{filename}")
async def get_clip_file(job_id: str, filename: str):
    """Serve a generated clip or thumbnail."""
    file_path = CLIPS_OUTPUT_DIR / job_id / "clips" / filename
    if not file_path.exists():
        file_path = CLIPS_OUTPUT_DIR / job_id / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    ext = file_path.suffix.lower()
    media_types = {
        '.mp4': 'video/mp4',
        '.mov': 'video/quicktime',
        '.webm': 'video/webm',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.json': 'application/json',
        '.srt': 'text/plain',
    }
    media_type = media_types.get(ext, 'application/octet-stream')
    
    return FileResponse(file_path, media_type=media_type)


@router.delete("/job/{job_id}")
async def delete_job(job_id: str):
    """Delete a job and its output files."""
    # First try to cancel if running
    if job_id in _job_cancel_flags:
        _job_cancel_flags[job_id] = True
    
    job_dir = CLIPS_OUTPUT_DIR / job_id
    
    if job_dir.exists():
        shutil.rmtree(job_dir)
    
    # Clean up tracking dicts
    _job_progress.pop(job_id, None)
    _job_results.pop(job_id, None)
    _job_cancel_flags.pop(job_id, None)
    _job_threads.pop(job_id, None)
    
    return {"status": "deleted", "job_id": job_id}


@router.get("/jobs")
async def list_jobs():
    """List all clipper jobs."""
    jobs = []
    
    for job_id, progress in _job_progress.items():
        job_info = {
            "job_id": job_id,
            "status": progress["status"],
            "progress": progress["progress"],
            "stage": progress["stage"],
            "detail": progress.get("detail"),
            "updated_at": progress.get("updated_at"),
        }
        
        if progress.get("error"):
            job_info["error"] = progress["error"]
        
        if progress["status"] == "completed" and job_id in _job_results:
            result = _job_results[job_id]
            job_info["clips_count"] = len(result.clips)
        
        jobs.append(job_info)
    
    # Sort by most recent first
    jobs.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    
    return {"jobs": jobs}


# ============================================================================
# LOCAL WORKER ENDPOINTS
# These endpoints allow a local worker (your PC) to process jobs
# ============================================================================

# Track registered workers and jobs waiting for workers
_registered_workers: Dict[str, dict] = {}
_worker_queue: List[dict] = []  # Jobs waiting for a worker
_worker_job_configs: Dict[str, dict] = {}  # job_id -> full job config for workers


@router.post("/worker/register")
async def register_worker(data: dict):
    """Register a local worker."""
    worker_id = data.get("worker_id")
    if not worker_id:
        raise HTTPException(status_code=400, detail="worker_id required")
    
    _registered_workers[worker_id] = {
        "worker_id": worker_id,
        "capabilities": data.get("capabilities", []),
        "platform": data.get("platform", "unknown"),
        "registered_at": datetime.now().isoformat(),
        "last_seen": datetime.now().isoformat(),
    }
    
    logger.info(f"Worker registered: {worker_id}")
    
    return {"status": "registered", "worker_id": worker_id}


@router.get("/worker/jobs/pending")
async def get_pending_worker_job(worker_id: str = None):
    """Get a pending job for a local worker to process."""
    if worker_id and worker_id in _registered_workers:
        _registered_workers[worker_id]["last_seen"] = datetime.now().isoformat()
    
    # Find a job that needs worker processing
    for job_id, progress in _job_progress.items():
        # Check for smart jobs ready for worker (download complete)
        if progress.get("mode") == "smart" and progress["status"] == "ready_for_worker":
            # Claim this job
            progress["status"] = "processing"
            progress["worker_id"] = worker_id
            progress["stage"] = "Assigned to worker"
            
            config = _worker_job_configs.get(job_id, {})
            add_job_log(job_id, f"Job claimed by worker: {worker_id}")
            
            return {
                "job": {
                    "job_id": job_id,
                    "job_type": "smart",  # Smart job = transcribe + analyze + render
                    "video_url": config.get("video_url"),
                    "config": config.get("config", {}),
                }
            }
        
        # Check for legacy worker mode jobs
        if progress.get("mode") == "worker" and progress["status"] == "queued":
            # Claim this job
            progress["status"] = "processing"
            progress["worker_id"] = worker_id
            progress["stage"] = "Assigned to worker"
            
            config = _worker_job_configs.get(job_id, {})
            
            return {
                "job": {
                    "job_id": job_id,
                    "job_type": "render",  # Just render pre-selected clips
                    "video_url": config.get("video_url"),
                    "youtube_url": config.get("youtube_url"),
                    "config": config.get("pipeline_config", config.get("config", {})),
                    "selected_clips": config.get("selected_clips"),
                }
            }
    
    return {"job": None}


@router.post("/worker/jobs/{job_id}/progress")
async def update_worker_job_progress(job_id: str, data: dict):
    """Update job progress from a local worker."""
    if job_id not in _job_progress:
        raise HTTPException(status_code=404, detail="Job not found")
    
    progress = data.get("progress", 0)
    stage = data.get("stage", "Processing")
    detail = data.get("detail", "")
    
    update_job_progress(job_id, "processing", progress, stage, detail)
    add_job_log(job_id, f"[{progress*100:.0f}%] {stage}: {detail}")
    
    # Check if job was cancelled
    if _job_cancel_flags.get(job_id):
        add_job_log(job_id, "Job cancellation requested", "warning")
        return {"status": "cancelled", "should_stop": True}
    
    return {"status": "ok", "should_stop": False}


@router.post("/worker/jobs/{job_id}/candidates")
async def upload_worker_candidates(job_id: str, data: dict):
    """Receive viral candidates from local worker after transcription + analysis."""
    if job_id not in _job_progress:
        raise HTTPException(status_code=404, detail="Job not found")
    
    candidates = data.get("candidates", [])
    transcript = data.get("transcript", {})
    
    # Store candidates
    _viral_candidates[job_id] = candidates
    
    # Save transcript to job directory
    job_dir = CLIPS_OUTPUT_DIR / job_id
    if transcript:
        with open(job_dir / "transcript.json", "w") as f:
            json.dump(transcript, f, indent=2)
    
    # Save candidates
    with open(job_dir / "viral_candidates.json", "w") as f:
        json.dump(candidates, f, indent=2)
    
    add_job_log(job_id, f"✓ Received {len(candidates)} viral candidates from worker", "success")
    
    # Update status to analyzed
    update_job_progress(
        job_id, "analyzed", 1.0,
        "Analysis complete",
        f"Found {len(candidates)} potential viral moments. Select which to render!"
    )
    
    return {"status": "ok", "candidates_received": len(candidates)}


@router.post("/worker/jobs/{job_id}/upload-clip")
async def upload_worker_clip(
    job_id: str,
    file: UploadFile = File(...),
    index: int = Form(...),
    start_time: float = Form(...),
    end_time: float = Form(...),
    duration: float = Form(...),
    score: float = Form(...),
    text: str = Form(""),
):
    """Upload a processed clip from a local worker."""
    if job_id not in _job_progress:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Save the clip
    job_dir = CLIPS_OUTPUT_DIR / job_id / "clips"
    job_dir.mkdir(parents=True, exist_ok=True)
    
    clip_path = job_dir / f"clip_{index:02d}.mp4"
    
    with open(clip_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    logger.info(f"Worker uploaded clip {index} for job {job_id}")
    
    return {
        "status": "uploaded",
        "clip_path": str(clip_path),
        "video_url": f"/api/clipper/clips/{job_id}/clip_{index:02d}.mp4",
    }


@router.post("/worker/jobs/{job_id}/complete")
async def complete_worker_job(job_id: str, data: dict):
    """Mark a worker job as complete."""
    if job_id not in _job_progress:
        raise HTTPException(status_code=404, detail="Job not found")
    
    success = data.get("success", False)
    error = data.get("error")
    clips_count = data.get("clips_count", 0)
    processing_time = data.get("processing_time", 0)
    
    if success:
        # Build a minimal result
        from .pipeline import PipelineResult, ClipResult
        
        # Find the uploaded clips
        clips_dir = CLIPS_OUTPUT_DIR / job_id / "clips"
        clips = []
        
        if clips_dir.exists():
            for i, clip_file in enumerate(sorted(clips_dir.glob("clip_*.mp4"))):
                clips.append(ClipResult(
                    index=i + 1,
                    video_path=str(clip_file),
                    thumbnail_path=None,
                    start_time=0,
                    end_time=0,
                    duration=0,
                    score=1.0,
                    text=""
                ))
        
        result = PipelineResult(
            success=True,
            source_video="worker",
            output_dir=str(CLIPS_OUTPUT_DIR / job_id),
            transcript_json="",
            transcript_srt="",
            clips=clips,
            total_duration=0,
            processing_time=processing_time,
        )
        
        _job_results[job_id] = result
        update_job_progress(job_id, "completed", 1.0, "Complete", f"Created {clips_count} clips")
        
        logger.info(f"Worker job {job_id} completed successfully with {clips_count} clips")
    else:
        update_job_progress(job_id, "failed", 0, "Failed", error or "Unknown error")
        _job_progress[job_id]["error"] = error or "Worker processing failed"
        
        logger.error(f"Worker job {job_id} failed: {error}")
    
    return {"status": "ok", "job_id": job_id}


@router.get("/worker/status")
async def get_worker_status():
    """Get status of registered workers and queued jobs."""
    # Clean up stale workers (not seen in 5 minutes)
    now = datetime.now()
    stale_workers = []
    for worker_id, worker in _registered_workers.items():
        last_seen = datetime.fromisoformat(worker["last_seen"])
        if (now - last_seen).total_seconds() > 300:
            stale_workers.append(worker_id)
    
    for worker_id in stale_workers:
        del _registered_workers[worker_id]
    
    # Count jobs waiting for workers
    queued_for_worker = sum(
        1 for p in _job_progress.values()
        if p.get("mode") == "worker" and p["status"] == "queued"
    )
    
    return {
        "workers": list(_registered_workers.values()),
        "workers_online": len(_registered_workers),
        "jobs_queued_for_worker": queued_for_worker,
    }


# Modify upload to support worker mode
@router.post("/upload-for-worker")
async def upload_video_for_worker(
    video: UploadFile = File(...),
    num_clips: int = Form(10),
    min_duration: float = Form(20),
    max_duration: float = Form(60),
    pause_threshold: float = Form(0.7),
    caption_style: str = Form("default"),
    whisper_model: str = Form("base"),
    burn_captions: bool = Form(True),
    crop_vertical: bool = Form(True),
    auto_center: bool = Form(True),
):
    """Upload a video to be processed by a local worker."""
    job_id = secrets.token_hex(4)
    
    # Save uploaded file
    job_dir = CLIPS_OUTPUT_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    
    input_path = job_dir / "input.mp4"
    with open(input_path, "wb") as f:
        content = await video.read()
        f.write(content)
    
    # Store job config for worker
    _worker_job_configs[job_id] = {
        "video_url": f"/api/clipper/clips/{job_id}/input.mp4",
        "pipeline_config": {
            "num_clips": num_clips,
            "min_duration": min_duration,
            "max_duration": max_duration,
            "pause_threshold": pause_threshold,
            "caption_style": caption_style,
            "whisper_model": whisper_model,
            "burn_captions": burn_captions,
            "crop_vertical": crop_vertical,
            "auto_center": auto_center,
        }
    }
    
    # Initialize progress in worker mode
    _job_progress[job_id] = {
        "status": "queued",
        "progress": 0,
        "stage": "Waiting for worker",
        "detail": "Job queued - waiting for a local worker to pick it up",
        "mode": "worker",
        "updated_at": datetime.now().isoformat(),
    }
    
    logger.info(f"Job {job_id} queued for local worker")
    
    return {
        "job_id": job_id,
        "status": "queued",
        "message": "Job queued for local worker. Make sure your local worker is running!"
    }


@router.post("/youtube-for-worker")
async def youtube_for_worker(
    background_tasks: BackgroundTasks,
    youtube_url: str = Form(...),
    num_clips: int = Form(10),
    min_duration: float = Form(20),
    max_duration: float = Form(60),
    pause_threshold: float = Form(0.7),
    caption_style: str = Form("default"),
    whisper_model: str = Form("base"),
    burn_captions: bool = Form(True),
    crop_vertical: bool = Form(True),
    auto_center: bool = Form(True),
):
    """Download YouTube video on Railway (fast), then queue for local worker processing."""
    job_id = secrets.token_hex(4)
    
    job_dir = CLIPS_OUTPUT_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    
    # Store job config for worker
    _worker_job_configs[job_id] = {
        "youtube_url": youtube_url,  # Keep for reference
        "video_url": None,  # Will be set after download
        "pipeline_config": {
            "num_clips": num_clips,
            "min_duration": min_duration,
            "max_duration": max_duration,
            "pause_threshold": pause_threshold,
            "caption_style": caption_style,
            "whisper_model": whisper_model,
            "burn_captions": burn_captions,
            "crop_vertical": crop_vertical,
            "auto_center": auto_center,
        }
    }
    
    # Initialize progress - downloading on Railway first
    _job_progress[job_id] = {
        "status": "downloading",
        "progress": 0,
        "stage": "Downloading on Railway",
        "detail": "Using Railway's fast servers to download from YouTube...",
        "mode": "worker",
        "updated_at": datetime.now().isoformat(),
    }
    
    logger.info(f"YouTube job {job_id} - downloading on Railway first: {youtube_url}")
    
    # Start download in background
    background_tasks.add_task(download_youtube_for_worker, job_id, youtube_url, job_dir)
    
    return {
        "job_id": job_id,
        "status": "downloading",
        "message": "Downloading on Railway (fast servers). Your PC will process it once ready."
    }


def download_youtube_for_worker(job_id: str, youtube_url: str, job_dir: Path):
    """Download YouTube video on Railway, then queue for worker."""
    import yt_dlp
    
    input_path = job_dir / "input.mp4"
    
    def progress_hook(d):
        if d['status'] == 'downloading':
            try:
                downloaded = d.get('downloaded_bytes', 0)
                total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                if total > 0:
                    pct = downloaded / total
                    update_job_progress(
                        job_id, "downloading", pct * 0.9,
                        "Downloading on Railway",
                        f"Using fast servers: {downloaded/1024/1024:.1f}MB / {total/1024/1024:.1f}MB"
                    )
            except:
                pass
        elif d['status'] == 'finished':
            update_job_progress(job_id, "downloading", 0.95, "Download complete", "Preparing for worker...")
    
    try:
        ydl_opts = {
            'format': 'best[height<=1080]/bestvideo[height<=1080]+bestaudio/best',
            'outtmpl': str(input_path.with_suffix('')),
            'merge_output_format': 'mp4',
            'progress_hooks': [progress_hook],
            'quiet': True,
            # Fix for 403 Forbidden errors - use android_creator
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.6261.119 Mobile Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            },
            'extractor_args': {
                'youtube': {
                    'player_client': ['android_creator', 'android', 'web'],
                }
            },
            'nocheckcertificate': True,
            'retries': 10,
            'fragment_retries': 10,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([youtube_url])
        
        # Find the downloaded file (might have different extension)
        for ext in ['.mp4', '.mkv', '.webm', '']:
            candidate = input_path.with_suffix(ext) if ext else input_path
            if candidate.exists() and candidate != input_path:
                candidate.rename(input_path)
                break
        
        if not input_path.exists():
            # Check for file without extension
            no_ext = job_dir / "input"
            if no_ext.exists():
                no_ext.rename(input_path)
        
        if input_path.exists():
            # Update config with local video URL
            _worker_job_configs[job_id]["video_url"] = f"/api/clipper/clips/{job_id}/input.mp4"
            _worker_job_configs[job_id]["youtube_url"] = None  # Clear YouTube URL so worker uses local file
            
            # Now queue for worker
            update_job_progress(
                job_id, "queued", 0,
                "Ready for your PC",
                "Video downloaded! Waiting for local worker to pick it up..."
            )
            logger.info(f"YouTube download complete for {job_id}, queued for worker")
        else:
            raise Exception("Download completed but file not found")
            
    except Exception as e:
        logger.exception(f"YouTube download failed for {job_id}")
        update_job_progress(job_id, "failed", 0, "Download failed", str(e))
        _job_progress[job_id]["error"] = str(e)


# ============================================================================
# SMART CLIPPER - AI-powered viral moment detection
# ============================================================================

# Job logs storage
_job_logs: Dict[str, List[dict]] = {}


def add_job_log(job_id: str, message: str, level: str = "info", eta: str = None):
    """Add a log entry for a job with optional ETA."""
    if job_id not in _job_logs:
        _job_logs[job_id] = []
    
    log_entry = {
        "time": datetime.now().isoformat(),
        "level": level,
        "message": message,
    }
    if eta:
        log_entry["eta"] = eta
    
    _job_logs[job_id].append(log_entry)
    logger.info(f"[{job_id}] {message}" + (f" (ETA: {eta})" if eta else ""))


@router.get("/job/{job_id}/logs")
async def get_job_logs(job_id: str):
    """Get logs for a job."""
    return {"logs": _job_logs.get(job_id, [])}


@router.post("/smart/analyze-full")
async def smart_analyze_full_railway(
    background_tasks: BackgroundTasks,
    youtube_url: str = Form(None),
    video: UploadFile = File(None),
    num_clips: int = Form(10),
    min_duration: float = Form(15),
    max_duration: float = Form(60),
    whisper_model: str = Form("tiny"),
    burn_captions: bool = Form(True),
    crop_vertical: bool = Form(True),
    auto_center: bool = Form(True),
    caption_style: str = Form("default"),
    # New style settings
    caption_animation: str = Form("karaoke"),
    caption_color: str = Form("#FFFFFF"),
    animation_color: str = Form("#FFFF00"),
    title_style: str = Form("bold"),
    title_color: str = Form("#FFFF00"),
    video_vibe: str = Form("default"),
    manual_topic_select: bool = Form(False),
    caption_size: int = Form(80),
    add_stock_images: bool = Form(False),
    caption_position: str = Form("middle-lower"),
    remove_silence: bool = Form(True),
):
    """
    FULL Railway processing - download, transcribe, analyze, ALL on Railway.
    No local worker needed. For users with Railway paid tier.
    """
    if not youtube_url and not video:
        raise HTTPException(status_code=400, detail="Provide youtube_url or video file")
    
    job_id = secrets.token_hex(4)
    job_dir = CLIPS_OUTPUT_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    
    _job_logs[job_id] = []
    add_job_log(job_id, f"Job created: {job_id} (Full Railway processing)")
    
    # Check cache
    cached_job_id = None
    if youtube_url:
        cache_key = get_video_cache_key(youtube_url)
        add_job_log(job_id, f"Checking cache: {cache_key}")
        if cache_key in _video_cache:
            cached_job_id = _video_cache[cache_key]
            cached_path = CLIPS_OUTPUT_DIR / cached_job_id / "input.mp4"
            if cached_path.exists():
                add_job_log(job_id, f"✓ Using cached video", "success")
                shutil.copy(cached_path, job_dir / "input.mp4")
                # Also copy transcript if exists
                cached_transcript = CLIPS_OUTPUT_DIR / cached_job_id / "transcript.json"
                if cached_transcript.exists():
                    shutil.copy(cached_transcript, job_dir / "transcript.json")
                    add_job_log(job_id, f"✓ Using cached transcript", "success")
            else:
                cached_job_id = None
    
    # Store config including style settings
    _worker_job_configs[job_id] = {
        "youtube_url": youtube_url,
        "config": {
            "num_clips": num_clips,
            "min_duration": min_duration,
            "max_duration": max_duration,
            "whisper_model": whisper_model,
            "burn_captions": burn_captions,
            "crop_vertical": crop_vertical,
            "auto_center": auto_center,
            "caption_style": caption_style,
            # Style settings
            "caption_animation": caption_animation,
            "caption_color": caption_color,
            "animation_color": animation_color,
            "title_style": title_style,
            "title_color": title_color,
            "video_vibe": video_vibe,
            "manual_topic_select": manual_topic_select,
        }
    }
    
    _job_progress[job_id] = {
        "status": "processing",
        "progress": 0.05 if cached_job_id else 0,
        "stage": "Using cached video" if cached_job_id else "Starting...",
        "detail": "Full Railway processing - no local worker needed",
        "mode": "railway",
        "updated_at": datetime.now().isoformat(),
    }
    
    # Handle file upload
    if video:
        add_job_log(job_id, f"Receiving upload: {video.filename}")
        input_path = job_dir / "input.mp4"
        with open(input_path, "wb") as f:
            content = await video.read()
            f.write(content)
        add_job_log(job_id, f"✓ Uploaded {len(content)/1024/1024:.1f}MB", "success")
        _job_progress[job_id]["progress"] = 0.1
    
    # Start full processing with style settings
    style_config = {
        "caption_animation": caption_animation,
        "caption_color": caption_color,
        "animation_color": animation_color,
        "title_style": title_style,
        "title_color": title_color,
        "video_vibe": video_vibe,
        "manual_topic_select": manual_topic_select,
        "caption_size": caption_size,
        "add_stock_images": add_stock_images,
        "caption_position": caption_position,
        "remove_silence": remove_silence,
    }
    
    background_tasks.add_task(
        run_full_railway_processing,
        job_id,
        job_dir,
        youtube_url,
        num_clips,
        min_duration,
        max_duration,
        whisper_model,
        burn_captions,
        crop_vertical,
        auto_center,
        caption_style,
        cached_job_id is not None,
        style_config,
    )
    
    return {
        "job_id": job_id,
        "status": "processing",
        "cached": cached_job_id is not None,
        "manual_select": manual_topic_select,  # Let frontend know if we'll show topics
        "message": "Processing on Railway - sit back and relax!"
    }


def run_full_railway_processing(
    job_id: str,
    job_dir: Path,
    youtube_url: Optional[str],
    num_clips: int,
    min_duration: float,
    max_duration: float,
    whisper_model: str,
    burn_captions: bool,
    crop_vertical: bool,
    auto_center: bool,
    caption_style: str,
    is_cached: bool,
    style_config: dict = None,
):
    """Run the FULL pipeline on Railway - download, transcribe, analyze, render."""
    # Default style config
    if style_config is None:
        style_config = {
            "caption_animation": "karaoke",
            "caption_color": "#FFFFFF",
            "animation_color": "#FFFF00",
            "title_style": "bold",
            "title_color": "#FFFF00",
            "video_vibe": "default",
            "manual_topic_select": False,
            "caption_size": 80,
        }
    
    # Log style config for debugging
    logger.info(f"🎨 Style config for job {job_id}: {style_config}")
    import json
    import traceback
    
    logger.info(f"🚀 Starting full Railway processing for job {job_id}")
    add_job_log(job_id, "🚀 Background task started")
    update_job_progress(job_id, "processing", 0.02, "Starting", "Initializing pipeline...")
    
    try:
        # Import inside function to catch import errors
        try:
            from .transcribe import transcribe_video
            from .render import render_final_clip, create_thumbnail
            from .captions import generate_ass_subtitles
            from .ai_editor import AIVideoEditor
            add_job_log(job_id, "✓ All modules loaded (including AI editor)")
        except Exception as e:
            logger.error(f"Import error: {e}")
            add_job_log(job_id, f"✗ Import failed: {e}", "error")
            update_job_progress(job_id, "failed", 0, "Import failed", str(e))
            return
        
        input_path = job_dir / "input.mp4"
        transcript_path = job_dir / "transcript.json"
        
        # Step 1: Download if needed
        if youtube_url and not input_path.exists():
            try:
                import yt_dlp
            except ImportError as e:
                add_job_log(job_id, f"✗ yt-dlp not installed: {e}", "error")
                update_job_progress(job_id, "failed", 0, "yt-dlp missing", "yt-dlp package not installed")
                return
            
            add_job_log(job_id, f"📥 Downloading from YouTube: {youtube_url}", eta="~1-3 min")
            update_job_progress(job_id, "processing", 0.05, "Downloading", "Fetching video from YouTube...")
            
            def progress_hook(d):
                if d['status'] == 'downloading':
                    try:
                        downloaded = d.get('downloaded_bytes', 0)
                        total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                        if total > 0:
                            pct = downloaded / total
                            update_job_progress(
                                job_id, "processing", 0.05 + pct * 0.15,
                                "Downloading",
                                f"{downloaded/1024/1024:.1f}MB / {total/1024/1024:.1f}MB"
                            )
                    except:
                        pass
            
            # Use a simpler output template that yt-dlp handles better
            output_template = str(job_dir / "input.%(ext)s")
            
            ydl_opts = {
                # Use simple format to avoid 403 - don't try to merge
                'format': 'best[height<=720]/bestvideo[height<=720]+bestaudio/best',
                'outtmpl': output_template,
                'progress_hooks': [progress_hook],
                'quiet': False,
                'no_warnings': False,
                # Postprocessor to convert to mp4 if needed
                'postprocessors': [{
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4',
                }],
                # Fix for 403 Forbidden - use android_creator client (most reliable)
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.6261.119 Mobile Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Connection': 'keep-alive',
                },
                'extractor_args': {
                    'youtube': {
                        # android_creator bypasses most 403 errors
                        'player_client': ['android_creator', 'android', 'web'],
                    }
                },
                # Bypass various restrictions
                'nocheckcertificate': True,
                'ignoreerrors': False,
                'age_limit': None,  # Don't skip age-restricted videos
                # Retry settings
                'socket_timeout': 60,
                'retries': 10,
                'fragment_retries': 10,
                'file_access_retries': 5,
            }
            
            try:
                add_job_log(job_id, f"Starting yt-dlp download (using iOS client)...")
                add_job_log(job_id, f"Output template: {output_template}")
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    # First extract info to check if video is available
                    info = ydl.extract_info(youtube_url, download=False)
                    add_job_log(job_id, f"Video found: {info.get('title', 'Unknown')} ({info.get('duration', 0)}s)")
                    
                    # Now download
                    ydl.download([youtube_url])
                    
            except Exception as dl_err:
                error_msg = str(dl_err)
                add_job_log(job_id, f"✗ Download error: {error_msg}", "error")
                logger.error(f"yt-dlp download failed: {dl_err}")
                
                # Try to give helpful error messages
                if "403" in error_msg:
                    add_job_log(job_id, "This video may have age/region restrictions. Try a different video.", "error")
                elif "private" in error_msg.lower():
                    add_job_log(job_id, "This video is private and cannot be downloaded.", "error")
                
                update_job_progress(job_id, "failed", 0, "Download failed", error_msg[:200])
                return
            
            # Find downloaded file - check all files in directory
            add_job_log(job_id, f"Looking for downloaded file in {job_dir}")
            found_file = None
            
            # List all files in directory
            all_files = list(job_dir.iterdir())
            add_job_log(job_id, f"Files in directory: {[f.name for f in all_files]}")
            
            # Check for input.mp4 first (direct match)
            if input_path.exists():
                found_file = input_path
                add_job_log(job_id, f"Found: {input_path}")
            else:
                # Check for any input.* file
                for f in all_files:
                    if f.name.startswith("input") and f.suffix in ['.mp4', '.mkv', '.webm', '.m4a', '.mov']:
                        found_file = f
                        add_job_log(job_id, f"Found video: {f.name}")
                        break
            
            if found_file and found_file != input_path:
                add_job_log(job_id, f"Renaming {found_file.name} to input.mp4")
                found_file.rename(input_path)
            elif not found_file:
                # Last resort - check for any video file
                for f in all_files:
                    if f.suffix in ['.mp4', '.mkv', '.webm', '.m4a', '.mov'] and f.stat().st_size > 1000:
                        add_job_log(job_id, f"Found video file: {f.name}, renaming to input.mp4")
                        f.rename(input_path)
                        found_file = input_path
                        break
            
            if not input_path.exists():
                add_job_log(job_id, f"✗ Download completed but no video file created!", "error")
                add_job_log(job_id, f"Directory contents: {[f.name for f in job_dir.iterdir()]}", "error")
                update_job_progress(job_id, "failed", 0, "Download failed", "Video file not found after download")
                return
            
            # Cache it
            cache_key = get_video_cache_key(youtube_url)
            _video_cache[cache_key] = job_id
            
            add_job_log(job_id, f"✓ Download complete: {input_path} ({input_path.stat().st_size / 1024 / 1024:.1f}MB)", "success")
        
        # Verify video file exists before proceeding
        if not input_path.exists():
            add_job_log(job_id, f"✗ Video file not found: {input_path}", "error")
            update_job_progress(job_id, "failed", 0, "Processing failed", f"Video file not found: {input_path}")
            return
        
        update_job_progress(job_id, "processing", 0.20, "Download complete", "Starting transcription...")
        
        # Step 2: Transcribe
        import time as time_module
        if not transcript_path.exists():
            add_job_log(job_id, f"🎤 Transcribing with Whisper ({whisper_model})...", eta="~2-5 min depending on video length")
            update_job_progress(job_id, "processing", 0.25, "Transcribing", f"Using {whisper_model} model...")
            
            transcribe_start = time_module.time()
            transcript_result = transcribe_video(str(input_path), model_size=whisper_model)
            transcript = transcript_result.to_dict()
            transcribe_time = time_module.time() - transcribe_start
            
            with open(transcript_path, "w") as f:
                json.dump(transcript, f, indent=2)
            
            add_job_log(job_id, f"✓ Transcription complete in {transcribe_time:.1f}s ({len(transcript.get('segments', []))} segments)", "success")
        else:
            with open(transcript_path) as f:
                transcript = json.load(f)
            add_job_log(job_id, "⚡ Using cached transcript (skipped transcription)", "success")
        
        update_job_progress(job_id, "processing", 0.45, "Transcription complete", "Analyzing for viral moments...")
        
        # Step 3: Analyze for viral moments with AI
        add_job_log(job_id, "🧠 AI analyzing transcript for viral moments...", eta="~30s")
        
        words = []
        for segment in transcript.get("segments", []):
            words.extend(segment.get("words", []))
        
        viral_moments = analyze_transcript_for_virality(
            words, num_clips=num_clips, min_duration=min_duration, max_duration=max_duration
        )
        
        # Store candidates
        candidates = []
        for i, moment in enumerate(viral_moments):
            candidates.append({
                "index": i,
                "start_time": moment.start_time,
                "end_time": moment.end_time,
                "duration": moment.duration,
                "text": moment.text,
                "virality_score": moment.virality_score,
                "virality_reason": moment.virality_reason,
                "suggested_caption": moment.suggested_caption,
                "suggested_hashtags": moment.suggested_hashtags,
                "category": moment.category,
                "selected": i < num_clips,
            })
        
        _viral_candidates[job_id] = candidates
        add_job_log(job_id, f"✓ AI found {len(candidates)} viral moments with hooks", "success")
        
        # Log top candidates
        for i, c in enumerate(candidates[:3]):
            add_job_log(job_id, f"  #{i+1} Score {c['virality_score']}: {c['text'][:50]}...")
        
        # Save candidates
        with open(job_dir / "viral_candidates.json", "w") as f:
            json.dump(candidates, f, indent=2)
        
        update_job_progress(job_id, "processing", 0.50, "Analysis complete", f"AI editing top {num_clips} clips...")
        add_job_log(job_id, f"🎬 Starting AI video editing for {num_clips} clips...", eta=f"~{num_clips * 45}s")
        
        # Step 4: AI-Powered Rendering with Dynamic Captions + Audio
        selected = [c for c in candidates if c.get("selected")][:num_clips]
        clips_dir = job_dir / "clips"
        clips_dir.mkdir(exist_ok=True)
        
        # Import audio effects
        try:
            from .audio_effects import add_viral_audio_package
            has_audio_fx = True
            add_job_log(job_id, "🎵 Audio effects module loaded")
        except Exception as e:
            has_audio_fx = False
            add_job_log(job_id, f"Audio effects unavailable: {e}", "warning")
        
        # Initialize AI editor with style config
        ai_editor = AIVideoEditor(
            enable_effects=True,
            enable_music=False,  # We'll add music via audio_effects module
            caption_style="dynamic",
            style_config=style_config,
        )
        
        # Initialize progressive results storage
        _viral_candidates[job_id + "_results"] = []
        
        results = []
        for i, clip in enumerate(selected):
            if _job_cancel_flags.get(job_id):
                add_job_log(job_id, "Job cancelled", "warning")
                update_job_progress(job_id, "cancelled", 0, "Cancelled", "Job cancelled by user")
                return
            
            progress = 0.50 + (i / len(selected)) * 0.45
            remaining_clips = len(selected) - i
            update_job_progress(
                job_id, "processing", progress,
                f"🎬 AI editing clip {i+1}/{len(selected)}",
                f"Score: {clip['virality_score']} - {clip['category']}"
            )
            add_job_log(
                job_id, 
                f"🎬 Clip {i+1}/{len(selected)}: {clip['text'][:40]}...",
                eta=f"~{remaining_clips * 25}s remaining"
            )
            add_job_log(job_id, f"   → Adding centered captions + hook header + scene changes")
            
            clip_name = f"clip_{i+1:02d}"
            clip_path = clips_dir / f"{clip_name}.mp4"
            
            # Get words for this clip
            clip_words = [
                w for w in words
                if clip["start_time"] <= w.get("start", 0) <= clip["end_time"]
            ]
            
            # Use AI editor for enhanced rendering
            try:
                edited_result = ai_editor.edit_clip(
                    source_video=input_path,
                    output_path=clip_path,
                    words=words,  # Pass all words for AI optimization
                    start_time=clip["start_time"],
                    end_time=clip["end_time"],
                    burn_captions=burn_captions,
                    add_music=False,
                    add_effects=False,  # Keep simple for now to avoid FFmpeg complexity
                    optimize_boundaries=True,  # AI-optimize hooks and endings
                )
                thumb_path = edited_result.thumbnail_path
                hook_text = edited_result.hook_text
                effects_applied = edited_result.effects_applied
            except Exception as e:
                logger.warning(f"AI editor failed, falling back to basic render: {e}")
                add_job_log(job_id, f"Using basic render for clip {i+1}", "warning")
                
                # Fallback to basic rendering
                ass_path = None
                if burn_captions:
                    from .transcribe import Word
                    from .captions import get_style_preset
                    word_objects = [
                        Word(
                            word=w.get("word", ""),
                            start=w.get("start", 0),
                            end=w.get("end", 0),
                            confidence=w.get("confidence", 1.0)
                        )
                        for w in clip_words
                    ]
                    if word_objects:
                        ass_path = clips_dir / f"{clip_name}.ass"
                        style = get_style_preset(caption_style)
                        generate_ass_subtitles(
                            word_objects, str(ass_path),
                            style=style,
                            time_offset=-clip["start_time"],
                        )
                
                render_final_clip(
                    input_path, clip_path,
                    clip["start_time"], clip["end_time"],
                    ass_path=ass_path,
                    crop_vertical=crop_vertical,
                    auto_center=auto_center,
                )
                
                thumb_path = clips_dir / f"{clip_name}_thumb.jpg"
                try:
                    create_thumbnail(clip_path, thumb_path)
                except:
                    thumb_path = None
                
                hook_text = ""
                effects_applied = []
            
            # Add viral audio package (music + sound effects)
            if has_audio_fx and clip_path.exists():
                try:
                    add_job_log(job_id, f"   → Adding background music + sound effects")
                    final_path = clips_dir / f"{clip_name}_final.mp4"
                    
                    # Determine music style based on category
                    music_styles = {
                        "funny": "funny",
                        "emotional": "dramatic",
                        "educational": "chill",
                        "controversial": "dramatic",
                        "shocking": "dramatic",
                    }
                    music_style = music_styles.get(clip.get("category", ""), "upbeat")
                    
                    add_viral_audio_package(
                        clip_path, final_path,
                        music_style=music_style,
                        add_whoosh_at_start=True,
                        add_bass_on_hook=True,
                        hook_timestamp=0.5,
                    )
                    
                    # Replace original with final
                    if final_path.exists():
                        clip_path.unlink()
                        final_path.rename(clip_path)
                        add_job_log(job_id, f"   ✓ Audio effects added", "success")
                except Exception as e:
                    add_job_log(job_id, f"   ⚠ Audio effects failed: {e}", "warning")
            
            clip_result = {
                "index": i + 1,
                "video_url": f"/api/clipper/clips/{job_id}/{clip_name}.mp4",
                "thumbnail_url": f"/api/clipper/clips/{job_id}/{clip_name}_thumb.jpg" if thumb_path else None,
                "start_time": clip["start_time"],
                "end_time": clip["end_time"],
                "duration": clip["duration"],
                "virality_score": clip["virality_score"],
                "virality_reason": clip["virality_reason"],
                "suggested_caption": clip["suggested_caption"],
                "suggested_hashtags": clip["suggested_hashtags"],
                "category": clip["category"],
                "text": clip["text"],
                "hook_text": hook_text,
                "effects_applied": effects_applied + (["music", "whoosh", "bass_drop"] if has_audio_fx else []),
                "ready": True,  # Mark as ready for immediate display
            }
            
            results.append(clip_result)
            
            # Store progressively so frontend can show clips as they complete
            _viral_candidates[job_id + "_results"] = results.copy()
            
            add_job_log(job_id, f"✓ Clip {i+1} READY - can be viewed now!", "success")
        
        # Store results
        _viral_candidates[job_id + "_results"] = results
        
        with open(job_dir / "results.json", "w") as f:
            json.dump(results, f, indent=2)
        
        update_job_progress(job_id, "completed", 1.0, "Complete!", f"Created {len(results)} viral clips")
        add_job_log(job_id, f"✓ All done! {len(results)} clips ready", "success")
        
        # Save to history
        add_to_clip_history(job_id, results, youtube_url)
        
    except Exception as e:
        logger.exception(f"Full Railway processing failed for {job_id}")
        add_job_log(job_id, f"✗ Error: {str(e)}", "error")
        update_job_progress(job_id, "failed", 0, "Processing failed", str(e))
        _job_progress[job_id]["error"] = str(e)


@router.post("/smart/analyze")
async def smart_analyze_video(
    background_tasks: BackgroundTasks,
    youtube_url: str = Form(None),
    video: UploadFile = File(None),
    num_clips: int = Form(10),
    min_duration: float = Form(15),
    max_duration: float = Form(60),
    whisper_model: str = Form("base"),
    use_local_worker: bool = Form(True),  # Default to local worker for processing
):
    """
    Smart analysis flow:
    - Railway: Downloads video only (fast servers)
    - Local Worker: Transcription + Analysis + Rendering (your PC's power)
    
    Returns job_id to track progress.
    """
    if not youtube_url and not video:
        raise HTTPException(status_code=400, detail="Provide youtube_url or video file")
    
    job_id = secrets.token_hex(4)
    job_dir = CLIPS_OUTPUT_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize logs
    _job_logs[job_id] = []
    add_job_log(job_id, f"Job created: {job_id}")
    
    # Check cache for YouTube videos
    cached_job_id = None
    if youtube_url:
        cache_key = get_video_cache_key(youtube_url)
        add_job_log(job_id, f"Checking cache for video: {cache_key}")
        if cache_key in _video_cache:
            cached_job_id = _video_cache[cache_key]
            cached_path = CLIPS_OUTPUT_DIR / cached_job_id / "input.mp4"
            if cached_path.exists():
                add_job_log(job_id, f"✓ Found cached video from job {cached_job_id}", "success")
                shutil.copy(cached_path, job_dir / "input.mp4")
            else:
                cached_job_id = None
                add_job_log(job_id, "Cache miss - video file not found")
    
    # Store config
    _worker_job_configs[job_id] = {
        "youtube_url": youtube_url,
        "video_url": f"/api/clipper/clips/{job_id}/input.mp4" if cached_job_id else None,
        "cached_from": cached_job_id,
        "config": {
            "num_clips": num_clips,
            "min_duration": min_duration,
            "max_duration": max_duration,
            "whisper_model": whisper_model,
        },
        "use_local_worker": use_local_worker,
    }
    
    # Initialize progress with time estimates
    _job_progress[job_id] = {
        "status": "downloading" if not cached_job_id else "ready_for_worker",
        "progress": 0.9 if cached_job_id else 0,
        "stage": "Using cached video" if cached_job_id else "Downloading on Railway",
        "detail": "Video ready for processing" if cached_job_id else "Starting download...",
        "mode": "smart",
        "updated_at": datetime.now().isoformat(),
        "estimates": {
            "download": "~30s-2min (Railway fast servers)",
            "transcribe": "~1-3min (on your PC)",
            "analyze": "~10-30s (AI analysis)",
            "render": "~30s per clip (on your PC)",
            "total": "~3-8min depending on video length",
        }
    }
    
    # Handle file upload
    if video:
        add_job_log(job_id, f"Receiving uploaded file: {video.filename}")
        input_path = job_dir / "input.mp4"
        with open(input_path, "wb") as f:
            content = await video.read()
            f.write(content)
        file_size_mb = len(content) / 1024 / 1024
        add_job_log(job_id, f"✓ File uploaded: {file_size_mb:.1f}MB", "success")
        _job_progress[job_id]["progress"] = 0.9
        _job_progress[job_id]["status"] = "ready_for_worker"
        _job_progress[job_id]["stage"] = "Ready for your PC"
        _worker_job_configs[job_id]["video_url"] = f"/api/clipper/clips/{job_id}/input.mp4"
    
    # If cached, video is ready immediately
    if cached_job_id:
        add_job_log(job_id, "Video ready - waiting for local worker to pick up job")
        return {
            "job_id": job_id,
            "status": "ready_for_worker",
            "cached": True,
            "message": "Video ready! Start the worker on your PC to process."
        }
    
    # Start download on Railway (only download, not transcription)
    if youtube_url:
        add_job_log(job_id, f"Starting YouTube download: {youtube_url[:50]}...")
        background_tasks.add_task(
            download_video_only,
            job_id,
            job_dir,
            youtube_url,
        )
    
    return {
        "job_id": job_id,
        "status": "downloading",
        "cached": False,
        "message": "Downloading video on Railway (fast servers). Your PC will handle the rest!"
    }


def download_video_only(job_id: str, job_dir: Path, youtube_url: str):
    """Download YouTube video on Railway only - transcription happens on local worker."""
    import yt_dlp
    
    input_path = job_dir / "input.mp4"
    
    add_job_log(job_id, "Initializing yt-dlp...")
    
    def progress_hook(d):
        if d['status'] == 'downloading':
            try:
                downloaded = d.get('downloaded_bytes', 0)
                total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                if total > 0:
                    pct = downloaded / total
                    speed = d.get('speed', 0) or 0
                    speed_mb = speed / 1024 / 1024 if speed else 0
                    eta = d.get('eta', 0) or 0
                    
                    update_job_progress(
                        job_id, "downloading", pct * 0.9,
                        "Downloading on Railway",
                        f"{downloaded/1024/1024:.1f}MB / {total/1024/1024:.1f}MB @ {speed_mb:.1f}MB/s (ETA: {eta}s)"
                    )
            except:
                pass
        elif d['status'] == 'finished':
            add_job_log(job_id, "✓ Download finished, processing...", "success")
    
    try:
        add_job_log(job_id, "Fetching video info from YouTube...")
        
        ydl_opts = {
            'format': 'best[height<=1080]/bestvideo[height<=1080]+bestaudio/best',
            'outtmpl': str(input_path.with_suffix('')),
            'merge_output_format': 'mp4',
            'progress_hooks': [progress_hook],
            'quiet': True,
            # Fix for 403 Forbidden errors - use android_creator client
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.6261.119 Mobile Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            },
            'extractor_args': {
                'youtube': {
                    'player_client': ['android_creator', 'android', 'web'],
                }
            },
            'nocheckcertificate': True,
            'retries': 10,
            'fragment_retries': 10,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)
            duration = info.get('duration', 0)
            title = info.get('title', 'Unknown')
            add_job_log(job_id, f"Video: {title[:50]}... ({duration}s)")
            
            # Update estimates based on actual video duration
            _job_progress[job_id]["estimates"]["transcribe"] = f"~{max(30, duration // 10)}s-{max(60, duration // 5)}s"
            
            ydl.download([youtube_url])
        
        # Find downloaded file
        for ext in ['.mp4', '.mkv', '.webm', '']:
            candidate = input_path.with_suffix(ext) if ext else input_path
            if candidate.exists() and candidate != input_path:
                candidate.rename(input_path)
                break
        
        if input_path.exists():
            file_size = input_path.stat().st_size / 1024 / 1024
            add_job_log(job_id, f"✓ Video saved: {file_size:.1f}MB", "success")
            
            # Cache this video
            cache_key = get_video_cache_key(youtube_url)
            _video_cache[cache_key] = job_id
            add_job_log(job_id, f"Video cached for future use (key: {cache_key})")
            
            # Update config with video URL for worker
            _worker_job_configs[job_id]["video_url"] = f"/api/clipper/clips/{job_id}/input.mp4"
            
            # Mark as ready for worker
            update_job_progress(
                job_id, "ready_for_worker", 0.9,
                "Ready for your PC",
                "Video downloaded! Start the local worker to continue processing."
            )
            add_job_log(job_id, "✓ Ready for local worker - waiting for your PC to pick up the job", "success")
        else:
            raise Exception("Download completed but file not found")
            
    except Exception as e:
        add_job_log(job_id, f"✗ Download failed: {str(e)}", "error")
        update_job_progress(job_id, "failed", 0, "Download failed", str(e))
        _job_progress[job_id]["error"] = str(e)


def run_smart_analysis(
    job_id: str,
    job_dir: Path,
    youtube_url: Optional[str],
    num_clips: int,
    min_duration: float,
    max_duration: float,
    whisper_model: str,
    is_cached: bool,
):
    """Run the smart analysis pipeline."""
    import json
    
    try:
        input_path = job_dir / "input.mp4"
        transcript_path = job_dir / "transcript.json"
        
        # Step 1: Download if needed
        if youtube_url and not input_path.exists():
            import yt_dlp
            
            update_job_progress(job_id, "analyzing", 0.05, "Downloading video", "Using Railway's fast servers...")
            
            def progress_hook(d):
                if d['status'] == 'downloading':
                    try:
                        downloaded = d.get('downloaded_bytes', 0)
                        total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                        if total > 0:
                            pct = downloaded / total
                            update_job_progress(
                                job_id, "analyzing", 0.05 + pct * 0.25,
                                "Downloading video",
                                f"{downloaded/1024/1024:.1f}MB / {total/1024/1024:.1f}MB"
                            )
                    except:
                        pass
            
            output_template = str(job_dir / "input.%(ext)s")
            
            ydl_opts = {
                'format': 'best[height<=720]/bestvideo[height<=720]+bestaudio/best',
                'outtmpl': output_template,
                'progress_hooks': [progress_hook],
                'quiet': False,
                'no_warnings': False,
                'postprocessors': [{
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4',
                }],
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.6261.119 Mobile Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                },
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android_creator', 'android', 'web'],
                    }
                },
                'nocheckcertificate': True,
                'socket_timeout': 60,
                'retries': 10,
                'fragment_retries': 10,
            }
            
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([youtube_url])
            except Exception as dl_err:
                logger.error(f"yt-dlp download failed: {dl_err}")
                update_job_progress(job_id, "failed", 0, "Download failed", str(dl_err))
                return
            
            # Find downloaded file
            found_file = None
            if input_path.exists():
                found_file = input_path
            else:
                for f in job_dir.iterdir():
                    if f.name.startswith("input") and f.suffix in ['.mp4', '.mkv', '.webm', '.mov']:
                        found_file = f
                        break
            
            if found_file and found_file != input_path:
                found_file.rename(input_path)
            
            # Find downloaded file fallback
            if not input_path.exists():
                for ext in ['.mp4', '.mkv', '.webm', '.m4a', '']:
                    candidate = input_path.with_suffix(ext) if ext else input_path
                    if candidate.exists():
                        found_file = candidate
                        break
            
            # Also check directory for any video files
            if not found_file:
                for f in job_dir.iterdir():
                    if f.name.startswith("input") and f.suffix in ['.mp4', '.mkv', '.webm']:
                        found_file = f
                        break
            
            if found_file and found_file != input_path:
                found_file.rename(input_path)
            elif not found_file and not input_path.exists():
                update_job_progress(job_id, "failed", 0, "Download failed", "Video file not created")
                return
            
            # Cache this video
            cache_key = get_video_cache_key(youtube_url)
            _video_cache[cache_key] = job_id
            
            update_job_progress(job_id, "analyzing", 0.30, "Download complete", "Starting transcription...")
        
        # Verify file exists
        if not input_path.exists():
            update_job_progress(job_id, "failed", 0, "Processing failed", f"Video file not found: {input_path}")
            return
        
        # Step 2: Transcribe if needed
        if not transcript_path.exists():
            update_job_progress(job_id, "analyzing", 0.35, "Transcribing audio", f"Using Whisper {whisper_model} model...")
            
            from .transcribe import transcribe_video
            
            transcript_result = transcribe_video(
                str(input_path),
                model_size=whisper_model,
            )
            transcript = transcript_result.to_dict()
            
            # Save transcript
            with open(transcript_path, "w") as f:
                json.dump(transcript, f, indent=2)
            
            update_job_progress(job_id, "analyzing", 0.60, "Transcription complete", "Analyzing for viral moments...")
        else:
            # Load existing transcript
            with open(transcript_path) as f:
                transcript = json.load(f)
            update_job_progress(job_id, "analyzing", 0.60, "Using cached transcript", "Analyzing for viral moments...")
        
        # Step 3: Analyze for viral moments
        update_job_progress(job_id, "analyzing", 0.65, "Finding viral moments", "AI analyzing transcript...")
        
        # Extract all words from segments
        words = []
        for segment in transcript.get("segments", []):
            words.extend(segment.get("words", []))
        
        viral_moments = analyze_transcript_for_virality(
            words,
            num_clips=num_clips,
            min_duration=min_duration,
            max_duration=max_duration,
        )
        
        # Convert to dict for JSON serialization
        candidates = []
        for i, moment in enumerate(viral_moments):
            candidates.append({
                "index": i,
                "start_time": moment.start_time,
                "end_time": moment.end_time,
                "duration": moment.duration,
                "text": moment.text,
                "virality_score": moment.virality_score,
                "virality_reason": moment.virality_reason,
                "suggested_caption": moment.suggested_caption,
                "suggested_hashtags": moment.suggested_hashtags,
                "hook": moment.hook,
                "category": moment.category,
                "selected": i < num_clips,  # Pre-select top N
            })
        
        # Store candidates
        _viral_candidates[job_id] = candidates
        
        # Save candidates to file
        with open(job_dir / "viral_candidates.json", "w") as f:
            json.dump(candidates, f, indent=2)
        
        # Update progress to complete analysis phase
        update_job_progress(
            job_id, "analyzed", 1.0,
            "Analysis complete",
            f"Found {len(candidates)} potential viral moments. Select which to render!"
        )
        
        logger.info(f"Smart analysis complete for {job_id}: {len(candidates)} candidates")
        
    except Exception as e:
        logger.exception(f"Smart analysis failed for {job_id}")
        update_job_progress(job_id, "failed", 0, "Analysis failed", str(e))
        _job_progress[job_id]["error"] = str(e)


@router.get("/smart/{job_id}/candidates")
async def get_viral_candidates(job_id: str):
    """Get the viral moment candidates for a job."""
    if job_id not in _job_progress:
        raise HTTPException(status_code=404, detail="Job not found")
    
    progress = _job_progress[job_id]
    
    # Return progress if still analyzing
    if progress["status"] not in ["analyzed", "rendering", "completed"]:
        return {
            "status": progress["status"],
            "progress": progress["progress"],
            "stage": progress["stage"],
            "detail": progress.get("detail"),
            "candidates": None,
        }
    
    # Return candidates
    candidates = _viral_candidates.get(job_id, [])
    
    return {
        "status": progress["status"],
        "progress": progress["progress"],
        "stage": progress["stage"],
        "candidates": candidates,
        "video_url": f"/api/clipper/clips/{job_id}/input.mp4",
    }


@router.post("/smart/{job_id}/render")
async def render_selected_clips(
    job_id: str,
    background_tasks: BackgroundTasks,
    selected_indices: List[int] = None,
    burn_captions: bool = Form(True),
    crop_vertical: bool = Form(True),
    auto_center: bool = Form(True),
    caption_style: str = Form("default"),
    use_local_worker: bool = Form(False),
):
    """
    Render the selected viral clips.
    
    Args:
        selected_indices: List of candidate indices to render. If None, renders pre-selected ones.
    """
    if job_id not in _job_progress:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job_id not in _viral_candidates:
        raise HTTPException(status_code=400, detail="No candidates found. Run analysis first.")
    
    candidates = _viral_candidates[job_id]
    
    # Get selected candidates
    if selected_indices is None:
        # Use pre-selected (top N by score)
        selected = [c for c in candidates if c.get("selected")]
    else:
        selected = [c for i, c in enumerate(candidates) if i in selected_indices]
    
    if not selected:
        raise HTTPException(status_code=400, detail="No clips selected for rendering")
    
    # Store render config
    job_dir = CLIPS_OUTPUT_DIR / job_id
    _worker_job_configs[job_id] = {
        **_worker_job_configs.get(job_id, {}),
        "selected_clips": selected,
        "render_config": {
            "burn_captions": burn_captions,
            "crop_vertical": crop_vertical,
            "auto_center": auto_center,
            "caption_style": caption_style,
        }
    }
    
    if use_local_worker:
        # Queue for local worker
        _job_progress[job_id]["status"] = "queued"
        _job_progress[job_id]["stage"] = "Waiting for local worker"
        _job_progress[job_id]["detail"] = f"Ready to render {len(selected)} clips on your PC"
        _job_progress[job_id]["mode"] = "worker"
        
        # Add video URL for worker
        _worker_job_configs[job_id]["video_url"] = f"/api/clipper/clips/{job_id}/input.mp4"
        
        return {
            "job_id": job_id,
            "status": "queued",
            "clips_to_render": len(selected),
            "message": "Queued for local worker. Start the worker on your PC!"
        }
    else:
        # Render on server
        _job_progress[job_id]["status"] = "rendering"
        _job_progress[job_id]["stage"] = "Starting render"
        _job_progress[job_id]["progress"] = 0
        
        background_tasks.add_task(
            render_smart_clips,
            job_id,
            job_dir,
            selected,
            burn_captions,
            crop_vertical,
            auto_center,
            caption_style,
        )
        
        return {
            "job_id": job_id,
            "status": "rendering",
            "clips_to_render": len(selected),
            "message": f"Rendering {len(selected)} clips..."
        }


def render_smart_clips(
    job_id: str,
    job_dir: Path,
    selected_clips: List[dict],
    burn_captions: bool,
    crop_vertical: bool,
    auto_center: bool,
    caption_style: str,
):
    """Render the selected clips."""
    import json
    from .render import render_final_clip, create_thumbnail
    from .captions import generate_ass_subtitles
    
    try:
        input_path = job_dir / "input.mp4"
        clips_dir = job_dir / "clips"
        clips_dir.mkdir(exist_ok=True)
        
        # Load transcript for captions
        transcript_path = job_dir / "transcript.json"
        transcript = None
        if transcript_path.exists() and burn_captions:
            with open(transcript_path) as f:
                transcript = json.load(f)
        
        results = []
        total = len(selected_clips)
        
        for i, clip in enumerate(selected_clips):
            if _job_cancel_flags.get(job_id):
                update_job_progress(job_id, "cancelled", 0, "Cancelled", "Render cancelled by user")
                return
            
            progress = (i / total)
            update_job_progress(
                job_id, "rendering", progress,
                f"Rendering clip {i+1}/{total}",
                f"Score: {clip['virality_score']} - {clip['category']}"
            )
            
            clip_name = f"clip_{i+1:02d}"
            clip_path = clips_dir / f"{clip_name}.mp4"
            
            # Generate captions for this clip if needed
            ass_path = None
            if burn_captions and transcript:
                from .transcribe import Word
                from .captions import get_style_preset
                # Filter words for this clip's time range and convert to Word objects
                clip_words = [
                    Word(
                        word=w.get("word", ""),
                        start=w.get("start", 0),
                        end=w.get("end", 0),
                        confidence=w.get("confidence", 1.0)
                    )
                    for w in transcript.get("words", [])
                    if clip["start_time"] <= w.get("start", 0) <= clip["end_time"]
                ]
                
                if clip_words:
                    ass_path = clips_dir / f"{clip_name}.ass"
                    style = get_style_preset(caption_style)
                    generate_ass_subtitles(
                        clip_words,
                        str(ass_path),
                        style=style,
                        time_offset=-clip["start_time"],
                    )
            
            # Render the clip
            render_final_clip(
                input_path,
                clip_path,
                clip["start_time"],
                clip["end_time"],
                ass_path=ass_path,
                crop_vertical=crop_vertical,
                auto_center=auto_center,
            )
            
            # Create thumbnail
            thumb_path = clips_dir / f"{clip_name}_thumb.jpg"
            try:
                create_thumbnail(clip_path, thumb_path)
            except:
                thumb_path = None
            
            results.append({
                "index": i + 1,
                "video_path": str(clip_path),
                "video_url": f"/api/clipper/clips/{job_id}/{clip_name}.mp4",
                "thumbnail_url": f"/api/clipper/clips/{job_id}/{clip_name}_thumb.jpg" if thumb_path else None,
                "start_time": clip["start_time"],
                "end_time": clip["end_time"],
                "duration": clip["duration"],
                "virality_score": clip["virality_score"],
                "virality_reason": clip["virality_reason"],
                "suggested_caption": clip["suggested_caption"],
                "suggested_hashtags": clip["suggested_hashtags"],
                "category": clip["category"],
                "text": clip["text"],
            })
        
        # Save results
        with open(job_dir / "render_results.json", "w") as f:
            json.dump(results, f, indent=2)
        
        # Store results
        from .pipeline import PipelineResult, ClipResult
        
        clip_results = [
            ClipResult(
                index=r["index"],
                video_path=r["video_path"],
                thumbnail_path=None,
                start_time=r["start_time"],
                end_time=r["end_time"],
                duration=r["duration"],
                score=r["virality_score"] / 100.0,
                text=r["text"][:200],
            )
            for r in results
        ]
        
        _job_results[job_id] = PipelineResult(
            success=True,
            source_video=str(input_path),
            output_dir=str(job_dir),
            transcript_json=str(transcript_path) if transcript_path.exists() else "",
            transcript_srt="",
            clips=clip_results,
            total_duration=0,
            processing_time=0,
        )
        
        # Also store the full results with virality info
        _viral_candidates[job_id + "_results"] = results
        
        update_job_progress(
            job_id, "completed", 1.0,
            "Rendering complete",
            f"Created {len(results)} viral clips!"
        )
        
        # Save to history
        youtube_url = _worker_job_configs.get(job_id, {}).get("youtube_url")
        add_to_clip_history(job_id, results, youtube_url)
        
        logger.info(f"Smart render complete for {job_id}: {len(results)} clips")
        
    except Exception as e:
        logger.exception(f"Smart render failed for {job_id}")
        update_job_progress(job_id, "failed", 0, "Render failed", str(e))
        _job_progress[job_id]["error"] = str(e)


@router.get("/smart/{job_id}/results")
async def get_smart_results(job_id: str):
    """Get the rendered clips with virality info."""
    if job_id not in _job_progress:
        raise HTTPException(status_code=404, detail="Job not found")
    
    progress = _job_progress[job_id]
    
    if progress["status"] != "completed":
        return {
            "status": progress["status"],
            "progress": progress["progress"],
            "stage": progress["stage"],
            "clips": None,
        }
    
    results = _viral_candidates.get(job_id + "_results", [])
    
    return {
        "status": "completed",
        "clips": results,
    }


@router.post("/smart/edit-clip")
async def edit_clip_with_ai(
    background_tasks: BackgroundTasks,
    job_id: str = Form(""),
    clip_index: int = Form(0),
    edit_request: str = Form(""),
    original_start: float = Form(0),
    original_end: float = Form(0),
    caption_color: str = Form("#FFFFFF"),
    animation_color: str = Form("#FFFF00"),
    caption_size: int = Form(80),
    video_vibe: str = Form("default"),
):
    """
    AI-powered clip editing based on user request.
    Takes natural language instructions and re-renders the clip.
    """
    if not edit_request:
        raise HTTPException(status_code=400, detail="Edit request is required")
    
    add_job_log(job_id, f"🤖 Edit request for clip {clip_index + 1}: {edit_request}")
    
    # Use GPT to interpret the edit request and apply changes
    try:
        from openai import OpenAI
        import os
        
        client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": """You are a video editing AI. Parse the user's edit request and return JSON with the changes to make.
                
Available changes:
- music_style: "upbeat", "chill", "dramatic", "funny", "none"
- zoom_intensity: 0.0 to 1.0 (0 = no zoom, 1 = aggressive zoom)
- caption_animation: "karaoke", "pop", "bounce", "fade", "none"
- color_grade: "viral", "cinematic", "clean", "moody"
- speed: 0.5 to 2.0 (1.0 = normal)
- trim_start: seconds to trim from start
- trim_end: seconds to trim from end

Return ONLY valid JSON like: {"music_style": "dramatic", "zoom_intensity": 0.8}"""},
                {"role": "user", "content": f"Edit request: {edit_request}"}
            ],
            temperature=0.3,
            max_tokens=200,
        )
        
        import json
        import re
        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            content = re.sub(r'^```json?\n?', '', content)
            content = re.sub(r'\n?```$', '', content)
        
        edit_params = json.loads(content)
        add_job_log(job_id, f"AI interpreted edits: {edit_params}", "success")
        
        # TODO: Actually apply these edits in background task
        # For now, return success
        return {
            "success": True,
            "message": "Edit request received",
            "interpreted_changes": edit_params,
        }
        
    except Exception as e:
        logger.error(f"Edit request failed: {e}")
        return {
            "success": False,
            "error": str(e),
        }


@router.get("/history")
async def get_clip_history(limit: int = 20):
    """Get history of completed clip jobs."""
    return {
        "history": _clip_history[:limit],
        "total": len(_clip_history),
    }


# ============================================================================
# Social Media Posting Endpoints
# ============================================================================

@router.post("/post/instagram")
async def post_to_instagram(
    job_id: str = Form(""),
    clip_index: int = Form(0),
    video_url: str = Form(""),
    caption: str = Form(""),
    hook: str = Form(""),
    category: str = Form("default"),
):
    """Post a clip to Instagram Reels."""
    from ..social_posting import SocialMediaManager
    from ...config import get_settings
    
    settings = get_settings()
    manager = SocialMediaManager(settings)
    
    # If video_url not provided, construct from job_id
    if not video_url and job_id:
        video_url = f"/api/clipper/clips/{job_id}/clip_{clip_index + 1:02d}.mp4"
    
    if not video_url:
        return {"success": False, "error": "No video URL provided"}
    
    # Make absolute URL for Instagram
    base_url = os.environ.get("BASE_URL", "https://instagramposting-production-4e91.up.railway.app")
    if video_url.startswith("/"):
        video_url = f"{base_url}{video_url}"
    
    result = await manager.post_to_instagram(video_url, caption, hook, category)
    return result


@router.post("/post/tiktok")
async def post_to_tiktok(
    job_id: str = Form(""),
    clip_index: int = Form(0),
    video_url: str = Form(""),
    caption: str = Form(""),
    hook: str = Form(""),
    category: str = Form("default"),
):
    """Post a clip to TikTok."""
    from ..social_posting import SocialMediaManager
    from ...config import get_settings
    
    settings = get_settings()
    manager = SocialMediaManager(settings)
    
    # If video_url not provided, construct from job_id
    if not video_url and job_id:
        video_url = f"/api/clipper/clips/{job_id}/clip_{clip_index + 1:02d}.mp4"
    
    if not video_url:
        return {"success": False, "error": "No video URL provided"}
    
    # Make absolute URL for TikTok (must be from allowed domain)
    base_url = os.environ.get("BASE_URL", "https://mccarthydemo.site")
    if video_url.startswith("/"):
        video_url = f"{base_url}{video_url}"
    
    result = await manager.post_to_tiktok(video_url, caption, hook, category)
    return result


@router.post("/post/youtube")
async def post_to_youtube(
    job_id: str = Form(""),
    clip_index: int = Form(0),
    caption: str = Form(""),
    hook: str = Form(""),
    category: str = Form("default"),
):
    """Post a clip to YouTube Shorts."""
    from ..social_posting import SocialMediaManager
    from ...config import get_settings
    
    settings = get_settings()
    manager = SocialMediaManager(settings)
    
    if not job_id:
        return {"success": False, "error": "Job ID required for YouTube upload"}
    
    # Get video file path
    job_dir = GENERATED_DIR / job_id
    clip_name = f"clip_{clip_index + 1:02d}"
    video_path = job_dir / "clips" / f"{clip_name}.mp4"
    
    if not video_path.exists():
        return {"success": False, "error": f"Video file not found: {video_path}"}
    
    result = await manager.post_to_youtube(video_path, caption, hook, category)
    return result


@router.post("/post/all")
async def post_to_all_platforms(
    job_id: str = Form(""),
    clip_index: int = Form(0),
    video_url: str = Form(""),
    caption: str = Form(""),
    hook: str = Form(""),
    category: str = Form("default"),
):
    """Post a clip to all configured platforms (Instagram, TikTok, YouTube)."""
    from ..social_posting import SocialMediaManager
    from ...config import get_settings
    
    settings = get_settings()
    manager = SocialMediaManager(settings)
    
    if not job_id:
        return {"success": False, "error": "Job ID required"}
    
    # Get video file path for YouTube
    job_dir = GENERATED_DIR / job_id
    clip_name = f"clip_{clip_index + 1:02d}"
    video_path = job_dir / "clips" / f"{clip_name}.mp4"
    
    # Construct video URL for Instagram/TikTok
    if not video_url:
        video_url = f"/api/clipper/clips/{job_id}/clip_{clip_index + 1:02d}.mp4"
    
    # Make absolute URL
    base_url = os.environ.get("BASE_URL", "https://instagramposting-production-4e91.up.railway.app")
    if video_url.startswith("/"):
        full_video_url = f"{base_url}{video_url}"
    else:
        full_video_url = video_url
    
    # TikTok needs the custom domain
    tiktok_url = full_video_url.replace(base_url, "https://mccarthydemo.site") if settings.tiktok_client_key else full_video_url
    
    results = await manager.post_to_all(
        video_path=video_path,
        video_url=full_video_url,
        caption=caption,
        hook=hook,
        category=category,
    )
    
    return results


@router.get("/post/status")
async def get_posting_status():
    """Check which platforms are configured for posting."""
    from ...config import get_settings
    
    settings = get_settings()
    
    return {
        "instagram": {
            "configured": bool(settings.instagram_access_token),
            "ready": bool(settings.instagram_access_token),
        },
        "tiktok": {
            "configured": bool(settings.tiktok_client_key),
            "ready": bool(settings.tiktok_client_key and settings.tiktok_access_token),
            "auth_url": f"https://mccarthydemo.site/tiktok/auth" if settings.tiktok_client_key else None,
        },
        "youtube": {
            "configured": bool(settings.youtube_api_key),
            "ready": bool(settings.youtube_refresh_token),
            "needs_oauth": bool(settings.youtube_api_key and not settings.youtube_refresh_token),
        },
    }


# TikTok OAuth callback
@router.get("/tiktok/callback")
async def tiktok_oauth_callback(code: str = "", state: str = ""):
    """Handle TikTok OAuth callback."""
    from ..social_posting import exchange_tiktok_code
    from ...config import get_settings
    
    if not code:
        return {"error": "No authorization code received"}
    
    settings = get_settings()
    
    result = await exchange_tiktok_code(
        code=code,
        client_key=settings.tiktok_client_key,
        client_secret=settings.tiktok_client_secret,
        redirect_uri=settings.tiktok_redirect_uri,
    )
    
    if "access_token" in result:
        # In production, you'd want to save this token
        return {
            "success": True,
            "message": "TikTok connected! Copy this access token to your environment:",
            "access_token": result["access_token"],
            "refresh_token": result.get("refresh_token"),
            "expires_in": result.get("expires_in"),
        }
    
    return {"success": False, "error": result}


@router.get("/tiktok/auth")
async def tiktok_auth_redirect():
    """Redirect to TikTok OAuth."""
    from ..social_posting import get_tiktok_auth_url
    from ...config import get_settings
    from fastapi.responses import RedirectResponse
    
    settings = get_settings()
    
    auth_url = get_tiktok_auth_url(
        client_key=settings.tiktok_client_key,
        redirect_uri=settings.tiktok_redirect_uri,
    )
    
    return RedirectResponse(url=auth_url)
