"""API routes for video clipper and captioner."""

import asyncio
import logging
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, File, UploadFile, HTTPException, BackgroundTasks, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .pipeline import ClipperPipeline, PipelineConfig, PipelineResult
from .crop import check_ffmpeg, get_ffmpeg_install_instructions
from .captions import STYLE_PRESETS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/clipper", tags=["Video Clipper"])

# Store for job progress
_job_progress = {}
_job_results = {}

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
    whisper_model: str = "base"
    burn_captions: bool = True
    crop_vertical: bool = True
    auto_center: bool = True


class ClipperJobResponse(BaseModel):
    """Response for clip job status."""
    job_id: str
    status: str
    progress: float
    stage: str
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


@router.get("/status")
async def check_clipper_status():
    """Check if video clipper dependencies are available."""
    issues = []
    
    # Check FFmpeg
    if not check_ffmpeg():
        issues.append({
            "name": "FFmpeg",
            "status": "missing",
            "instructions": get_ffmpeg_install_instructions()
        })
    else:
        issues.append({"name": "FFmpeg", "status": "installed"})
    
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
    whisper_model: str = Form("base"),
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
        with open(video_path, "wb") as f:
            content = await file.read()
            f.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    
    # Initialize job progress
    _job_progress[job_id] = {"status": "queued", "progress": 0.0, "stage": "Uploaded"}
    
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
    
    # Start processing in background
    if background_tasks:
        background_tasks.add_task(
            run_clipper_job, job_id, str(video_path), str(upload_dir), config
        )
    else:
        # Fallback: run in thread
        asyncio.create_task(
            asyncio.to_thread(run_clipper_job_sync, job_id, str(video_path), str(upload_dir), config)
        )
    
    return {
        "job_id": job_id,
        "status": "processing",
        "message": "Video uploaded. Processing started.",
    }


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
    # Validate path exists
    if not Path(video_path).exists():
        raise HTTPException(status_code=404, detail=f"Video not found: {video_path}")
    
    # Create job ID
    job_id = str(uuid.uuid4())[:8]
    
    # Create output directory
    output_dir = CLIPS_OUTPUT_DIR / job_id
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize job progress
    _job_progress[job_id] = {"status": "queued", "progress": 0.0, "stage": "Starting"}
    
    # Build config
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
    
    # Start processing
    if background_tasks:
        background_tasks.add_task(
            run_clipper_job, job_id, video_path, str(output_dir), pipeline_config
        )
    
    return {
        "job_id": job_id,
        "status": "processing",
        "message": "Processing started.",
    }


async def run_clipper_job(
    job_id: str,
    video_path: str,
    output_dir: str,
    config: PipelineConfig
):
    """Run the clipper pipeline as a background job."""
    await asyncio.to_thread(run_clipper_job_sync, job_id, video_path, output_dir, config)


def run_clipper_job_sync(
    job_id: str,
    video_path: str,
    output_dir: str,
    config: PipelineConfig
):
    """Synchronous clipper job runner."""
    def progress_callback(stage: str, progress: float):
        _job_progress[job_id] = {
            "status": "processing",
            "progress": progress,
            "stage": stage
        }
    
    try:
        _job_progress[job_id] = {
            "status": "processing",
            "progress": 0.0,
            "stage": "Initializing"
        }
        
        pipeline = ClipperPipeline(config, progress_callback=progress_callback)
        result = pipeline.run(video_path, output_dir)
        
        if result.success:
            _job_progress[job_id] = {
                "status": "completed",
                "progress": 1.0,
                "stage": "Complete"
            }
            _job_results[job_id] = result
        else:
            _job_progress[job_id] = {
                "status": "failed",
                "progress": 0.0,
                "stage": "Failed",
                "error": result.error
            }
            _job_results[job_id] = result
            
    except Exception as e:
        logger.exception(f"Job {job_id} failed")
        _job_progress[job_id] = {
            "status": "failed",
            "progress": 0.0,
            "stage": "Error",
            "error": str(e)
        }


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
        error=progress.get("error"),
        result=result_data
    )


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
    # Check in clips subdirectory first
    file_path = CLIPS_OUTPUT_DIR / job_id / "clips" / filename
    if not file_path.exists():
        # Check in main job directory
        file_path = CLIPS_OUTPUT_DIR / job_id / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    # Determine media type
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
    job_dir = CLIPS_OUTPUT_DIR / job_id
    
    if job_dir.exists():
        shutil.rmtree(job_dir)
    
    if job_id in _job_progress:
        del _job_progress[job_id]
    
    if job_id in _job_results:
        del _job_results[job_id]
    
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
        }
        
        if progress.get("error"):
            job_info["error"] = progress["error"]
        
        if progress["status"] == "completed" and job_id in _job_results:
            result = _job_results[job_id]
            job_info["clips_count"] = len(result.clips)
        
        jobs.append(job_info)
    
    return {"jobs": jobs}
