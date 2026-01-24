"""API routes for video clipper and captioner."""

import asyncio
import logging
import os
import shutil
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, File, UploadFile, HTTPException, BackgroundTasks, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .pipeline import ClipperPipeline, PipelineConfig, PipelineResult
from .crop import check_ffmpeg, get_ffmpeg_install_instructions, get_ffmpeg_path
from .captions import STYLE_PRESETS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/clipper", tags=["Video Clipper"])

# Store for job progress and control
_job_progress = {}
_job_results = {}
_job_cancel_flags = {}  # Track which jobs should be cancelled
_job_threads = {}  # Track running threads

# Output directory
CLIPS_OUTPUT_DIR = Path("generated_clips")
CLIPS_OUTPUT_DIR.mkdir(exist_ok=True)


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
        'format': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best',
        'outtmpl': str(output_path.with_suffix('')),
        'merge_output_format': 'mp4',
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'progress_hooks': [progress_hook],
        'socket_timeout': 30,  # Timeout for network operations
        'retries': 3,
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
