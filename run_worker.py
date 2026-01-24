#!/usr/bin/env python3
"""
Local Worker for Video Clipper

Run this script on your PC to process video jobs using your local compute power.
The UI runs on Railway, but the heavy processing happens on your machine.

Usage:
    python run_worker.py https://your-railway-app.up.railway.app

Or with custom settings:
    python run_worker.py https://your-railway-app.up.railway.app --poll-interval 3
"""

import argparse
import json
import logging
import os
import sys
import time
import tempfile
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional

# Check for requests library
try:
    import requests
except ImportError:
    print("Installing requests...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
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


def check_ffmpeg():
    """Check if FFmpeg is installed."""
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False


def check_yt_dlp():
    """Check if yt-dlp is installed."""
    try:
        result = subprocess.run(['yt-dlp', '--version'], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False


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
                logger.warning(f"⚠️  Worker registration returned {resp.status_code}")
                return True
        except Exception as e:
            logger.warning(f"⚠️  Could not register worker: {e}")
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
            resp = requests.post(
                f"{self.api_base}/worker/jobs/{job_id}/progress",
                json={
                    "worker_id": self.worker_id,
                    "progress": progress,
                    "stage": stage,
                    "detail": detail or "",
                },
                timeout=5
            )
            return resp.json().get("should_stop", False)
        except Exception as e:
            logger.debug(f"Could not update progress: {e}")
            return False
    
    def download_video(self, job_id: str, video_url: str = None, youtube_url: str = None) -> Path:
        """Download video to local work directory."""
        job_dir = self.work_dir / job_id
        job_dir.mkdir(exist_ok=True)
        
        video_path = job_dir / "input.mp4"
        
        # Railway has already downloaded YouTube videos - just fetch from server
        if video_url:
            logger.info(f"⬇️  Fetching video from Railway (already downloaded)...")
            full_url = video_url if video_url.startswith('http') else f"{self.server_url}{video_url}"
            resp = requests.get(full_url, stream=True, timeout=600)
            resp.raise_for_status()
            
            total_size = int(resp.headers.get('content-length', 0))
            downloaded = 0
            last_log = 0
            
            with open(video_path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=65536):  # 64KB chunks for speed
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        pct = downloaded / total_size
                        self.update_job_progress(
                            job_id, pct * 0.1,
                            "Transferring from Railway",
                            f"{downloaded/1024/1024:.1f}MB / {total_size/1024/1024:.1f}MB"
                        )
                        # Log every 5MB
                        if downloaded - last_log > 5*1024*1024:
                            logger.info(f"   📥 {downloaded/1024/1024:.1f}MB / {total_size/1024/1024:.1f}MB ({pct*100:.0f}%)")
                            last_log = downloaded
            
            logger.info(f"✅ Video transferred: {video_path} ({downloaded/1024/1024:.1f}MB)")
        
        elif youtube_url:
            # Fallback: download YouTube directly if no video_url provided
            logger.info(f"📺 Downloading from YouTube (fallback)...")
            self._download_youtube(youtube_url, video_path, job_id)
        
        return video_path
    
    def _download_youtube(self, url: str, output_path: Path, job_id: str):
        """Download YouTube video using yt-dlp."""
        try:
            import yt_dlp
        except ImportError:
            logger.info("Installing yt-dlp...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "yt-dlp"])
            import yt_dlp
        
        def progress_hook(d):
            if d['status'] == 'downloading':
                try:
                    downloaded = d.get('downloaded_bytes', 0)
                    total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                    if total > 0:
                        pct = downloaded / total
                        should_stop = self.update_job_progress(
                            job_id, pct * 0.1,
                            "Downloading from YouTube",
                            f"{downloaded/1024/1024:.1f}MB / {total/1024/1024:.1f}MB"
                        )
                        if should_stop:
                            raise Exception("Job cancelled")
                except Exception as e:
                    if "cancelled" in str(e).lower():
                        raise
        
        logger.info(f"🎬 yt-dlp: Fetching video info...")
        
        ydl_opts = {
            'format': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best',
            'outtmpl': str(output_path.with_suffix('')),
            'merge_output_format': 'mp4',
            'progress_hooks': [progress_hook],
            'quiet': False,
            'no_warnings': False,
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
    
    def process_smart_job(self, job_id: str, video_path: Path, config: dict) -> dict:
        """Process a smart job: transcribe, analyze for viral moments, return candidates."""
        job_dir = self.work_dir / job_id
        
        logger.info(f"")
        logger.info(f"🧠 SMART PROCESSING MODE")
        logger.info(f"   Transcription + AI Analysis on YOUR PC")
        logger.info(f"")
        
        whisper_model = config.get('whisper_model', 'base')
        num_clips = config.get('num_clips', 10)
        min_duration = config.get('min_duration', 15)
        max_duration = config.get('max_duration', 60)
        
        # Step 1: Transcribe locally
        logger.info(f"📝 Step 1: Transcribing with Whisper ({whisper_model})...")
        self.update_job_progress(job_id, 0.1, "Transcribing audio", f"Using Whisper {whisper_model} model on your PC...")
        
        try:
            # Try to use faster-whisper
            from faster_whisper import WhisperModel
            
            logger.info(f"   Loading Whisper model '{whisper_model}'...")
            model = WhisperModel(whisper_model, device="cpu", compute_type="int8")
            
            logger.info(f"   Transcribing...")
            segments_gen, info = model.transcribe(
                str(video_path),
                word_timestamps=True,
                vad_filter=True,
            )
            
            # Collect segments and words
            transcript = {
                "language": info.language,
                "duration": info.duration,
                "segments": []
            }
            
            total_duration = info.duration
            for seg in segments_gen:
                words = []
                if seg.words:
                    for w in seg.words:
                        words.append({
                            "word": w.word.strip(),
                            "start": w.start,
                            "end": w.end,
                        })
                
                transcript["segments"].append({
                    "text": seg.text.strip(),
                    "start": seg.start,
                    "end": seg.end,
                    "words": words,
                })
                
                # Update progress
                if total_duration > 0:
                    progress = 0.1 + (seg.end / total_duration) * 0.4
                    self.update_job_progress(
                        job_id, progress,
                        "Transcribing audio",
                        f"{seg.end:.0f}s / {total_duration:.0f}s transcribed"
                    )
            
            logger.info(f"   ✓ Transcription complete: {len(transcript['segments'])} segments")
            
            # Save transcript
            transcript_path = job_dir / "transcript.json"
            with open(transcript_path, "w") as f:
                json.dump(transcript, f, indent=2)
            
        except ImportError:
            logger.error("faster-whisper not installed!")
            logger.info("Installing: pip install faster-whisper")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "faster-whisper"])
            return {"success": False, "error": "Please restart worker - faster-whisper was just installed"}
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return {"success": False, "error": f"Transcription failed: {str(e)}"}
        
        # Step 2: Analyze for viral moments
        logger.info(f"")
        logger.info(f"🔥 Step 2: Analyzing for viral moments...")
        self.update_job_progress(job_id, 0.55, "Analyzing transcript", "Finding viral-worthy moments...")
        
        # Extract all words
        all_words = []
        for seg in transcript["segments"]:
            all_words.extend(seg.get("words", []))
        
        # Try to use GPT if available, otherwise use heuristics
        candidates = self._analyze_viral_moments(all_words, num_clips, min_duration, max_duration)
        
        logger.info(f"   ✓ Found {len(candidates)} potential viral moments")
        
        # Save candidates
        candidates_path = job_dir / "viral_candidates.json"
        with open(candidates_path, "w") as f:
            json.dump(candidates, f, indent=2)
        
        # Upload candidates to server
        self.update_job_progress(job_id, 0.9, "Uploading results", "Sending candidates to server...")
        
        try:
            resp = requests.post(
                f"{self.api_base}/worker/jobs/{job_id}/candidates",
                json={"candidates": candidates, "transcript": transcript},
                timeout=30
            )
            if resp.status_code == 200:
                logger.info(f"   ✓ Candidates uploaded to server")
            else:
                logger.warning(f"   ⚠ Failed to upload candidates: {resp.status_code}")
        except Exception as e:
            logger.warning(f"   ⚠ Failed to upload candidates: {e}")
        
        return {
            "success": True,
            "candidates": candidates,
            "transcript": transcript,
            "phase": "analyzed",
        }
    
    def _analyze_viral_moments(self, words: list, num_clips: int, min_duration: float, max_duration: float) -> list:
        """Analyze transcript for viral moments using heuristics or GPT."""
        
        # Build sentences from words
        sentences = []
        current_sentence = {"start": 0, "end": 0, "text": "", "words": []}
        
        for word in words:
            word_text = word.get("word", "")
            current_sentence["words"].append(word)
            current_sentence["text"] += word_text + " "
            current_sentence["end"] = word.get("end", 0)
            
            if not current_sentence["start"]:
                current_sentence["start"] = word.get("start", 0)
            
            if any(word_text.rstrip().endswith(p) for p in ['.', '!', '?']):
                current_sentence["text"] = current_sentence["text"].strip()
                if current_sentence["text"]:
                    sentences.append(current_sentence)
                current_sentence = {"start": 0, "end": 0, "text": "", "words": []}
        
        if current_sentence["text"].strip():
            current_sentence["text"] = current_sentence["text"].strip()
            sentences.append(current_sentence)
        
        # Score sentences
        viral_keywords = {
            "controversial": ["actually", "wrong", "truth", "secret", "nobody", "everyone", "always", "never"],
            "emotional": ["amazing", "incredible", "love", "hate", "worst", "best", "changed", "life"],
            "educational": ["how to", "why", "because", "learn", "tip", "hack", "strategy"],
            "funny": ["literally", "imagine", "wait", "hilarious", "crazy", "insane"],
        }
        
        # Create segments of appropriate length
        moments = []
        i = 0
        
        while i < len(sentences):
            segment_sentences = [sentences[i]]
            segment_start = sentences[i]["start"]
            segment_end = sentences[i]["end"]
            
            j = i + 1
            while j < len(sentences) and (segment_end - segment_start) < min_duration:
                segment_sentences.append(sentences[j])
                segment_end = sentences[j]["end"]
                j += 1
            
            duration = segment_end - segment_start
            if duration < min_duration:
                i += 1
                continue
            
            while duration > max_duration and len(segment_sentences) > 1:
                segment_sentences.pop()
                segment_end = segment_sentences[-1]["end"]
                duration = segment_end - segment_start
            
            text = " ".join(s["text"] for s in segment_sentences)
            
            # Score
            score = 50
            category = "general"
            reasons = []
            text_lower = text.lower()
            
            for cat, keywords in viral_keywords.items():
                for kw in keywords:
                    if kw in text_lower:
                        score += 5
                        category = cat
                        reasons.append(f"Contains '{kw}'")
            
            if "?" in text:
                score += 10
                reasons.append("Engaging question")
            if "!" in text:
                score += 5
                reasons.append("Shows emotion")
            if any(c.isdigit() for c in text):
                score += 5
                reasons.append("Contains numbers")
            
            word_count = len(text.split())
            if 15 <= word_count <= 50:
                score += 10
            
            moments.append({
                "index": len(moments),
                "start_time": segment_start,
                "end_time": segment_end,
                "duration": duration,
                "text": text,
                "virality_score": min(score, 95),
                "virality_reason": " | ".join(reasons) if reasons else "Potential engaging content",
                "suggested_caption": f"🔥 {text[:80]}...",
                "suggested_hashtags": ["viral", "fyp", category],
                "hook": text.split('.')[0] if '.' in text else text[:50],
                "category": category,
                "selected": len(moments) < num_clips,
            })
            
            i = j if j > i else i + 1
        
        moments.sort(key=lambda x: x["virality_score"], reverse=True)
        
        # Update selected flag for top N
        for idx, m in enumerate(moments):
            m["selected"] = idx < num_clips
        
        return moments[:num_clips * 3]  # Return more candidates than needed
    
    def process_video_ffmpeg(self, job_id: str, video_path: Path, config: dict) -> dict:
        """Process video using FFmpeg directly (simple mode without Whisper)."""
        job_dir = self.work_dir / job_id
        clips_dir = job_dir / "clips"
        clips_dir.mkdir(exist_ok=True)
        
        # Get video duration
        probe_cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            str(video_path)
        ]
        result = subprocess.run(probe_cmd, capture_output=True, text=True)
        total_duration = float(result.stdout.strip())
        
        logger.info(f"📹 Video duration: {total_duration:.1f}s")
        
        num_clips = config.get('num_clips', 10)
        min_dur = config.get('min_duration', 20)
        max_dur = config.get('max_duration', 60)
        crop_vertical = config.get('crop_vertical', True)
        
        # Calculate segment duration
        segment_duration = total_duration / num_clips
        if segment_duration < min_dur:
            segment_duration = min_dur
            num_clips = int(total_duration / segment_duration)
        elif segment_duration > max_dur:
            segment_duration = max_dur
            num_clips = int(total_duration / segment_duration)
        
        if num_clips < 1:
            num_clips = 1
            segment_duration = min(total_duration, max_dur)
        
        logger.info(f"🎬 Creating {num_clips} clips of ~{segment_duration:.0f}s each")
        
        clips = []
        for i in range(num_clips):
            # Check for cancellation
            should_stop = self.update_job_progress(
                job_id,
                0.1 + (0.8 * i / num_clips),
                f"Rendering clip {i+1}/{num_clips}",
                f"Processing..."
            )
            if should_stop:
                logger.info("⏹️  Job cancelled")
                return {"success": False, "error": "Cancelled"}
            
            start_time = i * segment_duration
            end_time = min(start_time + segment_duration, total_duration)
            duration = end_time - start_time
            
            clip_path = clips_dir / f"clip_{i+1:02d}.mp4"
            
            logger.info(f"   Clip {i+1}: {start_time:.1f}s - {end_time:.1f}s")
            
            # Build FFmpeg command
            cmd = [
                'ffmpeg', '-y',
                '-ss', str(start_time),
                '-i', str(video_path),
                '-t', str(duration),
            ]
            
            if crop_vertical:
                # Crop to 9:16 vertical
                cmd.extend(['-vf', 'crop=ih*9/16:ih,scale=1080:1920'])
            
            cmd.extend([
                '-c:v', 'libx264',
                '-preset', 'fast',
                '-crf', '23',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-movflags', '+faststart',
                str(clip_path)
            ])
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"FFmpeg error: {result.stderr[-500:]}")
                continue
            
            clips.append({
                "index": i + 1,
                "path": str(clip_path),
                "start_time": start_time,
                "end_time": end_time,
                "duration": duration,
                "score": 1.0,
                "text": f"Clip {i+1}"
            })
        
        return {"success": True, "clips": clips}
    
    def process_job(self, job: dict) -> dict:
        """Process a video clipping job locally."""
        job_id = job["job_id"]
        job_type = job.get("job_type", "render")  # 'smart' or 'render'
        config = job.get("config", {})
        video_url = job.get("video_url")
        youtube_url = job.get("youtube_url")
        
        logger.info(f"")
        logger.info(f"{'='*60}")
        logger.info(f"🎬 Processing Job: {job_id}")
        logger.info(f"   Type: {job_type.upper()}")
        logger.info(f"{'='*60}")
        
        if video_url:
            logger.info(f"📹 Video URL: {video_url[:60]}...")
        
        logger.info(f"⚙️  Config: {json.dumps(config, indent=2)}")
        
        self.current_job = job_id
        job_dir = self.work_dir / job_id
        job_dir.mkdir(exist_ok=True)
        
        start_time = datetime.now()
        
        try:
            # Download video from Railway (already downloaded by Railway)
            video_path = self.download_video(job_id, video_url, youtube_url)
            
            # Handle smart jobs (transcribe + analyze)
            if job_type == "smart":
                logger.info(f"")
                logger.info(f"🧠 SMART JOB: Transcribe + Analyze on YOUR PC")
                result = self.process_smart_job(job_id, video_path, config)
                
                processing_time = (datetime.now() - start_time).total_seconds()
                result["processing_time"] = processing_time
                result["job_id"] = job_id
                
                return result
            
            self.update_job_progress(job_id, 0.1, "Download complete", "Starting processing...")
            
            # Use simple FFmpeg processing (no Whisper)
            burn_captions = config.get("burn_captions", False)
            
            if burn_captions:
                # Try to use the full pipeline with Whisper
                logger.info("🎙️  Burn captions enabled - using full pipeline with Whisper")
                try:
                    # Add backend to path
                    backend_path = Path(__file__).parent / "backend"
                    if backend_path.exists():
                        sys.path.insert(0, str(backend_path))
                    
                    from backend.app.services.clipper.pipeline import ClipperPipeline, PipelineConfig
                    
                    def progress_callback(stage: str, progress: float):
                        adjusted = 0.1 + (progress * 0.9)
                        should_stop = self.update_job_progress(job_id, adjusted, stage, stage)
                        logger.info(f"📊 [{adjusted*100:.0f}%] {stage}")
                        if should_stop:
                            raise Exception("Job cancelled")
                    
                    pipeline_config = PipelineConfig(
                        num_clips=config.get("num_clips", 10),
                        min_duration=config.get("min_duration", 20),
                        max_duration=config.get("max_duration", 60),
                        pause_threshold=config.get("pause_threshold", 0.7),
                        caption_style=config.get("caption_style", "default"),
                        whisper_model=config.get("whisper_model", "base"),
                        burn_captions=True,
                        crop_vertical=config.get("crop_vertical", True),
                        auto_center=config.get("auto_center", True),
                    )
                    
                    pipeline = ClipperPipeline(pipeline_config, progress_callback=progress_callback)
                    result = pipeline.run(video_path, job_dir)
                    
                    if result.success:
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
                        }
                    else:
                        return {"success": False, "error": result.error}
                        
                except ImportError as e:
                    logger.warning(f"Full pipeline not available: {e}")
                    logger.info("Falling back to simple FFmpeg processing...")
            
            # Simple FFmpeg processing (no captions)
            result = self.process_video_ffmpeg(job_id, video_path, config)
            
            if result.get("success"):
                processing_time = (datetime.now() - start_time).total_seconds()
                logger.info(f"✅ Job completed in {processing_time:.1f}s")
                logger.info(f"🎥 Created {len(result['clips'])} clips")
                
                return {
                    "success": True,
                    "job_id": job_id,
                    "clips": result["clips"],
                    "processing_time": processing_time,
                }
            else:
                return {
                    "success": False,
                    "job_id": job_id,
                    "error": result.get("error", "Processing failed"),
                }
                
        except Exception as e:
            logger.exception(f"❌ Job failed")
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
                logger.error(f"❌ Reported failure to server: {result.get('error')}")
            except Exception as e:
                logger.error(f"Could not report failure: {e}")
            return False
        
        logger.info(f"⬆️  Uploading {len(result.get('clips', []))} clips to server...")
        
        try:
            for clip in result.get("clips", []):
                clip_path = Path(clip["path"])
                if clip_path.exists():
                    logger.info(f"   📤 Uploading clip {clip['index']}...")
                    with open(clip_path, 'rb') as f:
                        resp = requests.post(
                            f"{self.api_base}/worker/jobs/{job_id}/upload-clip",
                            files={"file": (clip_path.name, f, "video/mp4")},
                            data={
                                "index": clip["index"],
                                "start_time": clip["start_time"],
                                "end_time": clip["end_time"],
                                "duration": clip["duration"],
                                "score": clip.get("score", 1.0),
                                "text": clip.get("text", ""),
                            },
                            timeout=120
                        )
                        if resp.status_code == 200:
                            logger.info(f"   ✅ Clip {clip['index']} uploaded")
                        else:
                            logger.warning(f"   ⚠️  Clip {clip['index']} upload failed: {resp.status_code}")
            
            # Mark job complete
            requests.post(
                f"{self.api_base}/worker/jobs/{job_id}/complete",
                json={
                    "worker_id": self.worker_id,
                    "success": True,
                    "clips_count": len(result.get("clips", [])),
                    "processing_time": result.get("processing_time", 0),
                },
                timeout=30
            )
            
            logger.info(f"✅ All results uploaded!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Upload failed: {e}")
            return False
    
    def cleanup_job(self, job_id: str):
        """Clean up local files for a completed job."""
        job_dir = self.work_dir / job_id
        if job_dir.exists():
            shutil.rmtree(job_dir)
            logger.info(f"🧹 Cleaned up: {job_dir}")
    
    def run(self, poll_interval: int = 5):
        """Main worker loop."""
        logger.info(f"")
        logger.info(f"{'='*60}")
        logger.info(f"🚀 LOCAL WORKER STARTED")
        logger.info(f"{'='*60}")
        logger.info(f"")
        logger.info(f"Polling: {self.server_url}")
        logger.info(f"Press Ctrl+C to stop")
        logger.info(f"")
        
        if not self.check_server():
            logger.error("Cannot start - server unreachable")
            return
        
        self.register_worker()
        
        consecutive_errors = 0
        
        while self.running:
            try:
                job = self.fetch_pending_job()
                
                if job:
                    consecutive_errors = 0
                    result = self.process_job(job)
                    self.upload_results(job["job_id"], result)
                    self.cleanup_job(job["job_id"])
                else:
                    # No jobs, wait
                    print(f"\r⏳ Waiting for jobs... (checking every {poll_interval}s)", end="", flush=True)
                    time.sleep(poll_interval)
                    
            except KeyboardInterrupt:
                logger.info(f"\n⏹️  Shutting down...")
                self.running = False
                break
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"Error: {e}")
                
                if consecutive_errors > 10:
                    logger.error("Too many errors, stopping")
                    break
                
                time.sleep(min(poll_interval * consecutive_errors, 60))
        
        logger.info(f"👋 Worker stopped")


