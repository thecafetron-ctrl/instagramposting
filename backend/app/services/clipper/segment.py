"""Segment detection module - splits transcript into candidate clips."""

import logging
import re
from dataclasses import dataclass
from typing import Optional

from .transcribe import Transcript, Word

logger = logging.getLogger(__name__)


@dataclass
class CandidateClip:
    """A candidate clip segment."""
    start: float
    end: float
    words: list[Word]
    text: str
    
    @property
    def duration(self) -> float:
        return self.end - self.start
    
    @property
    def word_count(self) -> int:
        return len(self.words)


def find_pause_gaps(
    words: list[Word],
    pause_threshold: float = 0.7
) -> list[tuple[int, float]]:
    """Find significant pauses between words."""
    gaps = []
    for i in range(len(words) - 1):
        gap = words[i + 1].start - words[i].end
        if gap >= pause_threshold:
            gaps.append((i, gap))
    return gaps


def segment_transcript(
    transcript: Transcript,
    min_duration: float = 20.0,
    max_duration: float = 60.0,
    pause_threshold: float = 0.7,
    padding: float = 0.2,
) -> list[CandidateClip]:
    """Split transcript into candidate clip segments."""
    all_words = transcript.all_words()
    if not all_words:
        logger.warning("No words in transcript")
        return []
    
    pause_gaps = find_pause_gaps(all_words, pause_threshold)
    pause_indices = {idx for idx, _ in pause_gaps}
    
    sentence_end_indices = set()
    for i, word in enumerate(all_words):
        if word.word and word.word[-1] in '.!?':
            sentence_end_indices.add(i)
    
    break_points = pause_indices | sentence_end_indices
    break_points = sorted(break_points)
    
    candidates = []
    
    if break_points:
        start_idx = 0
        for bp in break_points:
            end_idx = bp + 1
            
            if end_idx > start_idx and end_idx <= len(all_words):
                clip_words = all_words[start_idx:end_idx]
                if clip_words:
                    start_time = max(0, clip_words[0].start - padding)
                    end_time = min(transcript.duration, clip_words[-1].end + padding)
                    duration = end_time - start_time
                    
                    if min_duration <= duration <= max_duration:
                        text = ' '.join(w.word for w in clip_words)
                        candidates.append(CandidateClip(
                            start=start_time,
                            end=end_time,
                            words=clip_words,
                            text=text
                        ))
            
            start_idx = end_idx
    
    window_candidates = _create_window_segments(
        all_words, transcript.duration,
        min_duration, max_duration, padding
    )
    candidates.extend(window_candidates)
    
    candidates = _deduplicate_clips(candidates, overlap_threshold=0.5)
    
    logger.info(f"Generated {len(candidates)} candidate clips")
    return candidates


def _create_window_segments(
    words: list[Word],
    total_duration: float,
    min_duration: float,
    max_duration: float,
    padding: float,
) -> list[CandidateClip]:
    """Create candidate segments using sliding window approach."""
    candidates = []
    
    target_durations = [
        min_duration,
        (min_duration + max_duration) / 2,
        max_duration * 0.8
    ]
    
    for target_dur in target_durations:
        step = target_dur * 0.5
        current_time = 0
        
        while current_time < total_duration - min_duration:
            end_time = min(current_time + target_dur, total_duration)
            
            window_words = [
                w for w in words
                if w.start >= current_time - padding and w.end <= end_time + padding
            ]
            
            if window_words and len(window_words) >= 5:
                start = max(0, window_words[0].start - padding)
                end = min(total_duration, window_words[-1].end + padding)
                duration = end - start
                
                if min_duration <= duration <= max_duration:
                    adjusted_words = _align_to_sentence(window_words, words)
                    if adjusted_words:
                        start = max(0, adjusted_words[0].start - padding)
                        end = min(total_duration, adjusted_words[-1].end + padding)
                        window_words = adjusted_words
                    
                    text = ' '.join(w.word for w in window_words)
                    candidates.append(CandidateClip(
                        start=start,
                        end=end,
                        words=window_words,
                        text=text
                    ))
            
            current_time += step
    
    return candidates


def _align_to_sentence(
    window_words: list[Word],
    all_words: list[Word]
) -> Optional[list[Word]]:
    """Try to adjust window to align with sentence boundaries."""
    if not window_words:
        return None
    
    try:
        start_idx = all_words.index(window_words[0])
        end_idx = all_words.index(window_words[-1])
    except ValueError:
        return window_words
    
    new_start_idx = start_idx
    for i in range(start_idx, max(0, start_idx - 10), -1):
        if i == 0 or (all_words[i-1].word and all_words[i-1].word[-1] in '.!?'):
            new_start_idx = i
            break
    
    new_end_idx = end_idx
    for i in range(end_idx, min(len(all_words), end_idx + 10)):
        word = all_words[i]
        if word.word and word.word[-1] in '.!?':
            new_end_idx = i
            break
    
    return all_words[new_start_idx:new_end_idx + 1]


def _deduplicate_clips(
    clips: list[CandidateClip],
    overlap_threshold: float = 0.5
) -> list[CandidateClip]:
    """Remove clips that overlap too much."""
    if not clips:
        return []
    
    def duration_score(clip):
        ideal = 35
        return -abs(clip.duration - ideal)
    
    sorted_clips = sorted(clips, key=duration_score, reverse=True)
    
    kept = []
    for clip in sorted_clips:
        is_duplicate = False
        for kept_clip in kept:
            overlap = _calculate_overlap(clip, kept_clip)
            if overlap > overlap_threshold:
                is_duplicate = True
                break
        
        if not is_duplicate:
            kept.append(clip)
    
    return kept


def _calculate_overlap(clip1: CandidateClip, clip2: CandidateClip) -> float:
    """Calculate overlap ratio between two clips."""
    overlap_start = max(clip1.start, clip2.start)
    overlap_end = min(clip1.end, clip2.end)
    
    if overlap_end <= overlap_start:
        return 0.0
    
    overlap_duration = overlap_end - overlap_start
    min_duration = min(clip1.duration, clip2.duration)
    
    return overlap_duration / min_duration if min_duration > 0 else 0.0
