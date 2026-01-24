"""Transcription module using faster-whisper with word-level timestamps."""

import json
import logging
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class Word:
    """A single word with timing information."""
    word: str
    start: float
    end: float
    confidence: float = 1.0


@dataclass
class Segment:
    """A transcript segment (sentence/phrase)."""
    text: str
    start: float
    end: float
    words: list[Word]


@dataclass
class Transcript:
    """Full transcript with segments and words."""
    segments: list[Segment]
    language: str
    duration: float

    def to_dict(self) -> dict:
        return {
            "language": self.language,
            "duration": self.duration,
            "segments": [
                {
                    "text": seg.text,
                    "start": seg.start,
                    "end": seg.end,
                    "words": [asdict(w) for w in seg.words]
                }
                for seg in self.segments
            ]
        }

    def all_words(self) -> list[Word]:
        """Get all words flattened."""
        return [w for seg in self.segments for w in seg.words]


def check_cuda_available() -> bool:
    """Check if CUDA is available for GPU acceleration."""
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


def transcribe_video(
    video_path: str | Path,
    model_size: str = "base",
    language: Optional[str] = None,
    device: Optional[str] = None,
) -> Transcript:
    """
    Transcribe a video file using faster-whisper.
    
    Args:
        video_path: Path to the video file
        model_size: Whisper model size (tiny, base, small, medium, large-v2)
        language: Language code (auto-detect if None)
        device: Device to use (auto-detect if None)
    
    Returns:
        Transcript object with word-level timestamps
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")
    
    # Auto-detect device
    if device is None:
        device = "cuda" if check_cuda_available() else "cpu"
    
    compute_type = "float16" if device == "cuda" else "int8"
    
    logger.info(f"Loading faster-whisper model '{model_size}' on {device}")
    
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise ImportError(
            "faster-whisper is not installed. Install with: pip install faster-whisper"
        )
    
    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    
    logger.info(f"Transcribing: {video_path}")
    
    segments_gen, info = model.transcribe(
        str(video_path),
        language=language,
        word_timestamps=True,
        vad_filter=True,
    )
    
    segments = []
    for seg in segments_gen:
        words = []
        if seg.words:
            for w in seg.words:
                words.append(Word(
                    word=w.word.strip(),
                    start=w.start,
                    end=w.end,
                    confidence=w.probability if hasattr(w, 'probability') else 1.0
                ))
        
        segments.append(Segment(
            text=seg.text.strip(),
            start=seg.start,
            end=seg.end,
            words=words
        ))
    
    transcript = Transcript(
        segments=segments,
        language=info.language,
        duration=info.duration
    )
    
    logger.info(f"Transcription complete: {len(segments)} segments, {info.language}")
    return transcript


def save_transcript_json(transcript: Transcript, output_path: str | Path) -> Path:
    """Save transcript as JSON file."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(transcript.to_dict(), f, indent=2, ensure_ascii=False)
    
    logger.info(f"Saved transcript JSON: {output_path}")
    return output_path


def save_transcript_srt(transcript: Transcript, output_path: str | Path) -> Path:
    """Save transcript as SRT subtitle file."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    def format_time(seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    
    lines = []
    for i, seg in enumerate(transcript.segments, 1):
        lines.append(str(i))
        lines.append(f"{format_time(seg.start)} --> {format_time(seg.end)}")
        lines.append(seg.text)
        lines.append("")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    logger.info(f"Saved transcript SRT: {output_path}")
    return output_path


def load_transcript_json(json_path: str | Path) -> Transcript:
    """Load transcript from JSON file."""
    json_path = Path(json_path)
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    segments = []
    for seg_data in data["segments"]:
        words = [Word(**w) for w in seg_data["words"]]
        segments.append(Segment(
            text=seg_data["text"],
            start=seg_data["start"],
            end=seg_data["end"],
            words=words
        ))
    
    return Transcript(
        segments=segments,
        language=data["language"],
        duration=data["duration"]
    )