def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║           🎬 VIDEO CLIPPER - LOCAL WORKER                    ║
╠══════════════════════════════════════════════════════════════╣
║  This worker processes video jobs using YOUR computer.       ║
║  Jobs are submitted via the web UI, but processed here.      ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    # Check requirements
    if not check_ffmpeg():
        print("❌ FFmpeg not found! Please install it:")
        print("   macOS:   brew install ffmpeg")
        print("   Ubuntu:  sudo apt install ffmpeg")
        print("   Windows: choco install ffmpeg")
        sys.exit(1)
    print("✅ FFmpeg found")
    
    if not check_yt_dlp():
        print("⚠️  yt-dlp not found - will install if needed")
    else:
        print("✅ yt-dlp found")
    
    parser = argparse.ArgumentParser(
        description="Local worker for video clipper"
    )
    parser.add_argument(
        "server",
        nargs="?",
        default=os.environ.get("CLIPPER_SERVER", "http://localhost:8000"),
        help="Server URL (e.g., https://your-app.railway.app)"
    )
    parser.add_argument(
        "--poll-interval", "-p",
        type=int,
        default=5,
        help="Seconds between polling (default: 5)"
    )
    parser.add_argument(
        "--worker-id", "-w",
        default=None,
        help="Custom worker ID"
    )
    
    args = parser.parse_args()
    
    print(f"\n🌐 Connecting to: {args.server}\n")
    
    worker = LocalWorker(
        server_url=args.server,
        worker_id=args.worker_id,
    )
    worker.run(poll_interval=args.poll_interval)


if __name__ == "__main__":
    main()
