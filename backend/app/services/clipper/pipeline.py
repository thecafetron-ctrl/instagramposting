"""Main pipeline module - orchestrates the full clipping workflow."""

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from .transcribe import (
    Transcript, transcribe_video, save_transcript_json,
    save_transcript_srt, load_transcript_json
)
from .segment import segment_transcript
from .score import score_clips, select_top_clips, ScoredClip
from .captions import generate_clip_captions, CaptionStyle, get_style_preset
from .render import render_final_clip, create_thumbnail
from .crop import check_ffmpeg, get_ffmpeg_install_instructions

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """Configuration for the clipping pipeline."""
    num_clips: int = 10
    min_duration: float = 20.0
    max_duration: float = 60.0
    pause_threshold: float = 0.7
    clip_padding: float = 0.2
    whisper_model: str = "base"
    language: Optional[str] = None
    crop_vertical: bool = True
    auto_center: bool = True
    caption_style: str = "default"
    burn_captions: bool = True
    output_format: str = "mp4"
    create_thumbnails: bool = True


@dataclass
class ClipResult:
    """Result for a single generated clip."""
    index: int
    video_path: str
    thumbnail_path: Optional[str]
    start_time: float
    end_time: float
    duration: float
    score: float
    text: str


@dataclass
class PipelineResult:
    """Result of the full pipeline run."""
    success: bool
    source_video: str
    output_dir: str
    transcript_json: str
    transcript_srt: str
    clips: list[ClipResult]
    total_duration: float
    processing_time: float
    error: Optional[str] = None


class ClipperPipeline:
    """Main pipeline for video clipping and captioning."""
    
    def __init__(
        self,
        config: Optional[PipelineConfig] = None,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ):
        self.config = config or PipelineConfig()
        self.progress_callback = progress_callback
        
        if not check_ffmpeg():
            raise RuntimeError(get_ffmpeg_install_instructions())
    
    def _update_progress(self, stage: str, progress: float):
        if self.progress_callback:
            self.progress_callback(stage, progress)
        logger.info(f"[{progress*100:.0f}%] {stage}")
    
    def run(
        self,
        video_path: str | Path,
        output_dir: str | Path,
        transcript_path: Optional[str | Path] = None,
    ) -> PipelineResult:
        """Run the full clipping pipeline."""
        start_time = datetime.now()
        video_path = Path(video_path)
        output_dir = Path(output_dir)
        
        if not video_path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")
        
        output_dir.mkdir(parents=True, exist_ok=True)
        clips_dir = output_dir / "clips"
        clips_dir.mkdir(exist_ok=True)
        
        try:
            self._update_progress("Transcribing video", 0.0)
            
            if transcript_path and Path(transcript_path).exists():
                logger.info(f"Loading existing transcript: {transcript_path}")
                transcript = load_transcript_json(transcript_path)
            else:
                transcript = transcribe_video(
                    video_path,
                    model_size=self.config.whisper_model,
                    language=self.config.language,
                )
            
            transcript_json_path = output_dir / "transcript.json"
            transcript_srt_path = output_dir / "transcript.srt"
            save_transcript_json(transcript, transcript_json_path)
            save_transcript_srt(transcript, transcript_srt_path)
            
            self._update_progress("Transcription complete", 0.15)
            
            self._update_progress("Segmenting transcript", 0.20)
            
            candidates = segment_transcript(
                transcript,
                min_duration=self.config.min_duration,
                max_duration=self.config.max_duration,
                pause_threshold=self.config.pause_threshold,
                padding=self.config.clip_padding,
            )
            
            if not candidates:
                logger.warning("No candidate clips found")
                return PipelineResult(
                    success=False,
                    source_video=str(video_path),
                    output_dir=str(output_dir),
                    transcript_json=str(transcript_json_path),
                    transcript_srt=str(transcript_srt_path),
                    clips=[],
                    total_duration=transcript.duration,
                    processing_time=(datetime.now() - start_time).total_seconds(),
                    error="No candidate clips found in video"
                )
            
            self._update_progress("Segmentation complete", 0.30)
            
            self._update_progress("Scoring clips", 0.35)
            
            scored = score_clips(candidates)
            selected = select_top_clips(scored, n=self.config.num_clips)
            
            self._update_progress("Scoring complete", 0.40)
            
            self._update_progress("Rendering clips", 0.45)
            
            all_words = transcript.all_words()
            style = get_style_preset(self.config.caption_style)
            clip_results = []
            
            for i, clip in enumerate(selected):
                progress = 0.45 + (0.50 * (i / len(selected)))
                self._update_progress(f"Rendering clip {i+1}/{len(selected)}", progress)
                
                clip_name = f"clip_{i+1:02d}"
                clip_video_path = clips_dir / f"{clip_name}.{self.config.output_format}"
                
                ass_path = None
                if self.config.burn_captions:
                    ass_path = clips_dir / f"{clip_name}.ass"
                    generate_clip_captions(
                        all_words,
                        clip.start,
                        clip.end,
                        ass_path,
                        style=style,
                    )
                
                render_final_clip(
                    video_path,
                    clip_video_path,
                    clip.start,
                    clip.end,
                    ass_path=ass_path if self.config.burn_captions else None,
                    crop_vertical=self.config.crop_vertical,
                    auto_center=self.config.auto_center,
                )
                
                thumbnail_path = None
                if self.config.create_thumbnails:
                    thumbnail_path = clips_dir / f"{clip_name}_thumb.jpg"
                    try:
                        create_thumbnail(clip_video_path, thumbnail_path)
                    except Exception as e:
                        logger.warning(f"Thumbnail creation failed: {e}")
                        thumbnail_path = None
                
                clip_results.append(ClipResult(
                    index=i + 1,
                    video_path=str(clip_video_path),
                    thumbnail_path=str(thumbnail_path) if thumbnail_path else None,
                    start_time=clip.start,
                    end_time=clip.end,
                    duration=clip.duration,
                    score=clip.total_score,
                    text=clip.text[:200] + "..." if len(clip.text) > 200 else clip.text,
                ))
            
            self._update_progress("Pipeline complete", 1.0)
            
            results_path = output_dir / "results.json"
            with open(results_path, 'w') as f:
                json.dump({
                    "config": asdict(self.config),
                    "clips": [asdict(c) for c in clip_results],
                }, f, indent=2)
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            return PipelineResult(
                success=True,
                source_video=str(video_path),
                output_dir=str(output_dir),
                transcript_json=str(transcript_json_path),
                transcript_srt=str(transcript_srt_path),
                clips=clip_results,
                total_duration=transcript.duration,
                processing_time=processing_time,
            )
            
        except Exception as e:
            logger.exception("Pipeline failed")
            processing_time = (datetime.now() - start_time).total_seconds()
            return PipelineResult(
                success=False,
                source_video=str(video_path),
                output_dir=str(output_dir),
                transcript_json="",
                transcript_srt="",
                clips=[],
                total_duration=0,
                processing_time=processing_time,
                error=str(e),
            )
