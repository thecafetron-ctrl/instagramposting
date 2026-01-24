"""
Local Worker for Video Clipper

This script runs on your local PC and processes video jobs from Railway.
It polls the Railway server for pending jobs, processes them locally using
your computer's power, and uploads results back.

Usage:
    python -m app.services.clipper.worker --server https://your-railway-app.up.railway.app

Or set environment variable:
    export CLIPPER_SERVER=https://your-railway-app.up.railway.app
    python -m app.services.clipper.worker
"""

import argparse
import json
import logging
import os
import sys
import time
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional
import requests

# Setup logging with colors
class ColoredFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record):
        color = self.COLORS.get(record.levelname, '')
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)

# Configure logging
handler = logging.StreamHandler()
handler.setFormatter(ColoredFormatter(
    '%(asctime)s │ %(levelname)s │ %(message)s',
    datefmt='%H:%M:%S'
))
logging.basicConfig(level=logging.INFO, handlers=[handler])
logger = logging.getLogger(__name__)


class LocalWorker:
    """Local worker that processes video jobs from a remote server."""
    
    def __init__(self, server_url: str, worker_id: str = None):
        self.server_url = server_url.rstrip('/')
        self.worker_id = worker_id or f"worker-{os.getpid()}"
        self.api_base = f"{self.server_url}/api/clipper"
        self.running = True
        self.current_job = None
        
        # Create temp directory for processing
        self.work_dir = Path(tempfile.gettempdir()) / "clipper_worker"
        self.work_dir.mkdir(exist_ok=True)
        
        logger.info(f"🖥️  Local Worker initialized")
        logger.info(f"📡 Server: {self.server_url}")
        logger.info(f"🆔 Worker ID: {self.worker_id}")
        logger.info(f"📁 Work directory: {self.work_dir}")
    
    def check_server(self) -> bool:
        """Check if the server is reachable."""
        try:
            resp = requests.get(f"{self.api_base}/status", timeout=10)
            data = resp.json()
            logger.info(f"✅ Server connected - Status: {data.get('status', 'unknown')}")
            return True
        except Exception as e:
            logger.error(f"❌ Cannot connect to server: {e}")
            return False
    
    def register_worker(self) -> bool:
        """Register this worker with the server."""
        try:
            resp = requests.post(
                f"{self.api_base}/worker/register",
                json={
                    "worker_id": self.worker_id,
                    "capabilities": ["transcribe", "render", "crop"],
                    "platform": sys.platform,
                },
                timeout=10
            )
            if resp.status_code == 200:
                logger.info(f"✅ Worker registered with server")
                return True
            else:
                # Server might not have worker endpoints yet, that's ok
                logger.warning(f"⚠️  Worker registration not available (continuing anyway)")
                return True
        except Exception as e:
            logger.warning(f"⚠️  Could not register worker: {e} (continuing anyway)")
            return True
    
    def fetch_pending_job(self) -> Optional[dict]:
        """Fetch a pending job from the server."""
        try:
            resp = requests.get(
                f"{self.api_base}/worker/jobs/pending",
                params={"worker_id": self.worker_id},
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("job"):
                    return data["job"]
            return None
        except Exception as e:
            logger.debug(f"No pending jobs or error: {e}")
            return None
    
    def update_job_progress(self, job_id: str, progress: float, stage: str, detail: str = None):
        """Update job progress on the server."""
        try:
            requests.post(
                f"{self.api_base}/worker/jobs/{job_id}/progress",
                json={
                    "worker_id": self.worker_id,
                    "progress": progress,
                    "stage": stage,
                    "detail": detail or "",
                },
                timeout=5
            )
        except Exception as e:
            logger.debug(f"Could not update progress: {e}")
    
    def download_video(self, job_id: str, video_url: str) -> Path:
        """Download video from server to local work directory."""
        job_dir = self.work_dir / job_id
        job_dir.mkdir(exist_ok=True)
        
        video_path = job_dir / "input.mp4"
        
        logger.info(f"⬇️  Downloading video...")
        
        # Handle YouTube URL or direct file URL
        if "youtube.com" in video_url or "youtu.be" in video_url:
            logger.info(f"📺 YouTube video detected, downloading with yt-dlp...")
            self._download_youtube(video_url, video_path, job_id)
        else:
            # Direct download from server
            full_url = video_url if video_url.startswith('http') else f"{self.server_url}{video_url}"
            resp = requests.get(full_url, stream=True, timeout=300)
            resp.raise_for_status()
            
            total_size = int(resp.headers.get('content-length', 0))
            downloaded = 0
            
            with open(video_path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        pct = downloaded / total_size
                        self.update_job_progress(
                            job_id, pct * 0.1,
                            "Downloading video",
                            f"{downloaded/1024/1024:.1f}MB / {total_size/1024/1024:.1f}MB"
                        )
        
        logger.info(f"✅ Video downloaded: {video_path}")
        return video_path
    
    def _download_youtube(self, url: str, output_path: Path, job_id: str):
        """Download YouTube video using yt-dlp."""
        import yt_dlp
        
        def progress_hook(d):
            if d['status'] == 'downloading':
                try:
                    downloaded = d.get('downloaded_bytes', 0)
                    total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                    if total > 0:
                        pct = downloaded / total
                        self.update_job_progress(
                            job_id, pct * 0.1,
                            "Downloading from YouTube",
                            f"{downloaded/1024/1024:.1f}MB / {total/1024/1024:.1f}MB"
                        )
                        logger.info(f"⬇️  {downloaded/1024/1024:.1f}MB / {total/1024/1024:.1f}MB ({pct*100:.0f}%)")
                except:
                    pass
        
        ydl_opts = {
            'format': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best',
            'outtmpl': str(output_path.with_suffix('')),
            'merge_output_format': 'mp4',
            'progress_hooks': [progress_hook],
            'quiet': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        # Find the output file
        for ext in ['.mp4', '.mkv', '.webm']:
            candidate = output_path.with_suffix(ext)
            if candidate.exists():
                if candidate != output_path:
                    candidate.rename(output_path)
                break
    
    def process_job(self, job: dict) -> dict:
        """Process a video clipping job locally."""
        job_id = job["job_id"]
        config = job.get("config", {})
        video_source = job.get("video_url") or job.get("youtube_url")
        
        logger.info(f"")
        logger.info(f"{'='*60}")
        logger.info(f"🎬 Processing Job: {job_id}")
        logger.info(f"{'='*60}")
        logger.info(f"📹 Source: {video_source[:80]}...")
        logger.info(f"⚙️  Config: {json.dumps(config, indent=2)}")
        
        self.current_job = job_id
        job_dir = self.work_dir / job_id
        job_dir.mkdir(exist_ok=True)
        
        try:
            # Download video
            video_path = self.download_video(job_id, video_source)
            
            # Import pipeline
            from .pipeline import ClipperPipeline, PipelineConfig
            
            # Setup progress callback
            def progress_callback(stage: str, progress: float):
                # Adjust progress (download was 0-10%, processing is 10-100%)
                adjusted = 0.1 + (progress * 0.9)
                self.update_job_progress(job_id, adjusted, stage, stage)
                logger.info(f"📊 [{adjusted*100:.0f}%] {stage}")
            
            # Build config
            pipeline_config = PipelineConfig(
                num_clips=config.get("num_clips", 10),
                min_duration=config.get("min_duration", 20),
                max_duration=config.get("max_duration", 60),
                pause_threshold=config.get("pause_threshold", 0.7),
                caption_style=config.get("caption_style", "default"),
                whisper_model=config.get("whisper_model", "base"),  # Use better model locally
                burn_captions=config.get("burn_captions", True),
                crop_vertical=config.get("crop_vertical", True),
                auto_center=config.get("auto_center", True),
            )
            
            # Run pipeline
            logger.info(f"🚀 Starting pipeline...")
            pipeline = ClipperPipeline(pipeline_config, progress_callback=progress_callback)
            result = pipeline.run(video_path, job_dir)
            
            if result.success:
                logger.info(f"✅ Job completed successfully!")
                logger.info(f"📁 Output: {job_dir}")
                logger.info(f"🎥 Clips: {len(result.clips)}")
                logger.info(f"⏱️  Processing time: {result.processing_time:.1f}s")
                
                return {
                    "success": True,
                    "job_id": job_id,
                    "clips": [
                        {
                            "index": c.index,
                            "path": c.video_path,
                            "start_time": c.start_time,
                            "end_time": c.end_time,
                            "duration": c.duration,
                            "score": c.score,
                            "text": c.text,
                        }
                        for c in result.clips
                    ],
                    "processing_time": result.processing_time,
                    "output_dir": str(job_dir),
                }
            else:
                logger.error(f"❌ Pipeline failed: {result.error}")
                return {
                    "success": False,
                    "job_id": job_id,
                    "error": result.error,
                }
                
        except Exception as e:
            logger.exception(f"❌ Job failed with exception")
            return {
                "success": False,
                "job_id": job_id,
                "error": str(e),
            }
        finally:
            self.current_job = None
    
    def upload_results(self, job_id: str, result: dict) -> bool:
        """Upload processing results back to the server."""
        if not result.get("success"):
            # Just report failure
            try:
                requests.post(
                    f"{self.api_base}/worker/jobs/{job_id}/complete",
                    json={
                        "worker_id": self.worker_id,
                        "success": False,
                        "error": result.get("error", "Unknown error"),
                    },
                    timeout=30
                )
            except Exception as e:
                logger.error(f"Could not report failure: {e}")
            return False
        
        logger.info(f"⬆️  Uploading results to server...")
        
        try:
            # Upload each clip
            clips_info = []
            for clip in result.get("clips", []):
                clip_path = Path(clip["path"])
                if clip_path.exists():
                    logger.info(f"   Uploading clip {clip['index']}...")
                    with open(clip_path, 'rb') as f:
                        resp = requests.post(
                            f"{self.api_base}/worker/jobs/{job_id}/upload-clip",
                            files={"file": (clip_path.name, f, "video/mp4")},
                            data={
                                "index": clip["index"],
                                "start_time": clip["start_time"],
                                "end_time": clip["end_time"],
                                "duration": clip["duration"],
                                "score": clip["score"],
                                "text": clip["text"],
                            },
                            timeout=120
                        )
                        if resp.status_code == 200:
                            clips_info.append(resp.json())
            
            # Mark job complete
            requests.post(
                f"{self.api_base}/worker/jobs/{job_id}/complete",
                json={
                    "worker_id": self.worker_id,
                    "success": True,
                    "clips_count": len(clips_info),
                    "processing_time": result.get("processing_time", 0),
                },
                timeout=30
            )
            
            logger.info(f"✅ Results uploaded successfully!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to upload results: {e}")
            return False
    
    def cleanup_job(self, job_id: str):
        """Clean up local files for a completed job."""
        job_dir = self.work_dir / job_id
        if job_dir.exists():
            shutil.rmtree(job_dir)
            logger.info(f"🧹 Cleaned up job directory: {job_dir}")
    
    def run(self, poll_interval: int = 5):
        """Main worker loop."""
        logger.info(f"")
        logger.info(f"{'='*60}")
        logger.info(f"🚀 LOCAL WORKER STARTED")
        logger.info(f"{'='*60}")
        logger.info(f"")
        logger.info(f"Waiting for jobs from: {self.server_url}")
        logger.info(f"Press Ctrl+C to stop")
        logger.info(f"")
        
        if not self.check_server():
            logger.error("Cannot start worker - server unreachable")
            return
        
        self.register_worker()
        
        consecutive_errors = 0
        
        while self.running:
            try:
                # Check for pending jobs
                job = self.fetch_pending_job()
                
                if job:
                    consecutive_errors = 0
                    result = self.process_job(job)
                    self.upload_results(job["job_id"], result)
                    
                    # Optional: cleanup after upload
                    # self.cleanup_job(job["job_id"])
                else:
                    # No jobs, wait and poll again
                    time.sleep(poll_interval)
                    
            except KeyboardInterrupt:
                logger.info(f"\n⏹️  Shutting down worker...")
                self.running = False
                break
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"Worker error: {e}")
                
                if consecutive_errors > 10:
                    logger.error("Too many consecutive errors, stopping worker")
                    break
                
                time.sleep(min(poll_interval * consecutive_errors, 60))
        
        logger.info(f"👋 Worker stopped")


def main():
    parser = argparse.ArgumentParser(
        description="Local worker for video clipper - processes jobs using your PC's power"
    )
    parser.add_argument(
        "--server", "-s",
        default=os.environ.get("CLIPPER_SERVER", "http://localhost:8000"),
        help="Server URL (default: $CLIPPER_SERVER or http://localhost:8000)"
    )
    parser.add_argument(
        "--worker-id", "-w",
        default=None,
        help="Worker ID (default: auto-generated)"
    )
    parser.add_argument(
        "--poll-interval", "-p",
        type=int,
        default=5,
        help="Seconds between polling for jobs (default: 5)"
    )
    
    args = parser.parse_args()
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║           🎬 VIDEO CLIPPER - LOCAL WORKER                    ║
╠══════════════════════════════════════════════════════════════╣
║  This worker processes video jobs using YOUR computer's      ║
║  power instead of the cloud server.                          ║
║                                                              ║
║  Server: {args.server:<50} ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    worker = LocalWorker(
        server_url=args.server,
        worker_id=args.worker_id,
    )
    worker.run(poll_interval=args.poll_interval)


if __name__ == "__main__":
    main()
